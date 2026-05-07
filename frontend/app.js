const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const messages = document.querySelector("#messages");
const sendButton = document.querySelector("#send-button");
const statusBadge = document.querySelector("#status");

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;

  appendMessage("user", text);
  input.value = "";
  setLoading(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    if (!response.ok) {
      throw new Error("Request failed");
    }
    const data = await response.json();
    appendMessage("assistant", data.answer, data.sources || []);
    statusBadge.textContent = data.fallback ? "Fallback" : "Готов";
    statusBadge.classList.toggle("chat__status--error", Boolean(data.fallback));
  } catch (error) {
    appendMessage(
      "assistant",
      "Сервис временно недоступен. Попробуйте повторить запрос позже или обратитесь в IT: incident@company.ru."
    );
    statusBadge.textContent = "Ошибка";
    statusBadge.classList.add("chat__status--error");
  } finally {
    setLoading(false);
    input.focus();
  }
});

function appendMessage(role, text, sources = []) {
  const article = document.createElement("article");
  article.className = `chat__message chat__message--${role}`;

  const bubble = document.createElement("div");
  bubble.className = `chat__bubble chat__bubble--${role}`;
  bubble.textContent = text;

  if (sources.length > 0) {
    const sourceList = document.createElement("div");
    sourceList.className = "chat__source-badges";

    sources.forEach((source) => {
      const badge = document.createElement("div");
      badge.className = "chat__source-badge";

      const label = document.createElement("span");
      label.className = "chat__source-label";
      label.textContent = "Источник";

      const text = document.createElement("span");
      text.textContent = `${source.document}, раздел: ${source.section}`;

      badge.append(label, text);
      sourceList.appendChild(badge);
    });

    bubble.appendChild(sourceList);
  }

  article.appendChild(bubble);
  messages.appendChild(article);
  messages.scrollTop = messages.scrollHeight;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  input.disabled = isLoading;
  statusBadge.textContent = isLoading ? "Ищу ответ" : "Готов";
  if (isLoading) {
    statusBadge.classList.remove("chat__status--error");
  }
}
