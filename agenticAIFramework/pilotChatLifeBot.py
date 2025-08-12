#!/usr/bin/env python3
"""
Agentic policy‑chatbot – works with LangGraph 0.6.4.
"""

# --------------------------------------------------------------
# 1️⃣  Imports
# --------------------------------------------------------------
import os, json, re, time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END   # important for 0.6.x

# --------------------------------------------------------------
# 2️⃣  Load .env
# --------------------------------------------------------------
load_dotenv()

# --------------------------------------------------------------
# 3️⃣  LLM – Ollama
# --------------------------------------------------------------
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST)

# --------------------------------------------------------------
# 4️⃣  Dummy legacy API
# --------------------------------------------------------------
def call_legacy_api(policy_number: str) -> dict:
    time.sleep(0.1)   # pretend network latency
    return {
        "policy_number": policy_number,
        "holder": "Jane Doe",
        "policy_type": "home insurance",
        "sum_insured": 275_000,
        "effective_date": "2023-06-01",
        "expiry_date": "2024-06-01",
        "coverage": [
            {"type": "fire", "limit": 200_000},
            {"type": "theft", "limit": 50_000},
            {"type": "natural_disaster", "limit": 50_000},
        ],
    }

# --------------------------------------------------------------
# 5️⃣  **State definition** – now a dataclass
# --------------------------------------------------------------
@dataclass
class State:
    """Data that flows through the graph."""
    user_message: str = ""                      # filled by the chat loop
    last_api_result: Optional[str] = None      # not used in the dummy version
    answer: Optional[str] = None               # final reply

# --------------------------------------------------------------
# 6️⃣  Helper – extract a 6‑char policy number
# --------------------------------------------------------------
def extract_policy_number(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z0-9]{6})\b", text, flags=re.I)
    return m.group(1).upper() if m else None

# --------------------------------------------------------------
# 7️⃣  Graph nodes
# --------------------------------------------------------------
def router_node(state: State) -> State:
    prompt = (
        "You are a routing assistant for a policy chatbot.\n"
        f"User said: \"{state.user_message}\"\n"
        "Do we need to call the legacy policy system to answer this?"
    )
    resp = llm.invoke([HumanMessage(content=prompt)])
    state.answer = resp.content.strip().lower()
    return state


def policy_agent(state: State) -> State:
    policy_no = extract_policy_number(state.user_message)
    if not policy_no:
        state.answer = "Sorry, I couldn’t find a policy number in your request."
        return state

    api_resp = call_legacy_api(policy_no)

    sys_prompt = SystemMessage(
        content=(
            "Below is a JSON record for a policy. The user asked: "
            f"{state.user_message}. Return only the requested information, nothing else."
        )
    )
    hum_prompt = HumanMessage(
        content=f"Policy JSON:\n{json.dumps(api_resp, indent=2)}"
    )
    llm_resp = llm.invoke([sys_prompt, hum_prompt])
    state.answer = llm_resp.content.strip()
    return state


def finish_node(state: State) -> State:
    if state.answer is None:
        sys_msg = SystemMessage(content="You are a friendly insurance chatbot.")
        hum_msg = HumanMessage(content=state.user_message)
        resp = llm.invoke([sys_msg, hum_msg])
        state.answer = resp.content.strip()
    return state

# --------------------------------------------------------------
# 8️⃣  Build the graph (0.6.x API)
# --------------------------------------------------------------
builder = StateGraph(State)

builder.add_node("router",       router_node)
builder.add_node("policy_agent", policy_agent)
builder.add_node("finish",       finish_node)

# entry point
builder.add_edge(START, "router")

# conditional routing – note the *plural* name is correct for 0.6.x
builder.add_conditional_edges(
    "router",
    lambda s: "policy_agent" if "yes" in s.answer.lower() else "finish"
)

builder.add_edge("policy_agent", "finish")
builder.add_edge("finish", END)

graph = builder.compile()

# --------------------------------------------------------------
# 9️⃣  Simple console chatbot
# --------------------------------------------------------------
def chat_loop():
    print("🚀  Agentic Policy Bot (dummy API) – type ‘quit’ to exit")
    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in {"quit", "exit"}:
                print("👋  Bye!")
                break
            init_state = State(user_message=user_input)   # works now
            result = graph.invoke(init_state)
            print("\n🤖", result["answer"])
            
        except Exception as exc:
            print(f"\n❌  Unexpected error: {exc}")

if __name__ == "__main__":
    chat_loop()
