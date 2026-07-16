/* ==========================================================================
   Market Pulse — shell-v3.js  ·  hành vi header ngang + ticker + mode toggle
   --------------------------------------------------------------------------
   Nạp SAU shell.js (giữ ⌘K + theme của shell.js). Ở đây chỉ lo phần shell mới:
   dropdown Công cụ/Nâng cao, hamburger mobile, dải ticker marquee (board),
   và toggle Cơ bản/Chuyên sâu (S3, class body.mode-basic + localStorage).
   ========================================================================== */
(function () {
  "use strict";

  /* --- dropdown menu header --- */
  document.querySelectorAll(".mp-drop[data-drop]").forEach(drop => {
    const btn = drop.querySelector("button");
    if (!btn) return;
    btn.addEventListener("click", e => {
      e.stopPropagation();
      const wasOpen = drop.classList.contains("open");
      document.querySelectorAll(".mp-drop.open").forEach(d => d.classList.remove("open"));
      if (!wasOpen) drop.classList.add("open");
    });
  });
  document.addEventListener("click", () =>
    document.querySelectorAll(".mp-drop.open").forEach(d => d.classList.remove("open")));

  /* --- hamburger mobile --- */
  const ham = document.getElementById("mp-hamburger");
  const menu = document.getElementById("mp-menu");
  if (ham && menu) ham.addEventListener("click", () => menu.classList.toggle("mobile-open"));

  /* --- toggle Cơ bản / Chuyên sâu (S3) --- MẶC ĐỊNH Cơ bản cho F0 --- */
  const MODE_KEY = "mp_mode";               // "basic" | "advanced"
  if (localStorage.getItem(MODE_KEY) !== "advanced") document.body.classList.add("mode-basic");
  window.mpSetMode = function (mode) {
    const basic = mode === "basic";
    document.body.classList.toggle("mode-basic", basic);
    localStorage.setItem(MODE_KEY, basic ? "basic" : "advanced");
    document.querySelectorAll(".mode-toggle button").forEach(b =>
      b.classList.toggle("active", b.dataset.mode === mode));
    window.dispatchEvent(new CustomEvent("mp:mode", { detail: mode }));
  };
  // đồng bộ nút toggle nếu trang có
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest(".mode-toggle button");
    if (b && b.dataset.mode) window.mpSetMode(b.dataset.mode);
  });
  // set trạng thái ban đầu cho mọi nút toggle có sẵn
  document.addEventListener("DOMContentLoaded", () => {
    const cur = document.body.classList.contains("mode-basic") ? "basic" : "advanced";
    document.querySelectorAll(".mode-toggle button").forEach(b =>
      b.classList.toggle("active", b.dataset.mode === cur));
  });

  /* --- ticker strip (R1): KHÔNG tự fetch bảng giá nữa — ăn theo nhịp chung của
     LivePoll (/api/live đã xếp sẵn top thanh khoản + %phiên cho từng mã). --- */
  let _vnIndexBase = null;
  function paintTicker(d) {
    const track = document.getElementById("mp-ticker-track");
    if (!track) return;
    const items = [];
    if (_vnIndexBase != null) items.push(tick("VN-INDEX", _vnIndexBase, null));
    (d?.ticker || []).forEach(r => items.push(tick(r.symbol, r.price, r.chg_pct)));
    if (!items.length) {
      track.innerHTML = `<span class="mp-tick"><span class="tk-name">Bảng giá chưa sẵn sàng — mở trong giờ giao dịch</span></span>`;
      return;
    }
    track.innerHTML = items.join("") + items.join("");   // nhân đôi cho marquee liền mạch
  }
  function tick(name, price, pct) {
    // Ảnh 6: màu giá theo chiều biến động (trước đây pct=null nên toàn xanh dương).
    const cls = pct == null ? "" : pct > 0 ? "chg-up" : pct < 0 ? "chg-down" : "chg-ref";
    const arw = pct == null ? "" : pct > 0 ? "▲" : pct < 0 ? "▼" : "";
    // Ảnh 15: giá cổ phiếu = đồng, không lẻ; chỉ số 2 lẻ.
    const p = price == null ? "" : (name === "VN-INDEX" ? fmtIndex(price) : fmtPrice(price));
    const pctTxt = pct == null ? "" : ` <span class="${cls}">${arw}${fmtVN(Math.abs(pct), 2)}%</span>`;
    return `<a class="mp-tick" href="/co-phieu/${encodeURIComponent(name)}" style="text-decoration:none">
      <span class="tk-name">${name}</span><span class="tk-price ${cls}">${p}</span>${pctTxt}</a>`;
  }
  if (document.getElementById("mp-ticker")) {
    fetch("/api/data/market_range").then(r => r.json())
      .then(mr => { if (mr?.available && mr.base != null) _vnIndexBase = mr.base; })
      .catch(() => {})
      .finally(() => LivePoll.on(paintTicker));
  }
})();
