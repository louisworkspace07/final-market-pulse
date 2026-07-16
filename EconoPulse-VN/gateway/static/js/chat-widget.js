/* ==========================================================================
   Ảnh 16 · chat-widget.js — Pulse Chat: bong bóng chat ở mọi trang.

   Điểm khác bản cũ (iframe EconoLens trong tab con trang Copilot):
   - Gọi thẳng API qua proxy /api/pchat/* → không iframe, không kẹt 1 trang.
   - CÓ LUỒNG ĐĂNG NHẬP NGAY TRONG PANEL: /api/chat của EconoLens có middleware
     auth, thiếu bước này widget mở ra là 401.
   - Gửi kèm NGỮ CẢNH TRANG (đang ở đâu, đang xem mã nào) để AI trả lời sát.
   ========================================================================== */
(function () {
  "use strict";

  const TOKEN_KEY = "pchat_token";
  const PERSONA_KEY = "pchat_persona";
  const PROVIDER_KEY = "pchat_provider";
  const $ = (s) => document.querySelector(s);

  const fab = $("#pchat-fab");
  if (!fab) return;                          // trang không nhúng widget

  const panel = $("#pchat-panel");
  const authBox = $("#pchat-auth");
  const authForm = $("#pchat-auth-form");
  const authErr = $("#pchat-auth-err");
  const msgs = $("#pchat-msgs");
  const form = $("#pchat-form");
  const textarea = $("#pchat-text");
  const personaSel = $("#pchat-persona");
  const logoutBtn = $("#pchat-logout");

  let token = localStorage.getItem(TOKEN_KEY) || "";
  let meta = null;
  let sending = false;
  let authMode = "login";
  let pendingMessage = null;                 // tin nhắn cần gửi lại sau khi đăng nhập

  /* ---------------- đóng/mở panel ---------------- */
  function open() {
    panel.classList.remove("closed");
    fab.classList.add("hidden");
    panel.setAttribute("aria-hidden", "false");
    setTimeout(() => (token ? textarea : authForm.querySelector("input"))?.focus(), 260);
    if (token && !meta) boot();
  }
  function close() {
    panel.classList.add("closed");
    fab.classList.remove("hidden");
    panel.setAttribute("aria-hidden", "true");
  }
  fab.addEventListener("click", open);
  $("#pchat-close").addEventListener("click", close);
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.classList.contains("closed")) close();
  });

  /* ---------------- gọi API qua proxy ---------------- */
  async function api(path, body, method) {
    const r = await fetch("/api/pchat/" + path, {
      method: method || (body ? "POST" : "GET"),
      headers: Object.assign({ "Content-Type": "application/json" },
        token ? { Authorization: "Bearer " + token } : {}),
      body: body ? JSON.stringify(body) : undefined,
    });
    let data = {};
    try { data = await r.json(); } catch (_) {}
    if (r.status === 401) { onUnauthorized(); throw new Error("__401__"); }
    if (!r.ok) throw new Error(data.error || `Lỗi ${r.status}`);
    return data;
  }

  /* Hết hạn giữa chừng: GIỮ NGUYÊN transcript, chỉ chèn form đăng nhập lại. */
  function onUnauthorized() {
    token = "";
    localStorage.removeItem(TOKEN_KEY);
    showAuth(msgs.children.length > 0);
  }

  /* ---------------- màn đăng nhập / đăng ký ---------------- */
  function showAuth(keepTranscript) {
    authBox.hidden = false;
    form.hidden = true;
    logoutBtn.hidden = true;
    personaSel.hidden = true;
    msgs.hidden = !keepTranscript;
    if (keepTranscript) {
      addSystemNote("Phiên đăng nhập đã hết hạn — đăng nhập lại để tiếp tục cuộc trò chuyện.");
    }
  }
  function showChat() {
    authBox.hidden = true;
    msgs.hidden = false;
    form.hidden = false;
    logoutBtn.hidden = false;
    personaSel.hidden = false;
  }

  document.querySelectorAll("[data-authtab]").forEach(b => b.addEventListener("click", () => {
    document.querySelectorAll("[data-authtab]").forEach(x => x.classList.remove("active"));
    b.classList.add("active");
    authMode = b.dataset.authtab;
    authForm.name.hidden = authMode !== "register";
    authForm.name.required = authMode === "register";
    authForm.password.autocomplete = authMode === "register" ? "new-password" : "current-password";
    authForm.querySelector(".pc-submit").textContent = authMode === "register" ? "Tạo tài khoản" : "Đăng nhập";
    authErr.hidden = true;
  }));

  authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    authErr.hidden = true;
    const btn = authForm.querySelector(".pc-submit");
    btn.disabled = true; btn.textContent = "Đang xử lý…";
    try {
      const body = { email: authForm.email.value.trim(), password: authForm.password.value };
      if (authMode === "register") body.name = authForm.name.value.trim();
      const d = await api(authMode, body);
      token = d.token;
      localStorage.setItem(TOKEN_KEY, token);
      authForm.reset();
      showChat();
      await boot();
      if (pendingMessage) { const m = pendingMessage; pendingMessage = null; send(m); }
    } catch (err) {
      if (err.message !== "__401__") { authErr.textContent = err.message; authErr.hidden = false; }
    } finally {
      btn.disabled = false;
      btn.textContent = authMode === "register" ? "Tạo tài khoản" : "Đăng nhập";
    }
  });

  logoutBtn.addEventListener("click", () => {
    token = ""; meta = null;
    localStorage.removeItem(TOKEN_KEY);
    msgs.innerHTML = "";
    showAuth(false);
  });

  /* ---------------- khởi tạo sau khi có token ---------------- */
  /* Chỉ dùng model ĐÃ CẤU HÌNH (`configured: true`). Trước đây lấy providers[0]
     nên rơi vào Claude chưa có API key → mọi câu hỏi đều báo lỗi thiếu key. */
  function configuredProviders() {
    return (meta?.providers || []).filter(p => p.configured);
  }
  function currentProvider() {
    const sel = document.querySelector("#pchat-provider");
    if (sel && sel.value) return sel.value;
    return configuredProviders()[0]?.id || "gemini_web";
  }

  async function boot() {
    try {
      meta = await api("meta");
      personaSel.innerHTML = (meta.personas || [])
        .map(p => `<option value="${p.id}">${p.name}</option>`).join("");
      const saved = localStorage.getItem(PERSONA_KEY);
      if (saved && [...personaSel.options].some(o => o.value === saved)) personaSel.value = saved;
      personaSel.addEventListener("change", () => localStorage.setItem(PERSONA_KEY, personaSel.value));

      // chọn model: chỉ liệt kê model đã có khoá/kênh sẵn sàng
      const ok = configuredProviders();
      const provSel = document.querySelector("#pchat-provider");
      if (provSel) {
        provSel.innerHTML = ok.map(p => `<option value="${p.id}">${p.name}</option>`).join("");
        const savedP = localStorage.getItem(PROVIDER_KEY);
        if (savedP && ok.some(p => p.id === savedP)) provSel.value = savedP;
        provSel.addEventListener("change", () => localStorage.setItem(PROVIDER_KEY, provSel.value));
        provSel.hidden = ok.length < 2;          // 1 model thì khỏi bày menu
      }
      showChat();
      if (!ok.length) {
        addSystemNote("Chưa có model AI nào được cấu hình. Thêm API key vào "
          + "AI Analyze Economic/.env (hoặc bật kênh Gemini Web) rồi khởi động lại.");
        return;
      }
      if (!msgs.children.length) greet();
    } catch (err) {
      if (err.message !== "__401__") addSystemNote(err.message);
    }
  }

  function greet() {
    const sym = window.MP_SYMBOL;
    addSystemNote(sym
      ? `Bạn đang xem mã ${sym}. Hỏi mình bất cứ điều gì về mã này hoặc thị trường.`
      : "Hỏi mình về chỉ số, ngành, cách đọc số liệu — hoặc về chính cách Market Pulse tính toán.");
  }

  /* ---------------- khung hội thoại ---------------- */
  function addSystemNote(text) {
    msgs.insertAdjacentHTML("beforeend",
      `<div class="pc-note-row">${PulseChatBlocks.esc(text)}</div>`);
    scrollDown();
  }
  function addUser(text) {
    msgs.insertAdjacentHTML("beforeend",
      `<div class="pc-msg pc-user">${PulseChatBlocks.esc(text)}</div>`);
    scrollDown();
  }
  function addTyping() {
    const el = document.createElement("div");
    el.className = "pc-msg pc-ai pc-typing";
    el.innerHTML = "<span></span><span></span><span></span>";
    msgs.appendChild(el); scrollDown();
    return el;
  }
  function scrollDown() { msgs.scrollTop = msgs.scrollHeight; }

  /* Ngữ cảnh trang: AI biết người dùng đang đứng ở đâu để trả lời sát màn hình. */
  function pageContext() {
    const bits = [`trang: ${location.pathname}`];
    if (window.MP_SYMBOL) bits.push(`đang xem mã: ${window.MP_SYMBOL}`);
    bits.push(document.body.classList.contains("mode-basic")
      ? "chế độ: Cơ bản (người mới, giải thích dễ hiểu, hạn chế thuật ngữ)"
      : "chế độ: Chuyên sâu (có thể dùng thuật ngữ và số liệu chi tiết)");
    return bits.join(" · ");
  }

  async function send(text) {
    if (sending || !text.trim()) return;
    if (!token) { pendingMessage = text; showAuth(false); return; }
    sending = true;
    addUser(text);
    const typing = addTyping();
    try {
      const d = await api("chat", {
        message: `[Ngữ cảnh: ${pageContext()}]\n\n${text}`,
        persona: personaSel.value || "investor",
        provider: currentProvider(),
      });
      typing.remove();
      const holder = document.createElement("div");
      holder.className = "pc-msg pc-ai";
      msgs.appendChild(holder);
      await PulseChatBlocks.renderBlocks(holder, d.response?.blocks, { onGrow: scrollDown });
      scrollDown();
    } catch (err) {
      typing.remove();
      if (err.message !== "__401__") {
        msgs.insertAdjacentHTML("beforeend",
          `<div class="pc-msg pc-ai pc-error">${PulseChatBlocks.esc(err.message)}</div>`);
        scrollDown();
      } else {
        pendingMessage = text;      // đăng nhập lại xong sẽ tự gửi tiếp
      }
    } finally {
      sending = false;
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const t = textarea.value;
    textarea.value = ""; textarea.style.height = "auto";
    send(t);
  });
  textarea.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
  textarea.addEventListener("input", () => {           // ô nhập tự cao dần
    textarea.style.height = "auto";
    textarea.style.height = Math.min(textarea.scrollHeight, 110) + "px";
  });

  // câu hỏi gợi ý từ block suggestions → bấm là hỏi luôn
  msgs.addEventListener("click", (e) => {
    const s = e.target.closest(".pcb-sugg-btn");
    if (s) { send(s.textContent); return; }
    const opt = e.target.closest(".pcb-q-opt");
    if (opt) {
      const quiz = opt.closest(".pcb-quiz");
      const right = Number(quiz.dataset.answer);
      quiz.querySelectorAll(".pcb-q-opt").forEach((b, i) => {
        b.disabled = true;
        if (i === right) b.classList.add("correct");
        else if (b === opt) b.classList.add("wrong");
      });
      const exp = quiz.querySelector(".pcb-q-exp");
      if (exp) exp.hidden = false;
      scrollDown();
    }
  });

  if (token) boot(); else showAuth(false);
})();
