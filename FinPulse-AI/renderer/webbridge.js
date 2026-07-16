// Web-bridge (client side) — chỉ là lớp mỏng gọi qua IPC.
// Toàn bộ việc lái Gemini chạy trong MAIN process trên một CỬA SỔ THẬT
// (BrowserWindow), nên ít bị Google chặn hơn <webview>.
(function () {
  function setStatus(s) { const e = document.getElementById('webStatus'); if (e) e.textContent = s; }

  if (window.api && window.api.onAiwinStatus) {
    window.api.onAiwinStatus((s) => setStatus(s));
  }

  let busy = false;

  window.webBridge = {
    async send(prompt) {
      if (busy) throw new Error('Web bridge đang bận — đợi lượt trước.');
      busy = true;
      try {
        const r = await window.api.aiwinSend(prompt);
        if (!r.ok) throw new Error(r.error || 'unknown');
        return r.text;
      } finally {
        busy = false;
      }
    },
    openHome: () => window.api.aiwinShow(),
    reload: () => window.api.aiwinShow(),
    isBusy: () => busy
  };
})();
