function formatTime() {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function toggleTheme() {
  document.body.classList.toggle("dark");
}

async function sendMessage() {
  const input = document.getElementById("userInput");
  const chatbox = document.getElementById("chatbox");
  const typing = document.getElementById("typing");
  const message = input.value.trim();
  if (!message) return;

  // Show user message
  chatbox.innerHTML += `
    <div class="flex justify-end">
      <div class="bg-blue-600 text-white px-4 py-2 rounded-lg max-w-xs text-sm shadow-md">
        ${message}
        <div class="text-xs text-right mt-1 opacity-70">${formatTime()}</div>
      </div>
    </div>
  `;
  input.value = "";
  chatbox.scrollTop = chatbox.scrollHeight;

  typing.style.display = "block";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message })
    });

    const data = await response.json();
    typing.style.display = "none";

    chatbox.innerHTML += `
      <div class="flex justify-start">
        <div class="bg-gray-200 dark:bg-gray-700 text-gray-800 dark:text-gray-100 px-4 py-2 rounded-lg max-w-xs text-sm shadow-md">
          ${data.reply}
          <div class="text-xs text-right mt-1 opacity-70">${formatTime()}</div>
        </div>
      </div>
    `;
    chatbox.scrollTop = chatbox.scrollHeight;
  } catch (err) {
    typing.style.display = "none";
    chatbox.innerHTML += `
      <div class="flex justify-start">
        <div class="bg-red-200 text-red-800 px-4 py-2 rounded-lg max-w-xs text-sm shadow-md">
          Error: ${err.message}
        </div>
      </div>
    `;
  }
}