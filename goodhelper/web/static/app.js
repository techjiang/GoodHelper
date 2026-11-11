const messages = document.getElementById("messages");
const form = document.getElementById("composer");
const input = document.getElementById("input");
const brief = document.getElementById("brief");
const clock = document.getElementById("clock");

function bubble(role, text, intent) {
  const row = document.createElement("div");
  row.className = "row " + role;
  const body = document.createElement("div");
  body.className = "bubble";
  body.textContent = text;
  if (intent) {
    const tag = document.createElement("span");
    tag.className = "intent";
    tag.textContent = intent;
    body.appendChild(tag);
  }
  row.appendChild(body);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
  return row;
}

function alertBox(lines) {
  if (!lines || !lines.length) return;
  const box = document.createElement("div");
  box.className = "alert";
  box.textContent = "该动了：\n" + lines.join("\n");
  messages.appendChild(box);
  messages.scrollTop = messages.scrollHeight;
}

function renderBrief(board) {
  const today = board.today || [];
  const todos = board.todos || [];
  const items = [];
  for (const ev of today) items.push(`<li><span class="t">${ev.when.split(" ").slice(-1)[0]}</span><span>${escapeHtml(ev.title)}</span></li>`);
  for (const todo of todos.slice(0, 4)) items.push(`<li><span class="t">#${todo.id}</span><span>${escapeHtml(todo.content)}</span></li>`);
  brief.innerHTML = `<h2>今日</h2>` + (items.length ? `<ul class="brief-list">${items.join("")}</ul>` : `<p class="muted">今天空着。</p>`);
}

function escapeHtml(text) {
  return text.replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

async function send(text) {
  if (!text.trim()) return;
  bubble("user", text);
  input.value = "";
  const btn = form.querySelector("button");
  btn.disabled = true;
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    const data = await res.json();
    if (!res.ok) {
      bubble("bot", data.error || "出了点岔子。");
      return;
    }
    bubble("bot", data.text, `${data.intent} · ${data.latency_ms}ms`);
    alertBox(data.alerts);
    renderBrief(data.board);
  } catch (err) {
    bubble("bot", "连不上服务，看看终端里还在跑吗？");
  } finally {
    btn.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  send(input.value);
});

document.getElementById("chips").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-q]");
  if (btn) send(btn.dataset.q);
});

function tick() {
  const now = new Date();
  clock.textContent = `${now.getHours().toString().padStart(2, "0")}:${now.getMinutes().toString().padStart(2, "0")} · 本地 · 离线可用`;
}
tick();
setInterval(tick, 30000);

(async function boot() {
  try {
    const [board, history] = await Promise.all([
      fetch("/api/board").then((r) => r.json()),
      fetch("/api/history").then((r) => r.json()),
    ]);
    renderBrief(board);
    if (history.messages && history.messages.length) {
      for (const m of history.messages.slice(-20)) {
        bubble(m.role === "user" ? "user" : "bot", m.content, m.role === "user" ? "" : m.intent);
      }
    } else {
      bubble("bot", "我在。想记点什么、安排点什么，直接说就行。", "welcome");
    }
  } catch (err) {
    bubble("bot", "服务没起来？先在终端跑 goodhelper serve。");
  }
})();
