/**
 * public/widget/chat-widget.js
 * Self-contained embeddable chat widget.
 * Embed with: <script src="https://tissatech.com/widget/chat-widget.js"
 *              data-api-key="tst_xxxxxxxx"
 *              data-workspace="tissatech"></script>
 */
(function () {
  "use strict";

  const script = document.currentScript;
  const API_KEY = script?.getAttribute("data-api-key") ?? "";
  const API_URL = script?.getAttribute("data-api-url") ?? "https://api.tissatech.com";

  // ── State ──────────────────────────────────────────────────────────────────
  let isOpen = false;
  let sessionId = sessionStorage.getItem("tst_session") ?? generateId();
  let conversationId = null;
  let config = { primary_color: "#2563EB", bot_name: "Assistant", greeting_message: "Hi! How can I help?" };
  let isStreaming = false;

  sessionStorage.setItem("tst_session", sessionId);

  // ── Styles ─────────────────────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    #tst-widget-btn {
      position: fixed; bottom: 24px; right: 24px; z-index: 9999;
      width: 56px; height: 56px; border-radius: 50%; border: none;
      background: var(--tst-primary, #2563EB); color: white;
      cursor: pointer; box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      display: flex; align-items: center; justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s; font-size: 22px;
    }
    #tst-widget-btn:hover { transform: scale(1.05); box-shadow: 0 6px 20px rgba(0,0,0,0.25); }
    #tst-widget-panel {
      position: fixed; bottom: 92px; right: 24px; z-index: 9998;
      width: 380px; max-height: 560px; border-radius: 16px;
      background: #fff; box-shadow: 0 8px 40px rgba(0,0,0,0.18);
      display: flex; flex-direction: column; overflow: hidden;
      transform-origin: bottom right;
      transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), opacity 0.2s;
    }
    #tst-widget-panel.hidden { transform: scale(0.7); opacity: 0; pointer-events: none; }
    .tst-header {
      background: var(--tst-primary, #2563EB); color: white;
      padding: 14px 16px; display: flex; align-items: center; gap: 10px;
      font-family: -apple-system, sans-serif;
    }
    .tst-header-avatar { width: 32px; height: 32px; border-radius: 50%; background: rgba(255,255,255,0.3); display: flex; align-items: center; justify-content: center; font-size: 16px; }
    .tst-header-name { font-weight: 600; font-size: 14px; }
    .tst-header-status { font-size: 11px; opacity: 0.85; }
    .tst-close { margin-left: auto; background: none; border: none; color: white; cursor: pointer; opacity: 0.8; font-size: 18px; padding: 4px; }
    .tst-messages {
      flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px;
      font-family: -apple-system, sans-serif; font-size: 14px;
    }
    .tst-msg { display: flex; align-items: flex-end; gap: 8px; }
    .tst-msg.user { flex-direction: row-reverse; }
    .tst-bubble {
      max-width: 75%; padding: 10px 14px; border-radius: 16px; line-height: 1.5;
      word-break: break-word; white-space: pre-wrap;
    }
    .tst-msg.bot .tst-bubble { background: #f1f5f9; border-bottom-left-radius: 4px; }
    .tst-msg.user .tst-bubble { background: var(--tst-primary, #2563EB); color: white; border-bottom-right-radius: 4px; }
    .tst-cursor { display: inline-block; width: 2px; height: 14px; background: currentColor; animation: tst-blink 0.8s infinite; vertical-align: middle; margin-left: 2px; }
    @keyframes tst-blink { 0%,100%{opacity:1} 50%{opacity:0} }
    .tst-input-row {
      padding: 12px; border-top: 1px solid #e5e7eb; display: flex; gap: 8px; align-items: flex-end; background: #fff;
    }
    .tst-input {
      flex: 1; border: 1px solid #d1d5db; border-radius: 10px; padding: 8px 12px;
      font-size: 14px; font-family: inherit; resize: none; outline: none; min-height: 40px; max-height: 100px;
      transition: border-color 0.15s; line-height: 1.4;
    }
    .tst-input:focus { border-color: var(--tst-primary, #2563EB); }
    .tst-send {
      width: 36px; height: 36px; border-radius: 10px; border: none;
      background: var(--tst-primary, #2563EB); color: white; cursor: pointer;
      display: flex; align-items: center; justify-content: center; flex-shrink: 0;
    }
    .tst-send:disabled { opacity: 0.5; cursor: not-allowed; }
    .tst-footer { text-align: center; font-size: 11px; color: #9ca3af; padding: 4px 0 10px; font-family: sans-serif; }
    @media (max-width: 420px) {
      #tst-widget-panel { width: calc(100vw - 24px); right: 12px; bottom: 80px; }
    }
  `;
  document.head.appendChild(style);

  // ── DOM ───────────────────────────────────────────────────────────────────
  const btn = document.createElement("button");
  btn.id = "tst-widget-btn";
  btn.innerHTML = "💬";
  btn.setAttribute("aria-label", "Open chat");

  const panel = document.createElement("div");
  panel.id = "tst-widget-panel";
  panel.classList.add("hidden");
  panel.innerHTML = `
    <div class="tst-header">
      <div class="tst-header-avatar">🤖</div>
      <div>
        <div class="tst-header-name" id="tst-bot-name">Assistant</div>
        <div class="tst-header-status">● Online</div>
      </div>
      <button class="tst-close" aria-label="Close">✕</button>
    </div>
    <div class="tst-messages" id="tst-messages"></div>
    <div class="tst-input-row">
      <textarea class="tst-input" id="tst-input" rows="1" placeholder="Type a message..."></textarea>
      <button class="tst-send" id="tst-send">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
      </button>
    </div>
    <div class="tst-footer">Powered by TissaTech</div>
  `;

  document.body.appendChild(btn);
  document.body.appendChild(panel);

  // ── Load config ────────────────────────────────────────────────────────────
  async function loadConfig() {
    try {
      const res = await fetch(`${API_URL}/api/v1/widget/config`, {
        headers: { "X-API-Key": API_KEY },
      });
      if (res.ok) {
        config = await res.json();
        document.getElementById("tst-bot-name").textContent = config.bot_name;
        document.getElementById("tst-input").placeholder = config.placeholder_text ?? "Type a message...";
        document.documentElement.style.setProperty("--tst-primary", config.primary_color);
        showGreeting();
      }
    } catch (_) {
      showGreeting();
    }
  }

  function showGreeting() {
    appendMessage("bot", config.greeting_message);
  }

  // ── Toggle ─────────────────────────────────────────────────────────────────
  function toggle() {
    isOpen = !isOpen;
    panel.classList.toggle("hidden", !isOpen);
    btn.innerHTML = isOpen ? "✕" : "💬";
    if (isOpen) {
      document.getElementById("tst-input").focus();
    }
  }

  btn.addEventListener("click", toggle);
  panel.querySelector(".tst-close").addEventListener("click", toggle);

  // ── Messaging ──────────────────────────────────────────────────────────────
  function appendMessage(role, text) {
    const container = document.getElementById("tst-messages");
    const row = document.createElement("div");
    row.className = `tst-msg ${role}`;
    const bubble = document.createElement("div");
    bubble.className = "tst-bubble";
    bubble.textContent = text;
    row.appendChild(bubble);
    container.appendChild(row);
    container.scrollTop = container.scrollHeight;
    return bubble;
  }

  async function sendMessage() {
    const input = document.getElementById("tst-input");
    const text = input.value.trim();
    if (!text || isStreaming) return;

    input.value = "";
    input.style.height = "auto";
    appendMessage("user", text);

    isStreaming = true;
    const bubble = appendMessage("bot", "");
    const cursor = document.createElement("span");
    cursor.className = "tst-cursor";
    bubble.appendChild(cursor);

    try {
      const res = await fetch(`${API_URL}/api/v1/chat/message`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-API-Key": API_KEY,
        },
        body: JSON.stringify({
          message: text,
          conversation_id: conversationId,
          session_id: sessionId,
        }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let content = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.content) {
                content += data.content;
                bubble.textContent = content;
                bubble.appendChild(cursor);
                document.getElementById("tst-messages").scrollTop = 99999;
              }
              if (data.conversation_id) conversationId = data.conversation_id;
            } catch (_) {}
          }
        }
      }

      cursor.remove();
    } catch (_) {
      bubble.textContent = "Sorry, something went wrong. Please try again.";
      cursor.remove();
    } finally {
      isStreaming = false;
    }
  }

  document.getElementById("tst-send").addEventListener("click", sendMessage);
  document.getElementById("tst-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
    // Auto-resize
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 100) + "px";
  });

  function generateId() {
    return Math.random().toString(36).slice(2, 18);
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  loadConfig();
})();
