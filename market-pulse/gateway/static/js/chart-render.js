/* ============================================================================
   D-2 · Vẽ biểu đồ cho trang cổ phiếu — PLAN-F0-TRUC-QUAN Phụ lục D.

   Nhận đúng payload của `GET /api/stock/<mã>/charts` (chart_data.py) và vẽ ra
   SVG. KHÔNG phụ thuộc thư viện ngoài:
     - dự án đã theo hướng này rồi (user.html tự vẽ SVG, lightweight-charts để
       sẵn trong vendor/), nên không thêm CDN mới;
     - chạy được cả khi máy không có mạng.
   Đổi lại: không có zoom/pan như thư viện lớn. Nếu sau này cần, thay file này
   là đủ — `chart_data.py` phát ra định dạng trung lập, không dính tới thư viện.

   Màu lấy từ token của giao diện (--accent/--up/--down/--text/--muted/--border)
   nên tự đúng ở cả nền sáng lẫn nền tối.

   Vào: MPCharts.renderAll("charts-root", payload)
   ========================================================================== */
(function (global) {
  "use strict";

  /* Hệ toạ độ trong SVG. QUAN TRỌNG: chữ trong SVG co giãn theo tỉ lệ
     (bề rộng hiển thị ÷ W), nên một W cố định làm chữ bé tí ở thẻ hẹp và to
     quá ở thẻ rộng. Dùng HAI hệ: thẻ thường ~560px, thẻ chiếm cả hàng ~1120px —
     nhờ vậy chữ hiện ra gần đúng cỡ thật ở cả hai. */
  const W_NARROW = 560, W_WIDE = 1120, H = 205;
  let W = W_NARROW, PAD = null, PLOT = null;

  function useWidth(wide) {
    W = wide ? W_WIDE : W_NARROW;
    PAD = { t: 18, r: wide ? 60 : 52, b: 34, l: wide ? 66 : 58 };
    PLOT = { w: W - PAD.l - PAD.r, h: H - PAD.t - PAD.b };
  }
  useWidth(false);

  // Dải màu cho nhiều chuỗi. Hai màu đầu là màu thương hiệu; các màu sau đủ
  // khác nhau về sắc độ để phân biệt được cả khi in đen trắng.
  const COLORS = ["var(--accent)", "var(--up)", "#F0B429", "#9B7BFF", "#1FD1B8", "#E14040"];

  const esc = (s) => String(s == null ? "" : s)
    .replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  /* Số kiểu Việt Nam; dùng lại helper chung nếu có để cả trang thống nhất.
     LƯU Ý: trong nhiều file của dự án `M` là biến cục bộ trỏ window.MPChart,
     nên ở đây luôn viết `window.M` đầy đủ. */
  function fmt(v) {
    if (v == null || !isFinite(v)) return "—";
    if (window.M && typeof window.M.fmtVN === "function") {
      return window.M.fmtVN(v, Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2);
    }
    return v.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
  }

  /* Mốc trục "tròn" (1/2/5 × 10^n) — dễ đọc hơn chia đều máy móc. */
  function ticks(lo, hi, n) {
    if (!(hi > lo)) return [lo];
    const raw = (hi - lo) / (n || 5);
    const mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) || mag * 10;
    const out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(v);
    return out.length ? out : [lo, hi];
  }

  const nums = (arr) => arr.filter((v) => v != null && isFinite(v));

  /* Miền giá trị cho một tập chuỗi. Luôn kéo về 0 với biểu đồ cột — cột không
     bắt đầu từ 0 là cách phóng đại chênh lệch một cách vô tình. */
  function domainOf(series, zeroBased) {
    let vals = [];
    series.forEach((s) => s.data.forEach((v) => {
      if (Array.isArray(v)) vals.push(...nums(v));
      else if (v != null && isFinite(v)) vals.push(v);
    }));
    vals = nums(vals);
    if (!vals.length) return null;
    let lo = Math.min(...vals), hi = Math.max(...vals);
    if (zeroBased) { lo = Math.min(0, lo); hi = Math.max(0, hi); }
    if (lo === hi) { lo -= 1; hi += 1; }
    const pad = (hi - lo) * 0.08;
    return { lo: zeroBased && lo === 0 ? 0 : lo - pad, hi: hi + pad };
  }

  const yOf = (v, d) => PAD.t + PLOT.h - ((v - d.lo) / (d.hi - d.lo)) * PLOT.h;
  const xBand = (i, n) => PAD.l + (PLOT.w / n) * (i + 0.5);

  function axes(d, labels, right) {
    let g = `<line x1="${PAD.l}" y1="${PAD.t + PLOT.h}" x2="${PAD.l + PLOT.w}" `
      + `y2="${PAD.t + PLOT.h}" stroke="var(--border-hi)" stroke-width="1"/>`;
    ticks(d.lo, d.hi, 4).forEach((t) => {
      const y = yOf(t, d);
      if (y < PAD.t - 1 || y > PAD.t + PLOT.h + 1) return;
      g += `<line x1="${PAD.l}" y1="${y}" x2="${PAD.l + PLOT.w}" y2="${y}" `
        + `stroke="var(--border)" stroke-width="1"/>`
        + `<text x="${PAD.l - 8}" y="${y + 4}" text-anchor="end" font-size="11" `
        + `fill="var(--muted)">${esc(fmt(t))}</text>`;
      if (right) {
        g += `<text x="${PAD.l + PLOT.w + 8}" y="${y + 4}" font-size="11" `
          + `fill="var(--muted)">${esc(fmt(right.lo + (t - d.lo) / (d.hi - d.lo) * (right.hi - right.lo)))}</text>`;
      }
    });
    // Trục ngang: nhãn thưa dần khi nhiều điểm để chữ không chồng nhau.
    const step = Math.max(1, Math.ceil(labels.length / 9));
    labels.forEach((lb, i) => {
      if (i % step) return;
      g += `<text x="${xBand(i, labels.length)}" y="${PAD.t + PLOT.h + 18}" `
        + `text-anchor="middle" font-size="11" fill="var(--muted)">${esc(lb)}</text>`;
    });
    return g;
  }

  function legend(series) {
    if (series.length < 2) return "";
    return `<div class="cr-legend">` + series.map((s, i) =>
      `<span class="cr-lg"><i style="background:${s.color || COLORS[i % COLORS.length]}"></i>`
      + `${esc(s.name)}</span>`).join("") + `</div>`;
  }

  /* ------------------------------------------------------------ các kiểu vẽ */
  function drawBars(series, d, n, opts) {
    const grouped = !(opts && opts.stacked);
    const bw = (PLOT.w / n) * 0.7;
    const each = grouped ? bw / series.length : bw;
    let g = "";
    const acc = new Array(n).fill(0);
    series.forEach((s, si) => {
      const col = s.color || COLORS[si % COLORS.length];
      s.data.forEach((v, i) => {
        if (v == null || !isFinite(v)) return;
        const x = grouped
          ? xBand(i, n) - bw / 2 + si * each
          : xBand(i, n) - bw / 2;
        const base = grouped ? 0 : acc[i];
        const y0 = yOf(base, d), y1 = yOf(base + v, d);
        g += `<rect x="${x.toFixed(1)}" y="${Math.min(y0, y1).toFixed(1)}" `
          + `width="${each.toFixed(1)}" height="${Math.max(1, Math.abs(y1 - y0)).toFixed(1)}" `
          + `fill="${col}" opacity=".88" rx="1"/>`;
        if (!grouped) acc[i] += v;
      });
    });
    return g;
  }

  function drawLine(s, d, n, color) {
    let path = "", open = false, dots = "";
    s.data.forEach((v, i) => {
      if (v == null || !isFinite(v)) { open = false; return; }   // ngắt đường ở kỳ thiếu số
      const x = xBand(i, n), y = yOf(v, d);
      path += (open ? " L" : " M") + x.toFixed(1) + " " + y.toFixed(1);
      open = true;
      if (n <= 16) dots += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="2.6" fill="${color}"/>`;
    });
    return `<path d="${path.trim()}" fill="none" stroke="${color}" stroke-width="2" `
      + `stroke-linejoin="round" stroke-linecap="round"/>` + dots;
  }

  function drawBand(series, d, n) {
    // series[2].data = [[lo,hi], …] → vùng tô; series[1] = trung vị; series[0] = giá trị
    let g = "";
    const band = series.find((s) => s.kind === "band");
    if (band) {
      const pts = band.data.map((p, i) => Array.isArray(p) ? [xBand(i, n), yOf(p[0], d), yOf(p[1], d)] : null)
        .filter(Boolean);
      if (pts.length) {
        const top = pts.map((p) => `${p[0].toFixed(1)},${p[2].toFixed(1)}`).join(" ");
        const bot = pts.slice().reverse().map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
        g += `<polygon points="${top} ${bot}" fill="var(--accent)" opacity=".10"/>`;
      }
    }
    series.forEach((s, i) => {
      if (s.kind === "band") return;
      const col = s.color || COLORS[i % COLORS.length];
      g += s.kind === "line" && s.name === "Trung vị"
        ? `<path d="M${PAD.l} ${yOf(s.data[0], d).toFixed(1)} L${PAD.l + PLOT.w} `
          + `${yOf(s.data[0], d).toFixed(1)}" stroke="var(--muted)" stroke-width="1.4" `
          + `stroke-dasharray="5 4" fill="none"/>`
        : drawLine(s, d, n, col);
    });
    return g;
  }

  function drawWaterfall(s, d, n) {
    // Cột đầu và cột cuối đứng từ 0; các cột giữa nối tiếp nhau.
    let g = "", run = 0;
    const bw = (PLOT.w / n) * 0.62;
    s.data.forEach((v, i) => {
      if (v == null || !isFinite(v)) return;
      const last = i === s.data.length - 1;
      const from = (i === 0 || last) ? 0 : run;
      const to = (i === 0 || last) ? v : run + v;
      const y0 = yOf(from, d), y1 = yOf(to, d);
      const col = last ? "var(--accent)" : v >= 0 ? "var(--up)" : "var(--down)";
      g += `<rect x="${(xBand(i, n) - bw / 2).toFixed(1)}" y="${Math.min(y0, y1).toFixed(1)}" `
        + `width="${bw.toFixed(1)}" height="${Math.max(1, Math.abs(y1 - y0)).toFixed(1)}" `
        + `fill="${col}" opacity=".85" rx="1"/>`;
      if (!last && i > 0) run = to; else if (i === 0) run = v;
    });
    g += `<line x1="${PAD.l}" y1="${yOf(0, d).toFixed(1)}" x2="${PAD.l + PLOT.w}" `
      + `y2="${yOf(0, d).toFixed(1)}" stroke="var(--border-hi)" stroke-width="1"/>`;
    return g;
  }

  /* Tán xạ: dữ liệu là [{x, y, label, self}] — không có trục hạng mục.
     Dùng cho "ngành: P/E × ROE", chấm của chính mã được tô đậm và ghi tên. */
  function drawScatter(c) {
    const pts = (c.series[0] && c.series[0].data) || [];
    const xs = nums(pts.map((p) => p.x)), ys = nums(pts.map((p) => p.y));
    if (xs.length < 3) return "";
    const dx = { lo: Math.min(...xs), hi: Math.max(...xs) };
    const dy = { lo: Math.min(...ys), hi: Math.max(...ys) };
    if (dx.hi === dx.lo) dx.hi += 1;
    if (dy.hi === dy.lo) dy.hi += 1;
    const px = (v) => PAD.l + (v - dx.lo) / (dx.hi - dx.lo) * PLOT.w;
    const py = (v) => PAD.t + PLOT.h - (v - dy.lo) / (dy.hi - dy.lo) * PLOT.h;

    let g = axes(dy, [], null);
    ticks(dx.lo, dx.hi, 4).forEach((t) => {
      if (t < dx.lo || t > dx.hi) return;
      g += `<text x="${px(t).toFixed(1)}" y="${PAD.t + PLOT.h + 18}" text-anchor="middle" `
        + `font-size="11" fill="var(--muted)">${esc(fmt(t))}</text>`;
    });
    pts.forEach((p) => {
      if (p.x == null || p.y == null) return;
      const on = !!p.self;
      g += `<circle cx="${px(p.x).toFixed(1)}" cy="${py(p.y).toFixed(1)}" `
        + `r="${on ? 6 : 3.4}" fill="${on ? "var(--accent)" : "var(--muted)"}" `
        + `opacity="${on ? 1 : .55}"><title>${esc(p.label)}: ${fmt(p.x)} / ${fmt(p.y)}</title></circle>`;
      if (on) {
        g += `<text x="${(px(p.x) + 9).toFixed(1)}" y="${(py(p.y) - 8).toFixed(1)}" `
          + `font-size="11.5" font-weight="700" fill="var(--accent)">${esc(p.label)}</text>`;
      }
    });
    return g;
  }

  /* Bản đồ nhiệt: data là [{row, col, v}], `rows` là danh sách hàng. */
  function drawHeatmap(c) {
    const s = c.series[0] || {};
    const cells = s.data || [], rows = s.rows || [];
    const vals = nums(cells.map((x) => x.v));
    if (!vals.length || !rows.length) return "";
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const cw = PLOT.w / c.x.length, ch = Math.min(34, PLOT.h / rows.length);
    let g = "";
    rows.forEach((r, ri) => {
      g += `<text x="${PAD.l - 8}" y="${(PAD.t + ri * ch + ch / 2 + 4).toFixed(1)}" `
        + `text-anchor="end" font-size="11" fill="var(--muted)">${esc(r)}</text>`;
    });
    c.x.forEach((col, ci) => {
      g += `<text x="${(PAD.l + ci * cw + cw / 2).toFixed(1)}" y="${(PAD.t - 5).toFixed(1)}" `
        + `text-anchor="middle" font-size="11" fill="var(--muted)">${esc(col)}</text>`;
    });
    cells.forEach((cell) => {
      const ri = rows.indexOf(cell.row), ci = c.x.indexOf(cell.col);
      if (ri < 0 || ci < 0 || cell.v == null) return;
      const t = hi > lo ? (cell.v - lo) / (hi - lo) : 0.5;
      g += `<rect x="${(PAD.l + ci * cw + 1).toFixed(1)}" y="${(PAD.t + ri * ch + 1).toFixed(1)}" `
        + `width="${(cw - 2).toFixed(1)}" height="${(ch - 2).toFixed(1)}" rx="2" `
        + `fill="var(--accent)" opacity="${(0.12 + t * 0.78).toFixed(2)}">`
        + `<title>${esc(cell.row)} ${esc(cell.col)}: ${fmt(cell.v)}</title></rect>`
        + `<text x="${(PAD.l + ci * cw + cw / 2).toFixed(1)}" `
        + `y="${(PAD.t + ri * ch + ch / 2 + 4).toFixed(1)}" text-anchor="middle" `
        + `font-size="10.5" fill="var(--text)">${esc(fmt(cell.v))}</text>`;
    });
    return g;
  }

  /* ------------------------------------------------------------ một biểu đồ */
  function svgFor(c) {
    if (c.kind === "scatter") {
      const g = drawScatter(c);
      return g ? `<svg viewBox="0 0 ${W} ${H}" class="cr-svg" role="img" `
        + `aria-label="${esc(c.title)}">${g}</svg>` : "";
    }
    if (c.kind === "heatmap") {
      const g = drawHeatmap(c);
      return g ? `<svg viewBox="0 0 ${W} ${H}" class="cr-svg" role="img" `
        + `aria-label="${esc(c.title)}">${g}</svg>` : "";
    }
    const n = c.x.length;
    if (!n) return "";
    const left = c.series.filter((s) => s.axis !== "right");
    const right = c.series.filter((s) => s.axis === "right");
    const barLike = ["bar", "stacked-bar", "histogram", "waterfall", "bar+line"].includes(c.kind);

    if (c.kind === "waterfall") {
      const d = domainOf(c.series, true);
      if (!d) return "";
      return `<svg viewBox="0 0 ${W} ${H}" class="cr-svg" role="img" aria-label="${esc(c.title)}">`
        + axes(d, c.x, null) + drawWaterfall(c.series[0], d, n) + `</svg>`;
    }

    const dL = domainOf(left, barLike);
    if (!dL) return "";
    const dR = right.length ? domainOf(right, true) : null;

    let body = "";
    if (c.kind === "band") {
      body = drawBand(c.series, dL, n);
    } else {
      const bars = left.filter((s) => s.kind === "bar" || (!s.kind && barLike && c.kind !== "bar+line"));
      const lines = left.filter((s) => !bars.includes(s));
      if (bars.length) body += drawBars(bars, dL, n, { stacked: c.kind === "stacked-bar" });
      lines.forEach((s, i) => { body += drawLine(s, dL, n, s.color || COLORS[(bars.length + i) % COLORS.length]); });
      right.forEach((s, i) => {
        const col = s.color || COLORS[(left.length + i) % COLORS.length];
        body += s.kind === "bar"
          ? drawBars([s], dR, n, {}).replace(/opacity="\.88"/g, 'opacity=".35"')
          : drawLine(s, dR, n, col);
      });
    }

    // Chấm sự kiện (F2): mốc thời gian có công bố.
    let marks = "";
    (c.marks || []).forEach((m) => {
      const i = c.x.indexOf(m.date);
      if (i < 0) return;
      marks += `<line x1="${xBand(i, n).toFixed(1)}" y1="${PAD.t}" x2="${xBand(i, n).toFixed(1)}" `
        + `y2="${PAD.t + PLOT.h}" stroke="var(--muted)" stroke-width="1" opacity=".35"/>`
        + `<circle cx="${xBand(i, n).toFixed(1)}" cy="${PAD.t + 6}" r="3.4" fill="var(--accent)">`
        + `<title>${esc(m.date)} — ${esc(m.text)}</title></circle>`;
    });

    // Vùng bắt chuột: mỗi kỳ một ô trong suốt, hiện <title> gốc của SVG.
    let hit = "";
    c.x.forEach((lb, i) => {
      const vals = c.series.map((s) => {
        const v = s.data[i];
        return `${s.name}: ${Array.isArray(v) ? v.map(fmt).join("–") : fmt(v)}`;
      }).join("\n");
      hit += `<rect x="${(xBand(i, n) - PLOT.w / n / 2).toFixed(1)}" y="${PAD.t}" `
        + `width="${(PLOT.w / n).toFixed(1)}" height="${PLOT.h}" fill="transparent">`
        + `<title>${esc(lb)}\n${esc(vals)}</title></rect>`;
    });

    return `<svg viewBox="0 0 ${W} ${H}" class="cr-svg" role="img" aria-label="${esc(c.title)}">`
      + axes(dL, c.x, dR) + body + marks + hit + `</svg>`;
  }

  function timelineHTML(c) {
    const items = (c.series[0] && c.series[0].data) || [];
    return `<ol class="cr-timeline">` + items.map((it) =>
      `<li><time>${esc(it.date)}</time><span class="cr-tl-kind">${esc(it.kind)}</span>`
      + `<p>${esc(it.text)}</p></li>`).join("") + `</ol>`;
  }

  /* Chú thích do AI ghim lên kỳ cụ thể (D-3). Chỉ hiện kỳ ĐÃ QUA validator. */
  function annHTML(c) {
    const a = c.annotations || [];
    if (!a.length) return "";
    return `<ul class="cr-ann">` + a.map((x) =>
      `<li><b>${esc(x.period)}</b> ${esc(x.note)}</li>`).join("") + `</ul>`;
  }

  function cardHTML(c) {
    // Biểu đồ nhiều điểm hoặc dạng bảng thì chiếm cả hàng; còn lại xếp 2 cột.
    const wide = c.kind === "timeline" || c.kind === "price"
      || c.kind === "heatmap" || c.kind === "scatter" || (c.x || []).length > 20;
    useWidth(wide);                       // đặt hệ toạ độ TRƯỚC khi vẽ
    const inner = c.kind === "timeline" ? timelineHTML(c) : svgFor(c);
    if (!inner) return "";
    return `<figure class="cr-card${wide ? " cr-wide" : ""}" id="cr-${esc(c.id)}">
      <figcaption class="cr-head">
        <h4 class="cr-title">${esc(c.title)}</h4>
        <span class="cr-unit">${esc(c.unit || "")}</span>
      </figcaption>
      ${legend(c.series.filter((s) => s.kind !== "band"))}
      <div class="cr-plot">${inner}</div>
      ${c.history_note ? `<p class="cr-hist">${esc(c.history_note)}</p>` : ""}
      ${annHTML(c)}
      ${c.read_this ? `<details class="cr-read"><summary>Đọc biểu đồ này thế nào</summary>
        <p>${esc(c.read_this)}</p></details>` : ""}
      ${c.note ? `<p class="cr-note">${esc(c.note)}</p>` : ""}
      <p class="cr-src">Nguồn: ${esc(c.source || "market.db")}${
        c.narrated ? ` · lời dẫn AI cho “${esc(c.title_data || "")}”` : ""}</p>
    </figure>`;
  }

  function renderAll(hostId, payload, symbol) {
    const host = typeof hostId === "string" ? document.getElementById(hostId) : hostId;
    if (!host) return false;
    const charts = (payload && payload.charts) || [];
    if (!charts.length) {
      host.innerHTML = `<p class="cr-empty">Chưa đủ dữ liệu để dựng biểu đồ cho mã này.</p>`;
      return false;
    }
    const groups = payload.groups || [];
    const n = payload.narrated_count || 0;
    // LỖI ĐÃ SỬA: route /api/stock/<mã>/charts/narrate (D-3, gọi AI thật qua
    // local_api.ask để viết lời dẫn cho từng nhóm biểu đồ) đã tồn tại từ
    // trước nhưng KHÔNG có nút nào trên UI gọi tới — narrated_count luôn là 0
    // trừ khi ai đó tự curl route này bằng tay. Thêm nút thật ở đây, không
    // tự viết lời dẫn giả — bấm mới tốn 1 lượt AI, giống pattern "Nhờ AI đọc
    // bài này" đã dùng ở tab Tin & Sự kiện.
    const narrateBtn = symbol ? `
      <button type="button" class="cr-narrate-btn" id="cr-narrate-btn"
        onclick="MPCharts._narrate('${esc(symbol)}')">
        ${n ? "↻ Sinh lại lời dẫn AI" : "✦ Nhờ AI viết lời dẫn cho biểu đồ"}
      </button>` : "";
    host.innerHTML = groups.map((g) => {
      const cards = charts.filter((c) => c.group === g.key).map(cardHTML).join("");
      return cards ? `<section class="cr-group"><h3 class="cr-group-h">${esc(g.title)}</h3>`
        + `<div class="cr-grid">${cards}</div></section>` : "";
    }).join("")
      + `<p class="cr-foot">${esc(payload.note || "")}`
      + (n ? ` Lời dẫn của AI có ở ${n}/${charts.length} biểu đồ; số liệu luôn lấy `
           + `từ market.db, AI không sinh số.` : "")
      + `</p>`
      + `<div class="cr-narrate-row">${narrateBtn}<span id="cr-narrate-msg"></span></div>`;
    return true;
  }

  let _lastSymbol = null;

  async function load(hostId, symbol) {
    const host = typeof hostId === "string" ? document.getElementById(hostId) : hostId;
    if (!host) return false;
    _lastSymbol = symbol;
    host.innerHTML = `<p class="cr-empty">Đang dựng biểu đồ…</p>`;
    try {
      const r = await fetch(`/api/stock/${encodeURIComponent(symbol)}/charts`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      return renderAll(host, await r.json(), symbol);
    } catch (e) {
      host.innerHTML = `<p class="cr-empty">Không tải được biểu đồ (${esc(e.message)}).</p>`;
      return false;
    }
  }

  async function _narrate(symbol) {
    const btn = document.getElementById("cr-narrate-btn");
    const msg = document.getElementById("cr-narrate-msg");
    if (!btn) return;
    btn.disabled = true;
    const old = btn.textContent;
    btn.textContent = "⏳ AI đang viết (mỗi nhóm 1 lượt, có thể mất khoảng 1 phút)…";
    if (msg) msg.textContent = "";
    try {
      const r = await fetch(`/api/stock/${encodeURIComponent(symbol)}/charts/narrate`,
        { method: "POST" });
      const j = await r.json();
      if (!j.ok) throw new Error(j.msg || `HTTP ${r.status}`);
      // Nạp lại toàn bộ để card hiện đúng lời dẫn vừa sinh, không tự chèn
      // text vào DOM — mọi chữ trên trang phải đi qua đúng 1 đường: API.
      await load("charts-root", symbol);
    } catch (e) {
      btn.disabled = false;
      btn.textContent = old;
      if (msg) msg.textContent = `Không sinh được lời dẫn: ${esc(e.message)}`;
    }
  }

  global.MPCharts = { renderAll, load, cardHTML, _svgFor: svgFor, _narrate };
})(window);
