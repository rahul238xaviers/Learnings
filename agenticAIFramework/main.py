#!/usr/bin/env python3
"""
Agentic policy chatbot – web version using FastAPI + LangGraph.
"""

# --------------------------------------------------------------
# 1️⃣ Imports
# --------------------------------------------------------------
import os, json, re, time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# --------------------------------------------------------------
# 2️⃣ Load environment
# --------------------------------------------------------------
load_dotenv()

# --------------------------------------------------------------
# 3️⃣ FastAPI setup
# --------------------------------------------------------------
app = FastAPI()
templates = Jinja2Templates(directory="agenticAIFramework/templates")
app.mount("/static", StaticFiles(directory="agenticAIFramework/static"), name="static")

# --------------------------------------------------------------
# 4️⃣ LLM – Ollama
# --------------------------------------------------------------
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
llm = ChatOllama(model=OLLAMA_MODEL, base_url=OLLAMA_HOST)

# --------------------------------------------------------------
# 5️⃣ Dummy legacy API
# --------------------------------------------------------------
def call_legacy_api(policy_number: str) -> dict:
    time.sleep(0.1)
    return {
        "policy_number": "P1234",
        "holder": "RK",
        "policy_type": "Life insurance",
        "sum_insured": 275_000,
        "effective_date": "2023-06-01",
        "expiry_date": "2050-06-01",
        "coverage": [
            {"type": "Death", "limit": 200_000},
            {"type": "TPD", "limit": 50_000},
            {"type": "Critical Illness", "limit": 50_000},
        ],
    }

# --------------------------------------------------------------
# 6️⃣ State definition
# --------------------------------------------------------------
@dataclass
class State:
    user_message: str = ""
    last_api_result: Optional[str] = None
    answer: Optional[str] = None

# --------------------------------------------------------------
# 7️⃣ Helper – extract policy number
# --------------------------------------------------------------
def extract_policy_number(text: str) -> Optional[str]:
    m = re.search(r"\b([A-Z0-9]{6})\b", text, flags=re.I)
    return m.group(1).upper() if m else None

# --------------------------------------------------------------
# 8️⃣ Graph nodes
# --------------------------------------------------------------
def router_node(state: State) -> State:
    prompt = (
        "You are a routing assistant for a policy chatbot.\n"
        f"User said: \"{state.user_message}\"\n"
        #"Do we need to call the legacy policy system to answer this?"
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
            "Below is a record for a policy. The user asked: "
            f"{state.user_message}. Return only the requested information, nothing else."
        )
    )
    hum_prompt = HumanMessage(content=f"\n{json.dumps(api_resp, indent=2)}")
    llm_resp = llm.invoke([sys_prompt, hum_prompt])
    state.answer = llm_resp.content.strip()
    print(state.answer)
    return state

def finish_node(state: State) -> State:
    if state.answer is None:
        sys_msg = SystemMessage(content="You are a friendly insurance chatbot.")
        hum_msg = HumanMessage(content=state.user_message)
        resp = llm.invoke([sys_msg, hum_msg])
        state.answer = resp.content.strip()
    return state

# --------------------------------------------------------------
# 9️⃣ Build LangGraph
# --------------------------------------------------------------
builder = StateGraph(State)
builder.add_node("router", router_node)
builder.add_node("policy_agent", policy_agent)
builder.add_node("finish", finish_node)
builder.add_edge(START, "router")
builder.add_conditional_edges("router", lambda s: "policy_agent" if "yes" in s.answer.lower() else "finish")
builder.add_edge("policy_agent", "finish")
builder.add_edge("finish", END)
graph = builder.compile()

# --------------------------------------------------------------
# 🔟 FastAPI routes
# --------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/chat")
async def chat(req: ChatRequest):
    try:
        state = State(user_message=req.message)
        result = graph.invoke(state)
        return JSONResponse(content={"reply": result["answer"]})
    except Exception as e:
        return JSONResponse(content={"reply": f"Error: {str(e)}"}, status_code=500)