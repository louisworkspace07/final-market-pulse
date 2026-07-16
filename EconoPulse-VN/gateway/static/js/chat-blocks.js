/* ==========================================================================
   Ảnh 16 · chat-blocks.js — dựng giao diện từ schema blocks[] của EconoLens.

   Cố ý KHÔNG tái dùng CSS của EconoLens: widget này sống trong Market Pulse nên
   phải theo token style-v3 (nền, viền, màu tăng/giảm, bo góc) để không lạc lõng.

   NÓI THẬT VỀ "STREAM": EconoLens trả full JSON 1 lần (không SSE), nên hiệu ứng
   ở đây là STAGGER RENDER — nhận xong thì gắn từng block vào DOM cách nhau 40ms
   kèm fade-up. Cảm giác mượt tương đương, nhưng không phải token-streaming.
   ========================================================================== */
(function (global) {
  "use strict";

  const esc = (s) => String(s == null ? "" : s)
    .replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* Markdown tối giản: đậm, nghiêng, code, link, xuống dòng, gạch đầu dòng.
     Escape TRƯỚC rồi mới dựng thẻ → nội dung AI không chèn được HTML. */
  function md(src) {
    let t = esc(src || "");
    t = t.replace(/`([^`]+)`/g, '<code>$1</code>');
    t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    t = t.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<i>$2</i>");
    t = t.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener">$1</a>');
    const lines = t.split("\n");
    let html = "", inList = false;
    for (const ln of lines) {
      const m = ln.match(/^\s*[-*]\s+(.*)$/);
      if (m) {
        if (!inList) { html += "<ul>"; inList = true; }
        html += `<li>${m[1]}</li>`;
      } else {
        if (inList) { html += "</ul>"; inList = false; }
        if (ln.trim()) html += `<p>${ln}</p>`;
      }
    }
    if (inList) html += "</ul>";
    return html;
  }

  const trendCls = (t) => t === "up" ? "num-up" : t === "down" ? "num-down" : "num-ref";

  /* ---- từng loại block → 1 phần tử DOM ---- */
  const RENDER = {
    heading: (b) => `<h4 class="pcb-h">${esc(b.text)}</h4>`,

    text: (b) => `<div class="pcb-text">${md(b.markdown || b.text)}</div>`,

    metrics: (b) => `<div class="pcb-metrics">${(b.items || []).map(m => `
      <div class="pcb-metric">
        <div class="pcb-m-label">${esc(m.label)}</div>
        <div class="pcb-m-value" data-countup="${esc(m.value)}">${esc(m.value)}</div>
        ${m.change ? `<div class="pcb-m-chg ${trendCls(m.trend)}">${esc(m.change)}</div>` : ""}
      </div>`).join("")}</div>`,

    table: (b) => `<div class="pcb-block">
      ${b.title ? `<div class="pcb-cap">${esc(b.title)}</div>` : ""}
      <div class="pcb-tablewrap"><table class="pcb-table">
        <thead><tr>${(b.headers || []).map(h => `<th>${esc(h)}</th>`).join("")}</tr></thead>
        <tbody>${(b.rows || []).map(r =>
          `<tr>${(r || []).map(c => `<td>${esc(c)}</td>`).join("")}</tr>`).join("")}</tbody>
      </table></div></div>`,

    callout: (b) => `<div class="pcb-callout pcb-${esc(b.style || "info")}">
      ${b.title ? `<div class="pcb-co-title">${esc(b.title)}</div>` : ""}
      <div>${md(b.markdown || b.text)}</div></div>`,

    comparison: (b) => `<div class="pcb-block">
      ${b.title ? `<div class="pcb-cap">${esc(b.title)}</div>` : ""}
      <div class="pcb-cmp">
        ${["left", "right"].map(side => {
          const s = b[side] || {};
          return `<div class="pcb-cmp-col">
            <div class="pcb-cmp-h">${esc(s.title || "")}</div>
            <ul>${(s.points || []).map(p => `<li>${esc(p)}</li>`).join("")}</ul></div>`;
        }).join("")}
      </div></div>`,

    timeline: (b) => `<div class="pcb-block">
      ${b.title ? `<div class="pcb-cap">${esc(b.title)}</div>` : ""}
      <div class="pcb-timeline">${(b.events || []).map(e => `
        <div class="pcb-tl-item">
          <div class="pcb-tl-date">${esc(e.date)}</div>
          <div><b>${esc(e.title)}</b>${e.description ? `<div class="pcb-tl-desc">${esc(e.description)}</div>` : ""}</div>
        </div>`).join("")}</div></div>`,

    quiz: (b) => {
      const id = "q" + Math.random().toString(36).slice(2, 8);
      return `<div class="pcb-quiz" data-answer="${Number(b.answerIndex) || 0}" data-id="${id}">
        <div class="pcb-q-text">${esc(b.question)}</div>
        <div class="pcb-q-opts">${(b.options || []).map((o, i) =>
          `<button type="button" class="pcb-q-opt" data-i="${i}">${esc(o)}</button>`).join("")}</div>
        <div class="pcb-q-exp" hidden>${esc(b.explanation || "")}</div></div>`;
    },

    suggestions: (b) => `<div class="pcb-sugg">${(b.items || []).map(s =>
      `<button type="button" class="pcb-sugg-btn">${esc(s)}</button>`).join("")}</div>`,

    /* chart: dùng chính engine của app (charts-v3) để đồng bộ màu/định dạng số */
    chart: (b) => `<div class="pcb-block">
      ${b.title ? `<div class="pcb-cap">${esc(b.title)}</div>` : ""}
      <div class="pcb-chart" data-chart='${esc(JSON.stringify({
        chartType: b.chartType, labels: b.labels, datasets: b.datasets }))}'></div></div>`,
  };

  /* Vẽ chart sau khi block đã vào DOM (cần biết bề rộng thật). */
  function hydrateChart(el) {
    let cfg;
    try { cfg = JSON.parse(el.dataset.chart.replace(/&quot;/g, '"').replace(/&amp;/g, "&")); }
    catch { return; }
    const M = global.MPChart;
    const ds = (cfg.datasets || [])[0] || {};
    const data = (cfg.labels || []).map((l, i) => ({ label: l, value: Number(ds.data?.[i]) }));
    if (!data.length || !M) { el.innerHTML = '<div class="pcb-note">Không vẽ được biểu đồ.</div>'; return; }
    try {
      if (/pie|doughnut/.test(cfg.chartType) && M.svgDonut) M.svgDonut(el, data, { height: 160 });
      else if (M.svgBars) M.svgBars(el, data, { height: 160 });
      else el.innerHTML = '<div class="pcb-note">Biểu đồ chưa hỗ trợ loại này.</div>';
    } catch (_) {
      el.innerHTML = '<div class="pcb-note">Không vẽ được biểu đồ.</div>';
    }
  }

  /* Đếm số tăng dần cho block metrics (chỉ khi giá trị bắt đầu bằng số). */
  function countUp(el) {
    const raw = el.dataset.countup || "";
    const m = raw.match(/^-?[\d.,]+/);
    if (!m) return;
    const target = parseFloat(m[0].replace(/\./g, "").replace(",", "."));
    if (!isFinite(target)) return;
    const suffix = raw.slice(m[0].length);
    const t0 = performance.now(), dur = 420;
    const step = (t) => {
      const p = Math.min(1, (t - t0) / dur);
      const v = target * (1 - Math.pow(1 - p, 3));      // ease-out
      el.textContent = v.toLocaleString("vi-VN", { maximumFractionDigits: 2 }) + suffix;
      if (p < 1) requestAnimationFrame(step); else el.textContent = raw;
    };
    requestAnimationFrame(step);
  }

  /**
   * Gắn danh sách block vào host, LẦN LƯỢT (stagger) cho mượt.
   * @returns {Promise<void>} resolve khi block cuối đã vào DOM.
   */
  function renderBlocks(host, blocks, opts) {
    opts = opts || {};
    const reduce = global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const gap = reduce ? 0 : (opts.stagger != null ? opts.stagger : 40);
    const list = (blocks || []).filter(b => b && RENDER[b.type]);
    if (!list.length) {
      host.insertAdjacentHTML("beforeend", '<div class="pcb-note">AI chưa trả về nội dung hiển thị được.</div>');
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      list.forEach((b, i) => setTimeout(() => {
        const wrap = document.createElement("div");
        wrap.className = "pcb-blk" + (reduce ? "" : " blk-enter");
        wrap.innerHTML = RENDER[b.type](b);
        host.appendChild(wrap);
        wrap.querySelectorAll(".pcb-chart").forEach(hydrateChart);
        wrap.querySelectorAll("[data-countup]").forEach(countUp);
        if (opts.onGrow) opts.onGrow();
        if (i === list.length - 1) resolve();
      }, i * gap));
    });
  }

  global.PulseChatBlocks = { renderBlocks, md, esc };
})(window);
