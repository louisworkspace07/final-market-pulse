/* ==========================================================================
   Market Pulse — charts-v3.js  ·  helper biểu đồ v3 (§2 / §2b của plan)
   --------------------------------------------------------------------------
   3 engine:
     • lightweight-charts (self-host /static/vendor) — chart GIÁ: area, nến, volume
     • SVG thuần (các hàm svg*) — strip, gauge, diverging bar, vol profile,
       sparkline, waterfall, sunburst, corr matrix, progress ring
     • Chart.js — giữ nguyên cho doughnut/fan-chart (các trang tự gọi)

   MỌI helper 1 chữ ký thống nhất:  fn(el, data, opts)
     el   : HTMLElement | selector string
     data : dữ liệu riêng từng loại
     opts : { title, sub, source, ts, notes:[{t,kind}], empty, height, ... }

   Màu LẤY TỪ TOKEN v3 (không hardcode rainbow). Đọc runtime để khớp theme.
   ========================================================================== */
(function (global) {
  "use strict";

  // ---- tiện ích chung ----
  function _el(x) { return typeof x === "string" ? document.querySelector(x) : x; }
  function _cssVar(name, fb) {
    const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fb;
  }
  function C() {
    return {
      up:      _cssVar("--up", "#25B770"),
      down:    _cssVar("--down", "#E14040"),
      ref:     _cssVar("--ref", "#FFC701"),
      primary: _cssVar("--primary", "#006CEC"),
      muted:   _cssVar("--muted", "#A7ADB2"),
      border:  _cssVar("--border-hi", "rgba(255,255,255,.14)"),
      text:    _cssVar("--text", "#F4F4F5"),
      card:    _cssVar("--card", "#181818"),
      bg2:     _cssVar("--bg2", "#121212"),
    };
  }
  // màu theo dấu số (tăng/giảm/tham chiếu)
  function signColor(v) { const c = C(); return v > 0 ? c.up : v < 0 ? c.down : c.ref; }
  // hash tên mã → màu ổn định cho logo tròn
  function symColor(sym) {
    let h = 0; for (let i = 0; i < sym.length; i++) h = (h * 31 + sym.charCodeAt(i)) & 0xffffff;
    const hue = h % 360; return `hsl(${hue} 55% 42%)`;
  }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
  function fmt(v, d) {
    if (v == null || !isFinite(v)) return "—";
    return Number(v).toLocaleString("vi-VN", { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
  }
  const NS = "http://www.w3.org/2000/svg";
  function svgEl(tag, attrs) {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    return e;
  }

  /* Nhãn canh giữa (text-anchor=middle) hay tràn khỏi mép SVG rồi bị cắt cụt.
     Ước lượng bề rộng theo số ký tự luôn sai (chữ Việt có dấu, font khác nhau)
     → ĐO THẬT bằng getBBox sau khi phần tử đã nằm trong DOM rồi mới dịch vào. */
  /* Hàng chờ nhãn cần kẹp: getBBox chỉ đo được KHI phần tử đã nằm trong DOM,
     mà lúc dựng chart thì SVG còn rời. Chart nào cần thì đẩy [text, width] vào
     đây, _responsive sẽ xử lý ngay sau khi gắn SVG vào trang. */
  const _pending = [];
  /* Đặt nhãn B ngay SAU nhãn A trên cùng dòng. Cũng phải hoãn: bề rộng của A chỉ
     đo được (getComputedTextLength) khi SVG đã nằm trong DOM — đo sớm trả 0 và
     hai nhãn chồng khít lên nhau. */
  const _pendingAfter = [];
  function _flushPending() {
    while (_pendingAfter.length) {
      const [a, b, gap] = _pendingAfter.pop();
      try {
        const w = a.getComputedTextLength ? a.getComputedTextLength() : 0;
        if (w) b.setAttribute("x", Number(a.getAttribute("x")) + w + (gap || 6));
      } catch (_) { /* không đo được → giữ nguyên vị trí dự phòng */ }
    }
    while (_pending.length) {
      const [t, w] = _pending.pop();
      keepInside(t, w);
    }
  }

  function keepInside(textEl, w, pad) {
    pad = pad == null ? 2 : pad;
    try {
      const b = textEl.getBBox();
      if (b.width >= w - pad * 2) return;          // quá dài thì chịu, không dịch
      let dx = 0;
      if (b.x < pad) dx = pad - b.x;
      else if (b.x + b.width > w - pad) dx = (w - pad) - (b.x + b.width);
      if (dx) textEl.setAttribute("x", Number(textEl.getAttribute("x")) + dx);
    } catch (_) { /* chưa layout được → bỏ qua, không phá chart */ }
  }

  /* ---- B1: render SVG theo PIXEL THẬT (không scale) --------------------------
     Bug cũ: viewBox nhỏ cố định + width:100% → SVG phóng to theo container ~1400px,
     chữ 11px hoá ~50px, số tràn card. Fix: đo bề rộng thật của host, dựng viewBox
     = số px thật (1 đơn vị = 1px) → font px giữ đúng cỡ; re-render khi resize. */
  function _cw(node, fb) {
    let w = node && node.clientWidth || 0;
    let p = node && node.parentNode;
    while (w < 20 && p && p.clientWidth != null) { w = p.clientWidth; p = p.parentNode; }
    return w >= 20 ? w : (fb || 320);
  }
  /* Vẽ đáp ứng: drawFn(width_px) trả về <svg> đã set width=px, viewBox="0 0 px h".
     Xoá node rồi vẽ; ResizeObserver vẽ lại khi bề rộng đổi >4px (1 observer/host). */
  function _responsive(host, drawFn) {
    let last = 0;
    const run = () => {
      const w = _cw(host);
      if (Math.abs(w - last) <= 4 && host.firstChild) return;
      last = w;
      host.innerHTML = "";
      const svg = drawFn(w);
      if (svg) {
        host.appendChild(svg);
        _flushPending();      // SVG đã vào DOM → giờ mới đo & kẹp nhãn được
      }
    };
    run();
    if (global.ResizeObserver && !host._roChart) {
      host._roChart = new ResizeObserver(() => run());
      host._roChart.observe(host);
    }
  }
  /* Co gọn đơn vị lớn: 6491 tỷ → "6,49 nghìn tỷ"; chỉ áp khi unit chứa "tỷ". */
  function fmtUnit(v, unit) {
    unit = unit || "";
    if (v == null || !isFinite(v)) return "—";
    if (/tỷ/.test(unit) && Math.abs(v) >= 1000) return fmt(v / 1000, 2) + " nghìn tỷ";
    const dec = Math.abs(v) >= 100 ? (unit ? 0 : 1) : 2;
    return fmt(v, dec) + (unit || "");
  }
  function fmtSigned(v, unit) {
    if (v == null || !isFinite(v)) return "—";
    return (v > 0 ? "+" : "") + fmtUnit(v, unit);
  }

  /* --- CHART CONTRACT: mọi helper bọc kết quả trong khung tiêu đề + source +
     bullet nhận xét. Trả về node content để helper vẽ chart vào. --- */
  function contract(host, opts) {
    opts = opts || {};
    host.innerHTML = "";
    const box = document.createElement("div"); box.className = "chart-box";
    if (opts.title) {
      const t = document.createElement("div"); t.className = "chart-title"; t.textContent = opts.title; box.appendChild(t);
    }
    if (opts.sub) {
      const s = document.createElement("div"); s.className = "chart-sub"; s.textContent = opts.sub; box.appendChild(s);
    }
    const body = document.createElement("div"); body.className = "chart-body"; box.appendChild(body);
    if (opts.notes && opts.notes.length) {
      const ul = document.createElement("ul"); ul.className = "auto-notes";
      opts.notes.forEach(n => {
        const li = document.createElement("li");
        li.className = n.kind || "neu"; li.textContent = n.t;
        ul.appendChild(li);
      });
      box.appendChild(ul);
    }
    if (opts.source && global.sourceTag) {
      const sd = document.createElement("div"); sd.style.marginTop = "8px";
      sd.innerHTML = global.sourceTag(opts.source, opts.ts || null);
      box.appendChild(sd);
    }
    host.appendChild(box);
    return body;
  }
  function empty(host, msg) {
    host.innerHTML = `<div class="chart-empty">${esc(msg || "Chưa đủ dữ liệu để hiển thị.")}</div>`;
  }

  /* ======================================================================
     A · SVG SPARKLINE (D14) — mini line 60×24, màu theo tổng kỳ
     data: number[]   opts: {w,h,color}
     ====================================================================== */
  function svgSparkline(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const w = opts.w || 60, h = opts.h || 24, pad = 2;
    if (!data || data.length < 2) { empty(host, "—"); return; }
    const min = Math.min(...data), max = Math.max(...data), rng = max - min || 1;
    const step = (w - pad * 2) / (data.length - 1);
    const pts = data.map((v, i) => [pad + i * step, h - pad - (v - min) / rng * (h - pad * 2)]);
    const col = opts.color || (data[data.length - 1] >= data[0] ? C().up : C().down);
    const svg = svgEl("svg", { width: w, height: h, viewBox: `0 0 ${w} ${h}`, class: "svg-chart" });
    const d = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
    // fill nhẹ dưới đường
    const area = svgEl("path", { d: d + ` L${pts[pts.length - 1][0].toFixed(1)} ${h} L${pts[0][0].toFixed(1)} ${h} Z`, fill: col, "fill-opacity": ".08", stroke: "none" });
    const line = svgEl("path", { d, fill: "none", stroke: col, "stroke-width": "1.5", "stroke-linejoin": "round", "stroke-linecap": "round" });
    svg.appendChild(area); svg.appendChild(line);
    host.innerHTML = ""; host.appendChild(svg);
  }

  /* ======================================================================
     B · SVG STRIP so peer (D5) — dot strip 1 dòng
     data: { self, median, peers:[{sym,value}], min, max, unit }
     ====================================================================== */
  function svgStrip(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (!data || data.self == null || !isFinite(data.self)) { empty(body, opts.empty || "Chưa đủ dữ liệu so sánh."); return; }
    const c = C();
    const unit = data.unit ? " " + data.unit : "";
    const peers = (data.peers || []).filter(p => p && p.value != null && isFinite(p.value));
    const peerVals = peers.map(p => p.value).sort((a, b) => a - b);
    // B15: clamp trục tại P5–P95 để 1 outlier (vd P/E 740) không nén mọi chấm về 1 cục.
    // Chấm ngoài dải vẽ sát mép + mũi tên "»giá trị"; tô vùng P25–P75 (giữa ngành).
    const pctl = (arr, q) => {
      if (!arr.length) return null;
      const idx = (arr.length - 1) * q, loI = Math.floor(idx), hiI = Math.ceil(idx);
      return arr[loI] + (arr[hiI] - arr[loI]) * (idx - loI);
    };
    const p05 = pctl(peerVals, 0.05), p95 = pctl(peerVals, 0.95);
    const p25 = pctl(peerVals, 0.25), p75 = pctl(peerVals, 0.75);
    const allVals = [data.self, data.median, ...peerVals].filter(v => v != null && isFinite(v));
    let lo = data.min != null ? data.min : (p05 != null ? Math.min(p05, data.self) : Math.min(...allVals));
    let hi = data.max != null ? data.max : (p95 != null ? Math.max(p95, data.self) : Math.max(...allVals));
    if (!(hi > lo)) { hi = lo + 1; lo = lo - 1; }
    _responsive(body, (w) => {
      const h = 58, padX = 10, midY = 22, axL = padX, axR = w - padX;
      const clampX = v => Math.max(axL, Math.min(axR, axL + (v - lo) / (hi - lo) * (axR - axL)));
      const inRange = v => v >= lo && v <= hi;
      const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart" });
      // vùng P25–P75 (khoảng giữa ngành) tô nhạt
      if (p25 != null && p75 != null && p75 > p25) {
        svg.appendChild(svgEl("rect", { x: clampX(p25), y: midY - 6, width: Math.max(clampX(p75) - clampX(p25), 1), height: 12,
          fill: c.primary, "fill-opacity": ".10", rx: 2 }));
      }
      svg.appendChild(svgEl("line", { x1: axL, y1: midY, x2: axR, y2: midY, stroke: c.border, "stroke-width": "1" }));
      svg.appendChild(svgEl("text", { x: axL, y: h - 4, fill: c.muted, "font-size": "9.5", "text-anchor": "start" })).textContent = fmt(lo, 1);
      svg.appendChild(svgEl("text", { x: axR, y: h - 4, fill: c.muted, "font-size": "9.5", "text-anchor": "end" })).textContent = fmt(hi, 1);
      // chú giải 1 dòng
      svg.appendChild(svgEl("text", { x: w / 2, y: h - 4, fill: c.muted, "font-size": "9", "text-anchor": "middle" }))
        .textContent = "mỗi chấm = 1 công ty cùng ngành";
      // peers mờ (hover ra mã); outlier ngoài P5–P95 → chấm sát mép + hình tam giác
      peers.forEach(p => {
        const out = !inRange(p.value);
        const cir = svgEl("circle", { cx: clampX(p.value), cy: midY, r: out ? 2.5 : 3,
          fill: out ? c.ref : c.muted, "fill-opacity": out ? ".8" : ".5" });
        const tt = svgEl("title"); tt.textContent = `${p.sym}: ${fmt(p.value, 2)}${unit}${out ? " (ngoài dải P5–P95)" : ""}`;
        cir.appendChild(tt); svg.appendChild(cir);
      });
      // trung vị ngành = vạch đứt + số dưới
      if (data.median != null && isFinite(data.median)) {
        const mx = clampX(data.median);
        svg.appendChild(svgEl("line", { x1: mx, y1: 10, x2: mx, y2: midY + 8, stroke: c.ref, "stroke-width": "1.2", "stroke-dasharray": "2 2" }));
        // nhãn canh giữa vạch → tràn mép khi trung vị nằm sát trái/phải
        const mt = svgEl("text", { x: mx, y: midY + 18, fill: c.ref, "font-size": "9.5", "text-anchor": "middle" });
        mt.textContent = "ngành " + fmt(data.median, 1);
        svg.appendChild(mt);
        _pending.push([mt, w]);
      }
      // mã này = chấm to xanh + số trên; nếu ngoài dải → mũi tên »giá trị
      const selfOut = !inRange(data.self);
      const sx = clampX(data.self);
      const me = svgEl("circle", { cx: sx, cy: midY, r: 5, fill: c.primary, stroke: c.bg2, "stroke-width": "1.5" });
      const tm = svgEl("title"); tm.textContent = `Mã này: ${fmt(data.self, 2)}${unit}`; me.appendChild(tm);
      svg.appendChild(me);
      const selfAnchor = sx > w - 34 ? "end" : sx < 34 ? "start" : "middle";
      svg.appendChild(svgEl("text", { x: sx, y: 11, fill: c.primary, "font-size": "10.5", "font-weight": "700", "text-anchor": selfAnchor }))
        .textContent = (selfOut ? "»" : "") + fmt(data.self, 1);
      return svg;
    });
  }

  /* ======================================================================
     C · SVG DIVERGING BAR ± (D4/D9/C10) — cột/thanh qua trục 0
     data: [{label, value}]   opts:{horizontal, unit, notes}
     ====================================================================== */
  function svgDiverging(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (!data || !data.length) { empty(body, opts.empty || "Chưa có dữ liệu."); return; }
    const c = C();
    const maxAbs = Math.max(...data.map(d => Math.abs(d.value || 0)), 1e-9);
    // B1: vẽ theo px thật — 1 unit viewBox = 1px, font px giữ đúng cỡ ở mọi bề rộng.
    if (opts.horizontal !== false) {
      _responsive(body, (w) => {
        const rowH = 26, padL = Math.min(120, Math.max(80, w * 0.28));
        const mid = padL + (w - padL) / 2;
        const h = data.length * rowH + 6;
        const halfBar = (w - padL) / 2 - 8;
        const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart" });
        data.forEach((d, i) => {
          const y = i * rowH + 4;
          const len = Math.abs(d.value) / maxAbs * halfBar;
          const col = signColor(d.value);
          const x = d.value >= 0 ? mid : mid - len;
          svg.appendChild(svgEl("text", { x: 4, y: y + rowH / 2 + 4, fill: c.muted, "font-size": "11" })).textContent = d.label;
          const r = svgEl("rect", { x, y: y + 4, width: Math.max(len, .5), height: rowH - 12, rx: 3, fill: col });
          const tt = svgEl("title"); tt.textContent = `${d.label}: ${fmtUnit(d.value, opts.unit)}`; r.appendChild(tt);
          svg.appendChild(r);
          // nhãn số: co đơn vị lớn; nếu tràn mép card → đặt TRONG bar (anchor ngược)
          const label = fmtSigned(d.value, opts.unit);
          const estW = label.length * 5.4;
          const outX = d.value >= 0 ? x + len + 4 : x - 4;
          const overflow = d.value >= 0 ? (outX + estW > w - 2) : (outX - estW < padL);
          const tx = overflow ? (d.value >= 0 ? x + len - 4 : x + 4) : outX;
          const anchor = overflow ? (d.value >= 0 ? "end" : "start") : (d.value >= 0 ? "start" : "end");
          svg.appendChild(svgEl("text", { x: tx, y: y + rowH / 2 + 4, fill: overflow ? "#fff" : col, "font-size": "10.5", "text-anchor": anchor })).textContent = label;
        });
        svg.appendChild(svgEl("line", { x1: mid, y1: 0, x2: mid, y2: h, stroke: c.border, "stroke-width": ".5" }));
        return svg;
      });
    } else {
      // cột dọc theo phiên (khối ngoại 10 phiên)
      _responsive(body, (w) => {
        const h = opts.height || 150, midY = h / 2;
        const colW = Math.max(14, Math.min(40, (w - 20) / data.length));
        const bw = Math.max(4, colW - 8);
        const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart" });
        svg.appendChild(svgEl("line", { x1: 0, y1: midY, x2: w, y2: midY, stroke: c.border, "stroke-width": ".5" }));
        data.forEach((d, i) => {
          const bh = Math.abs(d.value) / maxAbs * (h / 2 - 14);
          const col = signColor(d.value);
          const x = 10 + i * colW;
          const y = d.value >= 0 ? midY - bh : midY;
          const r = svgEl("rect", { x, y, width: bw, height: Math.max(bh, .5), rx: 2, fill: col });
          const tt = svgEl("title"); tt.textContent = `${d.label}: ${fmtUnit(d.value, opts.unit)}`; r.appendChild(tt);
          svg.appendChild(r);
        });
        return svg;
      });
    }
  }

  /* ======================================================================
     D · SVG GAUGE bán nguyệt (R2) — sức khỏe 0–100
     data: number(0–100)   opts:{label, bands}
     ====================================================================== */
  function svgGauge(el, value, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (value == null || !isFinite(value)) { empty(body, opts.empty || "Chưa chấm điểm được."); return; }
    const c = C();
    const w = 220, h = 130, cx = w / 2, cy = 116, r = 92;
    const pol = (ang) => [cx + r * Math.cos(Math.PI * (1 - ang)), cy - r * Math.sin(Math.PI * (1 - ang))];
    function arc(a0, a1, col, sw) {
      const [x0, y0] = pol(a0), [x1, y1] = pol(a1);
      const large = (a1 - a0) > .5 ? 1 : 0;
      return svgEl("path", { d: `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`, fill: "none", stroke: col, "stroke-width": sw, "stroke-linecap": "round" });
    }
    // B1: cố định px, không giãn theo container (gauge to lố ở card rộng).
    const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart", style: "max-width:100%;display:block;margin:0 auto" });
    // 3 dải nền mờ (thấp/vừa/cao — KHÔNG mua/bán)
    svg.appendChild(arc(0, 0.33, "rgba(225,64,64,.30)", 12));
    svg.appendChild(arc(0.34, 0.66, "rgba(255,199,1,.30)", 12));
    svg.appendChild(arc(0.67, 1, "rgba(37,183,112,.30)", 12));
    // kim
    const frac = Math.max(0, Math.min(1, value / 100));
    const [nx, ny] = pol(frac);
    svg.appendChild(svgEl("line", { x1: cx, y1: cy, x2: nx, y2: ny, stroke: c.text, "stroke-width": "2.5", "stroke-linecap": "round" }));
    svg.appendChild(svgEl("circle", { cx, cy, r: 4, fill: c.text }));
    body.appendChild(svg);
    const lab = document.createElement("div"); lab.className = "gauge-val"; lab.style.color = frac < .33 ? c.down : frac < .67 ? c.ref : c.up;
    lab.textContent = fmt(value, 0);
    body.appendChild(lab);
  }

  /* ======================================================================
     E · SVG PROGRESS RING (R7) — vòng % nhỏ
     data: number(0–100)   opts:{size,label}
     ====================================================================== */
  function svgRing(el, value, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const size = opts.size || 40, sw = 3.5, r = (size - sw) / 2, cx = size / 2;
    const c = C(), frac = Math.max(0, Math.min(1, (value || 0) / 100));
    const circ = 2 * Math.PI * r;
    const svg = svgEl("svg", { width: size, height: size, viewBox: `0 0 ${size} ${size}` });
    svg.appendChild(svgEl("circle", { cx, cy: cx, r, fill: "none", stroke: c.border, "stroke-width": sw }));
    svg.appendChild(svgEl("circle", { cx, cy: cx, r, fill: "none", stroke: opts.color || c.primary, "stroke-width": sw, "stroke-dasharray": `${circ * frac} ${circ}`, "stroke-linecap": "round", transform: `rotate(-90 ${cx} ${cx})` }));
    const t = svgEl("text", { x: cx, y: cx + 3.5, "text-anchor": "middle", "font-size": size / 3.6, fill: c.text }); t.textContent = fmt(value, 0);
    svg.appendChild(t);
    host.innerHTML = ""; host.className = "ring-mini"; host.appendChild(svg);
  }

  /* ======================================================================
     F · SVG VOLUME PROFILE (D10/C9) — histogram ngang theo mức giá
     data: [{price, vol, pct}]   opts:{current}
     ====================================================================== */
  function svgVProfile(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (!data || !data.length) { empty(body, opts.empty || "Chưa tính được phân bố khớp lệnh."); return; }
    const c = C();
    const maxPct = Math.max(...data.map(d => d.pct || 0), 1);
    // B1: px thật.
    _responsive(body, (w) => {
      const rowH = 18, padL = 56, padR = 46, h = data.length * rowH + 4;
      const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart" });
      data.forEach((d, i) => {
        const y = i * rowH + 2;
        const bw = (d.pct / maxPct) * (w - padL - padR);
        const hot = opts.current != null && Math.abs(d.price - opts.current) < 1e-9;
        svg.appendChild(svgEl("text", { x: 2, y: y + rowH / 2 + 3.5, fill: hot ? c.ref : c.muted, "font-size": "10.5" })).textContent = fmt(d.price, 2);
        svg.appendChild(svgEl("rect", { x: padL, y: y + 3, width: Math.max(bw, .5), height: rowH - 8, rx: 2, fill: hot ? c.ref : c.primary, "fill-opacity": hot ? ".8" : ".55" }));
        svg.appendChild(svgEl("text", { x: padL + bw + 4, y: y + rowH / 2 + 3.5, fill: c.muted, "font-size": "10" })).textContent = fmt(d.pct, 1) + "%";
      });
      return svg;
    });
  }

  /* ======================================================================
     G · SVG WATERFALL (D15) — dòng tiền bắc cầu
     data: [{label, value, kind}] kind: start|flow|end
     ====================================================================== */
  function svgWaterfall(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (!data || !data.length) { empty(body, opts.empty || "Chưa có dữ liệu dòng tiền."); return; }
    const c = C();
    // tính đỉnh cột lũy kế
    let cum = 0; const bars = [];
    data.forEach(d => {
      if (d.kind === "start" || d.kind === "end") { bars.push({ ...d, base: 0, top: d.value }); cum = d.value; }
      else { const base = cum; cum += d.value; bars.push({ ...d, base: Math.min(base, cum), top: Math.max(base, cum) }); }
    });
    const allv = bars.flatMap(b => [b.base, b.top]);
    const lo = Math.min(0, ...allv), hi = Math.max(...allv) || 1;
    // B1+B17: px thật + cột nối bắc cầu nét đứt. Nhãn số dồn về 1 HÀNG NGANG
    // chung phía trên đỉnh cột cao nhất (bỏ so le trên/dưới cho đỡ zigzag rối mắt).
    _responsive(body, (w) => {
      const h = opts.height || 190, padB = 22, padT = 30;   // padT chừa 1 hàng nhãn trên cùng
      const colW = Math.max(40, Math.min(72, (w - 20) / data.length));
      const bw = colW - 12;
      const Y = v => (h - padB) - (v - lo) / (hi - lo) * (h - padB - padT);
      const labelY = Y(hi) - 8;                             // 1 hàng nhãn thẳng trên đỉnh cột cao nhất
      const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart" });
      // đường 0
      if (lo < 0 && hi > 0) svg.appendChild(svgEl("line", { x1: 6, y1: Y(0), x2: w - 6, y2: Y(0), stroke: c.border, "stroke-width": ".5" }));
      bars.forEach((b, i) => {
        const x = 10 + i * colW;
        const col = b.kind === "start" || b.kind === "end" ? c.muted : (b.value >= 0 ? c.up : c.down);
        // cột nối bắc cầu nét đứt từ đỉnh lũy kế cột trước → chân cột này (chỉ flow)
        if (b.kind === "flow" && i > 0) {
          const prevTop = bars[i - 1].kind === "flow" || bars[i - 1].kind === "start" ? cumAt(bars, i - 1) : bars[i - 1].top;
          svg.appendChild(svgEl("line", { x1: (10 + (i - 1) * colW) + bw, y1: Y(prevTop),
            x2: x, y2: Y(prevTop), stroke: c.border, "stroke-width": ".8", "stroke-dasharray": "3 2" }));
        }
        svg.appendChild(svgEl("rect", { x, y: Y(b.top), width: bw, height: Math.max(Y(b.base) - Y(b.top), 1), rx: 2, fill: col }));
        svg.appendChild(svgEl("text", { x: x + bw / 2, y: h - 7, "text-anchor": "middle", fill: c.muted, "font-size": "10" })).textContent = b.label;
        // Nhãn số: tất cả trên CÙNG 1 hàng ngang (labelY), canh giữa cột. Kẹp tâm
        // chữ vào trong khung để nhãn cột đầu/cuối không tràn mép rồi bị cắt cụt.
        // Dùng SỐ TỶ GỌN (5.680, +2.130) thay "5,68 nghìn tỷ" — tiêu đề đã ghi
        // đơn vị "(tỷ đồng)" nên khỏi lặp, và nhãn ngắn thì các cột liền kề trên
        // cùng hàng không đè nhau ở màn hẹp.
        const short = fmt(Math.round(b.value), 0);
        const vlab = (b.kind === "flow") ? (b.value >= 0 ? "+" + short : short) : short;
        const vt = svgEl("text", { x: x + bw / 2, y: labelY, "text-anchor": "middle", fill: col, "font-size": "9", "font-weight": "600" });
        vt.textContent = vlab;
        svg.appendChild(vt);
        _pending.push([vt, w]);
      });
      return svg;
    });
    function cumAt(bars, idx) {  // đỉnh lũy kế đến hết cột idx (để bắc cầu)
      let cc = 0;
      for (let k = 0; k <= idx; k++) {
        const bb = bars[k];
        cc = (bb.kind === "start" || bb.kind === "end") ? bb.value : cc + bb.value;
      }
      return cc;
    }
  }

  /* ======================================================================
     H · SVG CORR MATRIX (D13) — ma trận màu -1↔+1
     data: { labels:[], matrix:[[]] }
     ====================================================================== */
  function svgCorrMatrix(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (!data || !data.labels || !data.labels.length) { empty(body, opts.empty || "Chưa đủ mã để tính tương quan."); return; }
    const c = C(), n = data.labels.length;
    const cell = Math.max(22, Math.min(44, 380 / n)), padL = 44, padT = 44;
    const w = padL + n * cell, h = padT + n * cell;
    const color = v => {  // -1 xanh dương ↔ 0 trắng ↔ +1 đỏ
      if (v == null) return c.bg2;
      const t = Math.max(-1, Math.min(1, v));
      if (t >= 0) return `rgba(225,64,64,${(t * .8).toFixed(2)})`;
      return `rgba(74,200,245,${(-t * .8).toFixed(2)})`;
    };
    // B1: kích thước cố định px (không kéo giãn theo container 1400px).
    const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart", style: "max-width:100%" });
    data.labels.forEach((lb, i) => {
      svg.appendChild(svgEl("text", { x: padL + i * cell + cell / 2, y: padT - 6, "text-anchor": "middle", fill: c.muted, "font-size": "10" })).textContent = lb;
      svg.appendChild(svgEl("text", { x: padL - 6, y: padT + i * cell + cell / 2 + 3, "text-anchor": "end", fill: c.muted, "font-size": "10" })).textContent = lb;
    });
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) {
      const v = data.matrix[i][j];
      svg.appendChild(svgEl("rect", { x: padL + j * cell, y: padT + i * cell, width: cell - 1, height: cell - 1, fill: color(v) }));
      if (v != null && Math.abs(v) >= 0.4) {
        const t = svgEl("text", { x: padL + j * cell + cell / 2, y: padT + i * cell + cell / 2 + 3, "text-anchor": "middle", "font-size": "9.5", fill: Math.abs(v) >= .7 ? "#fff" : c.text, "font-weight": Math.abs(v) >= .7 ? "700" : "400" });
        t.textContent = v.toFixed(2).replace("0.", ".").replace("-0.", "-."); svg.appendChild(t);
      }
    }
    body.appendChild(svg);
  }

  /* ======================================================================
     I · SVG SUNBURST 2 tầng (R6) — ngành→mã
     data: [{sector, cap, chg, children:[{sym,cap,chg}]}]  (đơn giản hoá)
     ====================================================================== */
  function svgSunburst(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    if (!data || !data.length) { empty(body, opts.empty || "Chưa có dữ liệu ngành."); return; }
    const c = C(), size = 300, cx = size / 2, cy = size / 2, r1 = 70, r2 = 120;
    const total = data.reduce((s, d) => s + (d.cap || 0), 0) || 1;
    const chgColor = v => v > 2 ? c.up : v > 0 ? "rgba(37,183,112,.6)" : v < -2 ? c.down : v < 0 ? "rgba(225,64,64,.6)" : c.ref;
    function seg(a0, a1, ri, ro, fill, label) {
      const p = a => [cx + ro * Math.cos(a), cy + ro * Math.sin(a)];
      const q = a => [cx + ri * Math.cos(a), cy + ri * Math.sin(a)];
      const [x0, y0] = p(a0), [x1, y1] = p(a1), [x2, y2] = q(a1), [x3, y3] = q(a0);
      const large = (a1 - a0) > Math.PI ? 1 : 0;
      const path = svgEl("path", { d: `M${x0} ${y0} A${ro} ${ro} 0 ${large} 1 ${x1} ${y1} L${x2} ${y2} A${ri} ${ri} 0 ${large} 0 ${x3} ${y3} Z`, fill, stroke: c.bg2, "stroke-width": "1" });
      if (label) { const tt = svgEl("title"); tt.textContent = label; path.appendChild(tt); }
      return path;
    }
    const svg = svgEl("svg", { viewBox: `0 0 ${size} ${size}`, class: "svg-chart", width: "100%", style: "max-width:320px;margin:0 auto" });
    let ang = -Math.PI / 2;
    data.forEach(d => {
      const sw = (d.cap || 0) / total * 2 * Math.PI;
      const a0 = ang, a1 = ang + sw;
      svg.appendChild(seg(a0, a1, r1, r2, chgColor(d.chg || 0), `${d.sector}: ${fmt(d.chg, 2)}%`));
      // tầng 2: mã
      let ca = a0; const ctot = (d.children || []).reduce((s, x) => s + (x.cap || 0), 0) || 1;
      (d.children || []).forEach(ch => {
        const cw = (ch.cap || 0) / ctot * sw;
        svg.appendChild(seg(ca, ca + cw, 40, r1 - 2, chgColor(ch.chg || 0), `${ch.sym}: ${fmt(ch.chg, 2)}%`));
        ca += cw;
      });
      ang = a1;
    });
    body.appendChild(svg);
  }

  /* ======================================================================
     J · LIGHTWEIGHT-CHARTS — area giá/chỉ số (D2)
     data: [{time, value}]  (time: "yyyy-mm-dd" hoặc unix)
     opts:{height, color, title, sub, source}
     ====================================================================== */
  // B10: trục thời gian LWC tiếng Việt — "Th8", "Th10/2026" thay vì "Aug/Oct".
  const _VN_MON = ["Th1","Th2","Th3","Th4","Th5","Th6","Th7","Th8","Th9","Th10","Th11","Th12"];
  function _lwcTime(t) {
    // LWC time có thể là "YYYY-MM-DD" (business day) hoặc epoch giây
    if (typeof t === "string") { const [y,m,d] = t.split("-").map(Number); return { y, m, d }; }
    if (t && typeof t === "object" && t.year) return { y: t.year, m: t.month, d: t.day };
    const dt = new Date((typeof t === "number" ? t : 0) * 1000);
    return { y: dt.getFullYear(), m: dt.getMonth() + 1, d: dt.getDate() };
  }
  function _vnTickFmt(time, tickType) {
    const { y, m, d } = _lwcTime(time);
    // tickType: 0=Year 1=Month 2=DayOfMonth 3=Time (theo LWC TickMarkType)
    if (tickType === 0) return String(y);
    if (tickType === 1) return `${_VN_MON[m - 1]}/${y}`;
    return `${d} ${_VN_MON[m - 1]}`;
  }
  function _vnTimeFmt(time) {
    const { y, m, d } = _lwcTime(time);
    return `${d} ${_VN_MON[m - 1]} ${y}`;
  }
  /* Ảnh 15 · Trục giá LWC mặc định in kiểu Anh ("2000.00") — đây là ổ lệch định
     dạng lớn nhất còn lại. Ngưỡng 10.000: giá cổ phiếu tính bằng đồng (73.500)
     làm tròn 0 lẻ; chỉ số / giá nghìn-đồng (1.848,25 · 7,50) giữ 2 lẻ. */
  function _vnPriceFmt(p) {
    const n = Number(p);
    if (!isFinite(n)) return "—";
    return n.toLocaleString("vi-VN", Math.abs(n) >= 10000
      ? { minimumFractionDigits: 0, maximumFractionDigits: 0 }
      : { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  const _vnLocalization = { locale: "vi-VN", timeFormatter: _vnTimeFmt, priceFormatter: _vnPriceFmt };

  function lwcArea(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    if (!global.LightweightCharts) { empty(host, "Chưa tải được thư viện biểu đồ."); return; }
    if (!data || data.length < 2) { empty(host, opts.empty || "Chưa đủ dữ liệu giá."); return; }
    const c = C();
    const box = document.createElement("div");
    if (opts.title) { const t = document.createElement("div"); t.className = "chart-title"; t.textContent = opts.title; host.innerHTML = ""; host.appendChild(t); } else host.innerHTML = "";
    host.appendChild(box);
    const chart = global.LightweightCharts.createChart(box, {
      height: opts.height || 260,
      layout: { background: { color: "transparent" }, textColor: c.muted, fontFamily: "Inter, sans-serif" },
      grid: { vertLines: { color: c.border, style: 1 }, horzLines: { color: c.border, style: 1 } },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, timeVisible: false, tickMarkFormatter: _vnTickFmt },
      localization: _vnLocalization,
      crosshair: { mode: 1 },
      handleScroll: true, handleScale: true,
    });
    const col = opts.color || c.primary;
    const series = chart.addAreaSeries({
      lineColor: col, topColor: col.startsWith("#") ? col + "40" : col, bottomColor: "transparent",
      lineWidth: 2, priceLineVisible: false,
    });
    series.setData(data);
    chart.__mpSeries = series;      // §18: cho phép createPriceLine từ bên ngoài
    chart.timeScale().fitContent();
    if (opts.source && global.sourceTag) {
      const sd = document.createElement("div"); sd.style.marginTop = "6px";
      sd.innerHTML = global.sourceTag(opts.source, opts.ts || null); host.appendChild(sd);
    }
    // responsive — xem ghi chú ở _refitOnResize (phải fit lại, không chỉ đổi width)
    _refitOnResize(chart, box);
    return chart;
  }

  /* K · LWC candlestick + volume (D1)
     data: {ohlc:[{time,open,high,low,close}], vol:[{time,value,color?}]} */
  function lwcCandle(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    if (!global.LightweightCharts) { empty(host, "Chưa tải được thư viện biểu đồ."); return; }
    if (!data || !data.ohlc || data.ohlc.length < 2) { empty(host, opts.empty || "Chưa đủ dữ liệu nến."); return; }
    const c = C();
    host.innerHTML = "";
    const box = document.createElement("div"); host.appendChild(box);
    const chart = global.LightweightCharts.createChart(box, {
      height: opts.height || 320,
      layout: { background: { color: "transparent" }, textColor: c.muted, fontFamily: "Inter, sans-serif" },
      grid: { vertLines: { color: c.border }, horzLines: { color: c.border } },
      rightPriceScale: { borderColor: c.border },
      timeScale: { borderColor: c.border, tickMarkFormatter: _vnTickFmt },
      localization: _vnLocalization,
      crosshair: { mode: 1 },
    });
    const cs = chart.addCandlestickSeries({ upColor: c.up, downColor: c.down, borderVisible: false, wickUpColor: c.up, wickDownColor: c.down });
    cs.setData(data.ohlc);
    chart.__mpSeries = cs;          // §18: cho phép createPriceLine từ bên ngoài
    if (data.vol && data.vol.length) {
      const vs = chart.addHistogramSeries({ priceScaleId: "vol", priceFormat: { type: "volume" } });
      chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
      vs.setData(data.vol.map(v => ({ time: v.time, value: v.value, color: v.color || (c.muted + "80") })));
    }
    chart.timeScale().fitContent();
    _refitOnResize(chart, box);
    return chart;
  }

  /* PHẢI fit LẠI sau mỗi lần đổi bề rộng, không chỉ applyOptions({width}).
     Chart hay được tạo lúc container chưa có bề rộng thật (tab đang ẩn, layout
     chưa xong) → fitContent() fit vào bề rộng cũ; container giãn ra thì khoảng
     cách nến giữ nguyên nên nến dồn hết về một phía, chừa nửa biểu đồ trống.
     Đúng lỗi thấy ở "Diễn biến giá". */
  function _refitOnResize(chart, box) {
    let w0 = 0;
    const ro = new ResizeObserver(() => {
      const w = box.clientWidth;
      if (!w || w === w0) return;
      w0 = w;
      chart.applyOptions({ width: w });
      chart.timeScale().fitContent();
    });
    ro.observe(box);
    return ro;
  }

  /* ======================================================================
     L · Logo tròn mã CK (C2) — trả về HTML string
     ====================================================================== */
  /* Ảnh 4 · Logo thật cho từng mã khi có file trong /static/logos/<MÃ>.png.
     Danh sách mã CÓ logo đọc từ manifest.json (nạp 1 lần) — nhờ vậy mã chưa có
     logo KHÔNG bắn request 404 nào, và khi bổ sung logo thì tự hiện, không cần
     sửa code. Chưa có logo → avatar chữ cái màu ổn định như cũ.
     LƯU Ý: chưa có nguồn dữ liệu website/logo doanh nghiệp trong stack hiện tại
     (vnstock/market.db đều không có trường này) nên manifest đang rỗng. */
  let _logoSet = null;
  (function loadLogoManifest() {
    fetch("/static/logos/manifest.json")
      .then(r => r.ok ? r.json() : null)
      .then(m => { _logoSet = new Set((m && m.symbols) || []); })
      .catch(() => { _logoSet = new Set(); });
  })();

  function symLogoHTML(sym) {
    const s = (sym || "?").toUpperCase();
    const letter = `<span class="sym-logo" style="background:${symColor(s)}">${esc(s[0] || "?")}</span>`;
    if (!_logoSet || !_logoSet.has(s)) return letter;
    return `<img class="sym-logo sym-logo-img" src="/static/logos/${encodeURIComponent(s)}.png"
      alt="${esc(s)}" loading="lazy"
      onerror="this.outerHTML=${esc(JSON.stringify(letter)).replace(/"/g, "&quot;")}">`;
  }

  /* ======================================================================
     §12 · ONE BAR SYSTEM — mpBar(el, opts)
     Chuẩn hóa MỌI chỉ số về 1 thanh cùng chiều: TRÁI = kém hơn, PHẢI = thuận
     lợi hơn (theo mô hình). Kim + gradient 5 nấc + verdict + reasons + ⓘ.
     opts: { value:0–100|null, labelLeft, labelRight, verdict, reasons:[],
             detailHtml, variant:'single'|'tug'|'thermo', animate,
             tug:{aLabel,bLabel,aValue,bValue}, sub }
     value=null → thanh xám "chưa đủ dữ liệu" (KHÔNG kim giả).
     ====================================================================== */
  let _mpBarSeq = 0;
  function mpBar(el, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const c = C();
    const variant = opts.variant || "single";
    const reduce = global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // ---- variant TUG: 2 lực đối đầu A | B ----
    if (variant === "tug") {
      const t = opts.tug || {};
      const a = Math.max(0, +t.aValue || 0), b = Math.max(0, +t.bValue || 0), sum = a + b;
      const aPct = sum > 0 ? a / sum * 100 : 50;
      const wrap = document.createElement("div"); wrap.className = "mpbar-wrap mpbar-tug";
      wrap.innerHTML =
        `<div class="mpbar-tug-labels"><span class="tl-a">${esc(t.aLabel || "A")}</span>` +
        `<span class="tl-b">${esc(t.bLabel || "B")}</span></div>` +
        `<div class="mpbar-track tug"><div class="tug-a" style="width:${sum > 0 ? aPct : 50}%"></div>` +
        `<div class="tug-b" style="width:${sum > 0 ? 100 - aPct : 50}%"></div></div>` +
        `<div class="mpbar-tug-pct"><span>${sum > 0 ? fmt(aPct, 0) + "%" : "—"}</span>` +
        `<span>${sum > 0 ? fmt(100 - aPct, 0) + "%" : "—"}</span></div>` +
        (opts.verdict ? `<div class="mpbar-verdict">${esc(opts.verdict)}</div>` : "");
      host.innerHTML = ""; host.appendChild(wrap);
      if (!reduce && sum > 0) {
        const ea = wrap.querySelector(".tug-a"), eb = wrap.querySelector(".tug-b");
        ea.style.width = "50%"; eb.style.width = "50%";
        requestAnimationFrame(() => { ea.style.width = aPct + "%"; eb.style.width = (100 - aPct) + "%"; });
      }
      return;
    }

    // ---- variant SINGLE / THERMO ----
    const v = opts.value;
    const missing = v == null || !isFinite(v);
    const val = missing ? 0 : Math.max(0, Math.min(100, v));
    const id = "mpb-" + (++_mpBarSeq);
    const wrap = document.createElement("div"); wrap.className = "mpbar-wrap";
    const reasons = (opts.reasons || []).slice(0, 3);
    const reasonHtml = reasons.length
      ? `<div class="mpbar-reasons">${reasons.map(r =>
          `<span class="mpbar-chip ${r.kind === "ok" ? "ok" : r.kind === "bad" ? "bad" : "neu"}">${esc(r.t || r)}</span>`).join("")}</div>`
      : "";
    const detailHtml = opts.detailHtml
      ? `<details class="mpbar-detail"><summary>ⓘ Xem số liệu gốc</summary><div class="mpbar-detail-body">${opts.detailHtml}</div></details>`
      : "";
    wrap.innerHTML =
      `<div class="mpbar-labels"><span>${esc(opts.labelLeft || "kém hơn")}</span>` +
      `<span>${esc(opts.labelRight || "thuận lợi hơn")}</span></div>` +
      `<div class="mpbar-track${missing ? " missing" : ""}">` +
        (missing
          ? `<span class="mpbar-na">chưa đủ dữ liệu</span>`
          : `<span class="mpbar-needle" id="${id}" style="left:${reduce ? val : 0}%">` +
            `<span class="mpbar-needle-val">${fmt(val, 0)}</span></span>`) +
      `</div>` +
      (opts.verdict ? `<div class="mpbar-verdict">${esc(opts.verdict)}</div>` : "") +
      reasonHtml + detailHtml;
    host.innerHTML = ""; host.appendChild(wrap);
    // animation kim trượt 350ms 1 lần
    if (!missing && !reduce) {
      const nd = wrap.querySelector("#" + id);
      requestAnimationFrame(() => { nd.style.transition = "left .35s ease"; nd.style.left = val + "%"; });
    }
  }

  /* ======================================================================
     §B16 · TREND BLOCK — mpTrend(el, data, opts)
     Chuỗi năm ngắn (LNST/ROE/payout…): CHUYỆN tăng/giảm, không phải 4 bar giống nhau.
     data: [{label, value}]  (theo thứ tự thời gian, cũ→mới)
     opts: { title, unit, metric (tên hiển thị headline), source, ts,
             higherIsBetter=true, height }
     - HEADLINE: delta tổng đầu→cuối ("LNST +73% sau 4 năm").
     - Mỗi bar: %YoY cạnh cột; năm GIẢM so năm trước tô ĐỎ (màu THEO YoY, không theo dấu).
     - Bar năm mới nhất đậm, năm trước mờ 65%.
     value=null/thiếu → bỏ qua điểm đó (không bịa).
     ====================================================================== */
  function mpTrend(el, data, opts) {
    const host = _el(el); if (!host) return;
    opts = opts || {};
    const body = contract(host, opts);
    const pts = (data || []).filter(d => d && d.value != null && isFinite(d.value));
    if (pts.length < 2) { empty(body, opts.empty || "Chưa đủ dữ liệu nhiều năm."); return; }
    const c = C();
    const unit = opts.unit || "";
    const hib = opts.higherIsBetter !== false;
    const first = pts[0].value, last = pts[pts.length - 1].value;

    /* Chỉ số VỐN ĐÃ LÀ PHẦN TRĂM (payout, biên lợi nhuận, ROE…) thì so sánh 2 năm
       bằng %-thay-đổi là vô nghĩa: payout 2,1% → 40,5% ra "+1.829%", còn 3,6% →
       291,3% ra "+7.001,7% YoY" — đúng số học nhưng người đọc không hiểu gì.
       Với các chỉ số này phải dùng ĐIỂM % (chênh lệch tuyệt đối). */
    const isPct = unit === "%";
    const deltaTxt = (from, to) => {
      const d = to - from;
      if (isPct) return `${d >= 0 ? "+" : ""}${fmt(d, 1)} điểm %`;
      if (from !== 0 && isFinite(from)) return `${d >= 0 ? "+" : ""}${fmt(d / Math.abs(from) * 100, 1)}%`;
      return fmtSigned(d, unit);
    };
    // biến động từng năm (năm đầu không có)
    const yoy = pts.map((d, i) => i === 0 ? null
      : (isPct ? d.value - pts[i - 1].value
               : (pts[i - 1].value !== 0
                  ? (d.value - pts[i - 1].value) / Math.abs(pts[i - 1].value) * 100 : null)));
    const yoyTxt = (v) => v == null ? ""
      : `${v >= 0 ? "+" : ""}${fmt(v, 1)}${isPct ? " điểm %" : "%"}`;

    const headline = (isPct || (first !== 0 && isFinite(first)))
      ? `${opts.metric || "Giá trị"} ${deltaTxt(first, last)} sau ${pts.length - 1} năm`
      : `${opts.metric || "Giá trị"} ${fmtSigned(last - first, unit)} sau ${pts.length - 1} năm`;
    const headKind = (last >= first) === hib ? "ok" : "bad";

    // header kể chuyện
    const head = document.createElement("div"); head.className = "mptrend-head " + headKind;
    head.innerHTML = `<span class="mpt-delta">${esc(headline)}</span>` +
      `<span class="mpt-range">${esc(String(pts[0].label))}: ${fmtUnit(first, unit)} → ${esc(String(pts[pts.length - 1].label))}: ${fmtUnit(last, unit)}</span>`;
    body.appendChild(head);

    // bar theo px thật; màu THEO YoY (tăng=xanh, giảm=đỏ); năm mới nhất đậm.
    // Vẽ vào child riêng — _responsive xóa innerHTML của host nên KHÔNG dùng body
    // (sẽ wipe .mptrend-head vừa append).
    const barHost = document.createElement("div"); body.appendChild(barHost);
    _responsive(barHost, (w) => {
      // giá trị + biến động giờ nằm CÙNG dòng nên cần lề phải rộng hơn hẳn:
      // dài nhất gặp thực tế "6,76 nghìn tỷ  +287,7 điểm %" ≈ 150px.
      const rowH = 30, padL = 52, padR = isPct ? 162 : 150, h = pts.length * rowH + 6;
      const maxAbs = Math.max(...pts.map(d => Math.abs(d.value)), 1e-9);
      const barMax = w - padL - padR;
      const svg = svgEl("svg", { viewBox: `0 0 ${w} ${h}`, width: w, height: h, class: "svg-chart" });
      pts.forEach((d, i) => {
        const y = i * rowH + 4;
        const len = Math.abs(d.value) / maxAbs * barMax;
        const newest = i === pts.length - 1;
        // màu theo YoY: năm đầu (không YoY) trung tính primary; tăng=up; giảm=down
        const yv = yoy[i];
        const col = yv == null ? c.primary : (yv >= 0 ? c.up : c.down);
        const op = newest ? "1" : "0.65";
        svg.appendChild(svgEl("text", { x: 4, y: y + rowH / 2 + 4, fill: newest ? c.text : c.muted,
          "font-size": "11.5", "font-weight": newest ? "700" : "500" })).textContent = d.label;
        // 1 năm đột biến (payout 291% giữa các năm 2–4%) làm mọi cột khác teo còn
        // sợi chỉ. Giữ tỷ lệ THẬT nhưng cho cột tối thiểu 3px để vẫn nhìn thấy có số.
        const r = svgEl("rect", { x: padL, y: y + 5, width: Math.max(len, 3), height: rowH - 14, rx: 3, fill: col, opacity: op });
        const tt = svgEl("title");
        tt.textContent = `${d.label}: ${fmtUnit(d.value, unit)}`
          + (yv != null ? ` (so năm trước ${yoyTxt(yv)})` : "");
        r.appendChild(tt);
        svg.appendChild(r);
        /* Giá trị + biến động năm nằm CÙNG 1 DÒNG. Bản cũ xếp chồng 2 dòng cách
           nhau 11px trong khi mỗi dòng cao ~12px → chữ đè nhau (đo được 9 cặp),
           nhìn rất rối. Một dòng vừa hết đè vừa đỡ rườm mắt cho người mới. */
        const tx = padL + Math.max(len, 3) + 6;
        const ty = y + rowH / 2 + 4;
        const valTxt = fmtUnit(d.value, unit);
        const vEl = svgEl("text", { x: tx, y: ty, fill: newest ? c.text : c.muted,
          "font-size": "10.5", "font-weight": newest ? "700" : "400" });
        vEl.textContent = valTxt;
        svg.appendChild(vEl);
        if (yv != null) {
          // vị trí tạm (ước lượng) rồi hoãn lại để đặt chính xác sau khi vào DOM
          const yEl = svgEl("text", { x: tx + valTxt.length * 5.6 + 7, y: ty, fill: col, "font-size": "9.5" });
          yEl.textContent = yoyTxt(yv);
          svg.appendChild(yEl);
          _pendingAfter.push([vEl, yEl, 7]);
        }
      });
      return svg;
    });
  }

  // ---- export ----
  global.MPChart = {
    svgSparkline, svgStrip, svgDiverging, svgGauge, svgRing,
    svgVProfile, svgWaterfall, svgCorrMatrix, svgSunburst,
    lwcArea, lwcCandle, symLogoHTML, symColor, mpBar, mpTrend,
    _contract: contract, _empty: empty, _C: C, _fmtUnit: fmtUnit,
  };
})(window);
