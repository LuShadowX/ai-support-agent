/*
 * Embeddable chat widget. Add to any website with one line:
 *   <script src="https://YOUR-SERVER/static/widget.js" data-color="#2f5d50" defer></script>
 * Optional attributes: data-api (server URL, defaults to where this script is hosted), data-color.
 * Uses Shadow DOM so the host site's CSS can't break it (and it can't break theirs).
 */
(function () {
  "use strict";
  const script = document.currentScript;
  const API = (script.dataset.api || new URL(script.src).origin).replace(/\/$/, "");
  const COLOR = script.dataset.color || "#2f5d50";
  const STORAGE_KEY = "support-agent-session";

  const host = document.createElement("div");
  host.id = "support-agent-widget";
  document.body.appendChild(host);
  const root = host.attachShadow({ mode: "open" });

  root.innerHTML = `
    <style>
      :host { --c: ${COLOR}; all: initial; font-family: system-ui, -apple-system, "Segoe UI", sans-serif; }
      * { box-sizing: border-box; }
      .launcher { position: fixed; right: 24px; bottom: 24px; width: 60px; height: 60px; border-radius: 50%;
        border: 0; background: var(--c); color: #fff; cursor: pointer; box-shadow: 0 8px 24px rgba(0,0,0,.2);
        display: grid; place-items: center; z-index: 2147483000; transition: transform .15s; }
      .launcher:hover { transform: scale(1.06); }
      .launcher svg { width: 28px; height: 28px; }
      .panel { position: fixed; right: 24px; bottom: 96px; width: 380px; height: 580px; max-height: calc(100vh - 120px);
        background: #fff; border-radius: 16px; box-shadow: 0 16px 48px rgba(0,0,0,.22); display: none;
        flex-direction: column; overflow: hidden; z-index: 2147483000; }
      .panel.open { display: flex; }
      .header { background: var(--c); color: #fff; padding: 16px 18px; display: flex; align-items: center; gap: 10px; }
      .header .dot { width: 10px; height: 10px; border-radius: 50%; background: #5ee29a; }
      .header .title { font-weight: 600; font-size: 15px; }
      .header .sub { font-size: 12px; opacity: .85; }
      .header .close { margin-left: auto; background: none; border: 0; color: #fff; font-size: 22px; cursor: pointer; line-height: 1; }
      .messages { flex: 1; overflow-y: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; background: #f7f8f7; }
      .msg { max-width: 85%; padding: 10px 14px; border-radius: 14px; font-size: 14px; line-height: 1.45; color: #1d1d1d; word-wrap: break-word; }
      .msg.bot { background: #fff; border: 1px solid #e6e8e6; align-self: flex-start; border-bottom-left-radius: 4px; }
      .msg.user { background: var(--c); color: #fff; align-self: flex-end; border-bottom-right-radius: 4px; }
      .msg p { margin: 0 0 6px; } .msg p:last-child { margin: 0; }
      .msg ul { margin: 4px 0; padding-left: 18px; }
      .msg a { color: inherit; }
      .sources { font-size: 11px; color: #6b716e; margin-top: 6px; }
      .typing { display: flex; gap: 4px; padding: 14px; }
      .typing span { width: 7px; height: 7px; border-radius: 50%; background: #a5aba8; animation: b 1.2s infinite; }
      .typing span:nth-child(2) { animation-delay: .15s; } .typing span:nth-child(3) { animation-delay: .3s; }
      @keyframes b { 0%, 60%, 100% { transform: translateY(0); opacity: .5; } 30% { transform: translateY(-5px); opacity: 1; } }
      form { display: flex; gap: 8px; padding: 12px; border-top: 1px solid #e6e8e6; background: #fff; }
      input { flex: 1; border: 1px solid #d5d9d6; border-radius: 22px; padding: 10px 16px; font: inherit; font-size: 14px; outline: none; }
      input:focus { border-color: var(--c); }
      .send { border: 0; background: var(--c); color: #fff; border-radius: 50%; width: 40px; height: 40px; cursor: pointer; display: grid; place-items: center; }
      .send:disabled { opacity: .5; cursor: default; }
      .footer { text-align: center; font-size: 10px; color: #9aa09d; padding: 0 0 8px; background: #fff; }
      @media (max-width: 480px) {
        .panel { right: 0; bottom: 0; width: 100vw; height: 100vh; max-height: none; border-radius: 0; }
      }
    </style>
    <button class="launcher" aria-label="Open chat">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
    </button>
    <div class="panel" role="dialog" aria-label="Chat">
      <div class="header">
        <span class="dot"></span>
        <div><div class="title">Assistant</div><div class="sub">Typically replies instantly</div></div>
        <button class="close" aria-label="Close chat">&times;</button>
      </div>
      <div class="messages" aria-live="polite"></div>
      <form>
        <input type="text" placeholder="Type your message..." maxlength="2000" autocomplete="off" aria-label="Message" />
        <button class="send" type="submit" aria-label="Send">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 2 11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
        </button>
      </form>
      <div class="footer">AI assistant · may make mistakes</div>
    </div>`;

  const $ = (sel) => root.querySelector(sel);
  const panel = $(".panel"), list = $(".messages"), form = $("form"), input = $("input"), sendBtn = $(".send");
  let sessionId = null, greeted = false, busy = false;
  try { sessionId = localStorage.getItem(STORAGE_KEY); } catch (_) {}

  // Minimal, safe markdown: escape everything first, then allow **bold**, links, bullet lists, paragraphs.
  function render(text) {
    const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const inline = (s) => s
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    const bullet = /^\s*[-*•]\s+/;
    return esc.split(/\n{2,}/).map((block) => {
      let html = "", text = [], items = [];
      const flushText = () => { if (text.length) { html += "<p>" + text.map(inline).join("<br>") + "</p>"; text = []; } };
      const flushList = () => { if (items.length) { html += "<ul>" + items.map((i) => "<li>" + inline(i) + "</li>").join("") + "</ul>"; items = []; } };
      for (const line of block.split("\n")) {
        if (bullet.test(line)) { flushText(); items.push(line.replace(bullet, "")); }
        else { flushList(); text.push(line); }
      }
      flushText(); flushList();
      return html;
    }).join("");
  }

  function add(role, text, sources) {
    const el = document.createElement("div");
    el.className = "msg " + role;
    el.innerHTML = role === "bot" ? render(text) : render(text).replace(/<\/?(strong|a)[^>]*>/g, "");
    if (sources && sources.length) {
      const s = document.createElement("div");
      s.className = "sources";
      s.textContent = "Sources: " + sources.join(", ");
      el.appendChild(s);
    }
    list.appendChild(el);
    list.scrollTop = list.scrollHeight;
  }

  function typing(on) {
    const existing = $(".typing");
    if (on && !existing) {
      const el = document.createElement("div");
      el.className = "msg bot typing";
      el.innerHTML = "<span></span><span></span><span></span>";
      list.appendChild(el);
      list.scrollTop = list.scrollHeight;
    } else if (!on && existing) existing.remove();
  }

  async function loadConfig() {
    try {
      const cfg = await (await fetch(API + "/api/config")).json();
      $(".title").textContent = cfg.bot_name;
      if (!greeted) { add("bot", cfg.greeting); greeted = true; }
    } catch (_) {
      if (!greeted) { add("bot", "Hi! How can I help you today?"); greeted = true; }
    }
  }

  async function send(text) {
    busy = true; sendBtn.disabled = true;
    add("user", text);
    typing(true);
    try {
      const res = await fetch(API + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, session_id: sessionId }),
      });
      const data = await res.json();
      typing(false);
      if (!res.ok) { add("bot", typeof data.detail === "string" ? data.detail : "Sorry, something went wrong."); return; }
      sessionId = data.session_id;
      try { localStorage.setItem(STORAGE_KEY, sessionId); } catch (_) {}
      add("bot", data.reply, data.sources);
    } catch (_) {
      typing(false);
      add("bot", "I can't reach the server right now. Please check your connection and try again.");
    } finally {
      busy = false; sendBtn.disabled = false; input.focus();
    }
  }

  $(".launcher").addEventListener("click", () => {
    panel.classList.toggle("open");
    if (panel.classList.contains("open")) { if (!greeted) loadConfig(); input.focus(); }
  });
  $(".close").addEventListener("click", () => panel.classList.remove("open"));
  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || busy) return;
    input.value = "";
    send(text);
  });
})();
