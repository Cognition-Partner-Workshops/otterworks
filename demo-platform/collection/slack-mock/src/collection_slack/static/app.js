"use strict";
// All user and Devin text is rendered with textContent; nothing is inserted as HTML.
(() => {
  const state = { users: {}, channels: [], channel: null, thread: null, lastId: 0, max: 4000, mode: "stub", fake: false };
  const $ = (id) => document.getElementById(id);
  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  const uuid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + "-" + Math.random().toString(16).slice(2));

  async function api(path, body) {
    const opts = body === undefined ? {} : {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Collection-Client": "1" },
      body: JSON.stringify(body),
    };
    const res = await fetch(path, { credentials: "same-origin", ...opts });
    if (res.status === 401) { location.href = "/login"; throw new Error("login"); }
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || res.statusText);
    return data;
  }

  function initials(name) {
    return name.split(/\s+/).map((p) => p[0] || "").join("").slice(0, 2).toUpperCase();
  }
  function avatar(handle) {
    const u = state.users[handle] || { name: handle, color: "#6b7280" };
    const a = el("div", "avatar" + (u.bot ? " bot" : ""), handle === "system" ? "i" : initials(u.name));
    a.style.background = handle === "system" ? "#9ca3af" : u.color;
    return a;
  }
  function fmtTime(t) { return new Date(t * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }

  function messageNode(m) {
    const row = el("div", "message " + m.kind);
    row.dataset.id = String(m.id);
    row.dataset.fs = m.forward_state || "";
    row.appendChild(avatar(m.kind === "system" ? "system" : m.author));
    const body = el("div", "message-body");
    const meta = el("div", "meta");
    const name = m.kind === "system" ? "Workspace" : (state.users[m.author] || { name: m.author }).name;
    meta.appendChild(el("span", "author", name));
    if (m.kind === "devin") meta.appendChild(el("span", "tag", "BOT"));
    meta.appendChild(el("span", "time muted", fmtTime(m.created_at)));
    if (m.forward_state === "failed") meta.appendChild(el("span", "tag warn", "not delivered"));
    body.appendChild(meta);
    body.appendChild(el("div", "text", m.body));
    row.appendChild(body);
    return row;
  }

  function renderChannels() {
    const nav = $("channels");
    nav.replaceChildren();
    for (const c of state.channels) {
      const b = el("button", "channel-link" + (state.channel && c.id === state.channel.id ? " active" : ""), "# " + c.name);
      b.type = "button";
      b.addEventListener("click", () => selectChannel(c));
      nav.appendChild(b);
    }
  }

  async function selectChannel(c) {
    state.channel = c;
    $("channel-name").textContent = "# " + c.name;
    $("channel-topic").textContent = c.topic;
    renderChannels();
    closeThread();
    await refreshThreads();
  }

  async function refreshThreads() {
    if (!state.channel) return;
    const data = await api(`/api/channels/${state.channel.id}/threads`);
    const box = $("threads");
    box.replaceChildren();
    if (!data.threads.length) box.appendChild(el("p", "muted empty", "No threads yet. Start one below."));
    for (const t of data.threads) {
      if (!t.root) continue;
      const card = el("div", "thread-card" + (state.thread === t.id ? " active" : ""));
      card.appendChild(messageNode(t.root));
      const foot = el("div", "thread-foot");
      const open = el("button", "link", t.replies ? `${t.replies} repl${t.replies === 1 ? "y" : "ies"}` : "Reply");
      open.type = "button";
      open.addEventListener("click", () => openThread(t.id));
      foot.appendChild(open);
      if (t.session_state) foot.appendChild(el("span", "badge " + t.session_state, sessionLabel(t.session_state)));
      card.appendChild(foot);
      box.appendChild(card);
    }
  }

  function sessionLabel(s) {
    if (state.mode !== "live") return "stub";
    if (state.fake) return "FAKE v3 session: " + s;
    return { active: "Devin session live", creating: "starting Devin", verifying: "verifying", rejected: "rejected",
      failed: "failed", interrupted: "interrupted" }[s] || s;
  }

  async function openThread(id) {
    state.thread = id;
    state.lastId = 0;
    $("thread-messages").replaceChildren();
    $("thread-pane").hidden = false;
    await refreshThread();
    refreshThreads();
  }
  function closeThread() { state.thread = null; $("thread-pane").hidden = true; }

  async function refreshThread() {
    if (!state.thread) return;
    const id = state.thread;
    const box = $("thread-messages");
    const pending = [...box.querySelectorAll('[data-fs="pending"]')].map((n) => Number(n.dataset.id));
    const after = pending.length ? Math.min(state.lastId, Math.min(...pending) - 1) : state.lastId;
    const data = await api(`/api/threads/${id}?after=${after}`);
    if (id !== state.thread) return;
    let added = false;
    for (const m of data.messages) {
      const old = box.querySelector(`[data-id="${m.id}"]`);
      if (old) {
        if (old.dataset.fs !== (m.forward_state || "")) old.replaceWith(messageNode(m));
        continue;
      }
      box.appendChild(messageNode(m));
      added = true;
      state.lastId = Math.max(state.lastId, m.id);
    }
    if (added) box.scrollTop = box.scrollHeight;
    const badge = $("session-badge");
    badge.replaceChildren();
    if (data.session) {
      badge.className = "badge " + data.session.state;
      if (data.session.url && data.session.state === "active") {
        const a = el("a", "", sessionLabel(data.session.state));
        if (/^https:\/\//.test(data.session.url)) { a.href = data.session.url; a.target = "_blank"; a.rel = "noopener noreferrer"; }
        badge.appendChild(a);
      } else {
        badge.textContent = sessionLabel(data.session.state) + (data.session.detail ? ` (${data.session.detail})` : "");
      }
    } else { badge.className = "badge"; }
  }

  function bindComposer(formId, textId, countId, post, after) {
    const text = $(textId);
    const count = $(countId);
    const btn = $(formId).querySelector("button");
    let inflight = false;
    let error = "";
    const update = () => {
      const over = text.value.length > state.max;
      count.textContent = error || `${text.value.length}/${state.max}` + (over ? " - too long to send" : "");
      count.classList.toggle("warn", over || Boolean(error));
      btn.disabled = over || inflight;
    };
    text.addEventListener("input", () => { error = ""; update(); });
    text.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $(formId).requestSubmit(); } });
    $(formId).addEventListener("submit", async (e) => {
      e.preventDefault();
      const value = text.value.trim();
      if (inflight || !value || value.length > state.max) return;
      inflight = true;
      error = "";
      update();
      let result;
      try {
        result = await post(value);
      } catch (err) {
        error = `Not sent: ${err.message}`;
        return;
      } finally {
        inflight = false;
        update();
      }
      // Committed: never offer a repost. A failed refresh is recovered by the periodic poll.
      if (text.value.trim() === value) { text.value = ""; update(); }
      try { await after(result); } catch (err) { console.warn("refresh after send failed", err); }
    });
    update();
  }

  function persona() { return $("persona").value; }

  async function boot() {
    const data = await api("/api/bootstrap");
    state.mode = data.mode;
    state.fake = data.api_target === "fake-loopback";
    state.max = data.max_message_chars;
    for (const u of data.users) state.users[u.handle] = u;
    state.channels = data.channels;
    const banner = $("mode-banner");
    if (state.fake) {
      banner.hidden = false;
      banner.textContent = "FAKE v3 API on loopback: sessions and Devin replies are test doubles, not real Devin sessions.";
    } else if (data.mode !== "live") {
      banner.hidden = false;
      banner.textContent = "STUB MODE: not connected to the Devin API. Mentions get a labelled stub reply; no session is created.";
    }
    const sel = $("persona");
    const humans = data.users.filter((u) => !u.bot);
    for (const u of humans) { const o = el("option", "", u.name); o.value = u.handle; sel.appendChild(o); }
    const saved = localStorage.getItem("collection-persona");
    if (saved && humans.some((u) => u.handle === saved)) sel.value = saved;
    const preview = () => { $("persona-preview").replaceChildren(avatar(persona()), el("span", "", state.users[persona()].name)); };
    sel.addEventListener("change", () => { localStorage.setItem("collection-persona", persona()); preview(); });
    preview();
    $("close-thread").addEventListener("click", () => { closeThread(); refreshThreads(); });
    bindComposer("new-thread", "new-thread-text", "new-thread-count", async (value) => {
      return api(`/api/channels/${state.channel.id}/threads`, { author: persona(), text: value, client_msg_id: uuid() });
    }, async (r) => {
      await refreshThreads();
      await openThread(r.thread_id);
    });
    bindComposer("reply", "reply-text", "reply-count", async (value) => {
      return api(`/api/threads/${state.thread}/messages`, { author: persona(), text: value, client_msg_id: uuid() });
    }, refreshThread);
    await selectChannel(state.channels[0]);
    setInterval(() => { refreshThread().catch(() => {}); }, 1500);
    setInterval(() => { refreshThreads().catch(() => {}); }, 4000);
  }
  document.addEventListener("DOMContentLoaded", () => { boot().catch((e) => console.error(e)); });
})();
