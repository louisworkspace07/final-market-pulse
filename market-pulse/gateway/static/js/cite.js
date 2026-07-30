/* ==========================================================================
   Market Pulse — cite.js  ·  S6: chip trích dẫn [N1]/[E2]/[CD-x]/[M-..] thành
   nút "Nguồn ▸" có popover bấm được (thay tooltip title mờ, không rõ là nút).
   --------------------------------------------------------------------------
   Không đổi cách các trang SINH chip (overview.js/macro.js/soitin.js/copilot.js
   vẫn tạo .evidence-chip với title=...). Ở đây chỉ NÂNG CẤP sau render:
   - chuyển title → data-src (giữ nội dung), thêm nhãn "Nguồn" + mũi tên ▸
   - click → popover hiện nguồn (tái dùng look .term-pop)
   MutationObserver để bắt chip render động.
   ========================================================================== */
(function () {
  "use strict";
  let pop = null;

  function ensurePop() {
    if (pop) return pop;
    pop = document.createElement("div");
    pop.className = "term-pop cite-pop"; pop.style.display = "none";
    document.body.appendChild(pop);
    return pop;
  }
  function show(target, text) {
    const p = ensurePop();
    p.innerHTML = `<b style="color:var(--primary)">Nguồn dẫn chứng</b>
      <div style="margin-top:4px">${text}</div>`;
    p.style.display = "block";
    const r = target.getBoundingClientRect();
    let left = r.left + window.scrollX;
    left = Math.min(left, window.scrollX + document.documentElement.clientWidth - 300);
    p.style.top = (r.bottom + window.scrollY + 6) + "px";
    p.style.left = Math.max(8, left) + "px";
  }
  function hide() { if (pop) pop.style.display = "none"; }

  // nâng cấp 1 chip: title → data-src, gắn nhãn Nguồn (bỏ qua chip .missing giữ cảnh báo)
  function upgrade(el) {
    if (el.dataset.citeReady) return;
    el.dataset.citeReady = "1";
    // Ảnh 14: ghi lại mã bằng chứng NGAY (trước khi chèn mũi tên) để click biết
    // cần nhảy tới dòng nào trong kho bằng chứng.
    const txt = el.textContent.trim().replace(/[▸\s\[\]]/g, "");
    if (/^(?:N|E|M|R-|TT-|CD-)[\w-]*$/.test(txt)) el.dataset.evId = txt;
    const isMissing = el.classList.contains("missing");
    const src = el.getAttribute("title");
    if (src && !isMissing) {
      el.dataset.src = src;
      el.removeAttribute("title");          // bỏ tooltip mặc định → dùng popover
      el.classList.add("cite-btn");
      el.setAttribute("role", "button");
      el.setAttribute("tabindex", "0");
      // thêm mũi tên gợi ý bấm nếu chip là mã trích dẫn ngắn (không phải câu dài)
      if (el.textContent.trim().length <= 10 && !el.querySelector(".cite-arw"))
        el.insertAdjacentHTML("beforeend", '<span class="cite-arw"> ▸</span>');
    }
  }

  function scan(root) {
    (root || document).querySelectorAll(".evidence-chip, .fact-ref").forEach(upgrade);
  }

  /* Ảnh 14 · Click chip → CUỘN XUỐNG kho bằng chứng và làm nổi đúng dòng, để từ
     đó người dùng bấm "Mở nguồn →" xem báo cáo gốc. Popover chỉ còn dùng khi
     trang KHÔNG có kho bằng chứng (vd trang cổ phiếu) hoặc khi hover xem nhanh. */
  function jumpToEvidence(el) {
    const id = (el.dataset.evId || el.textContent || "").replace(/[\[\]▸\s]/g, "").trim();
    if (!id) return false;
    const anchor = document.getElementById(
      (window._evAnchor ? window._evAnchor(id) : "ev-" + id.replace(/[^\w-]/g, "_")));
    if (!anchor) return false;
    // kho bằng chứng nằm trong <details> → mở ra trước khi cuộn, không thì vô hình
    const det = anchor.closest("details");
    if (det && !det.open) det.open = true;
    hide();
    anchor.scrollIntoView({ behavior: "smooth", block: "center" });
    anchor.classList.remove("ev-flash");
    void anchor.offsetWidth;                 // ép reflow để animation chạy lại
    anchor.classList.add("ev-flash");
    setTimeout(() => anchor.classList.remove("ev-flash"), 2100);
    return true;
  }

  // click / phím → ưu tiên nhảy xuống kho; không có kho thì popover như cũ
  document.addEventListener("click", (e) => {
    const el = e.target.closest && e.target.closest(".cite-btn");
    if (el) {
      e.stopPropagation();
      if (!jumpToEvidence(el) && el.dataset.src) show(el, el.dataset.src);
      return;
    }
    if (!e.target.closest || !e.target.closest(".cite-pop")) hide();
  });

  // hover = xem nhanh (không cuộn) — giữ trải nghiệm tra cứu tại chỗ
  let hoverT = null;
  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest && e.target.closest(".cite-btn");
    if (!el || !el.dataset.src) return;
    clearTimeout(hoverT);
    hoverT = setTimeout(() => show(el, el.dataset.src), 260);
  });
  document.addEventListener("mouseout", (e) => {
    if (e.target.closest && e.target.closest(".cite-btn")) clearTimeout(hoverT);
  });
  document.addEventListener("keydown", (e) => {
    if ((e.key === "Enter" || e.key === " ") && e.target.classList && e.target.classList.contains("cite-btn")) {
      e.preventDefault(); show(e.target, e.target.dataset.src || "");
    }
    if (e.key === "Escape") hide();
  });
  window.addEventListener("scroll", hide, { passive: true });

  let t = null;
  function schedule() { clearTimeout(t); t = setTimeout(() => scan(), 300); }
  function init() {
    scan();
    const main = document.querySelector("main") || document.body;
    new MutationObserver(muts => { for (const m of muts) if (m.addedNodes.length) { schedule(); break; } })
      .observe(main, { childList: true, subtree: true });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
  window.MPCite = { scan };
})();
