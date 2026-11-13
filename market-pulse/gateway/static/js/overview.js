/* Trang Tổng quan — luồng all-in-one 5 bước */
const STEP_ICONS = { pending: "○", running: "◐", done: "✔", error: "✖" };

/* Ảnh 5 + 10 · Tên bước cho mode Cơ bản: bỏ chữ nội bộ ("Python thuần", "phiên
   hội thoại"), nói bằng ngôn ngữ người dùng. Chuyên sâu giữ nguyên tên kỹ thuật. */
const STEP_NAME_BASIC = {
  "Thu thập + kỹ thuật (Python thuần)": "Thu thập dữ liệu thị trường",
  "Nạp ngữ cảnh vào phiên hội thoại": "Chuẩn bị dữ liệu cho AI",
  "Độ rộng & dòng tiền": "Thị trường mạnh hay yếu",
  "Kháng cự / hỗ trợ từng mã": "Vùng giá đáng chú ý",
  "Nguyên nhân + bằng chứng": "Vì sao thị trường biến động",
  "Rủi ro & thiếu dữ liệu": "Rủi ro cần biết",
  "Tổng hợp + điểm theo dõi": "Tổng hợp",
  "Rút gọn cho người mới": "Viết lại cho dễ hiểu",
};

function renderSteps(steps) {
  const basic = document.body.classList.contains("mode-basic");
  $("#overview-steps").classList.add("show");
  $("#overview-steps").innerHTML = steps.map(s => `
    <div class="step ${s.status}">
      <span class="st-icon">${s.status === "running" ? '<span class="spinner"></span>' : STEP_ICONS[s.status]}</span>
      <span class="st-name">${_esc(basic ? (STEP_NAME_BASIC[s.name] || s.name) : s.name)}</span>
      <span class="st-detail">${s.detail || ""}</span>
    </div>`).join("");
}

/* Ảnh 14 · id bằng chứng có dấu gạch/chấm (TT-ACB, E6810…) → id DOM an toàn.
   Dùng CHUNG cho cả nơi sinh anchor (kho bằng chứng) và nơi nhảy tới (cite.js). */
function _evAnchor(id) {
  return "ev-" + String(id || "").replace(/[^\w-]/g, "_");
}
window._evAnchor = _evAnchor;

/* Ảnh 11 · nhãn vị trí giá (từ tech_full) sang tiếng Việt gọn — bảng cũ ghi cả
   câu dài "vượt đỉnh (không còn kháng cự trên)" lặp đi lặp lại trong mọi dòng. */
const _POS_VI = { breakout: "vượt đỉnh", near_res: "sát kháng cự",
                  near_sup: "về hỗ trợ", mid: "giữa vùng" };

/* Nạp bộ chỉ báo theo nhu cầu (Lazy Load) khi mở phân tích S/R,
   tránh quét toàn bộ 1.543 mã ngay khi mở trang làm đơ server. */
window.__techFull = { items: {}, skipped: {} };
window.__techFullPromise = null;
function ensureTechFull(symbols) {
  if (window.__techFullPromise) return window.__techFullPromise;
  const syms = Array.isArray(symbols) && symbols.length ? `?symbols=${symbols.slice(0, 15).join(",")}` : "";
  window.__techFullPromise = fetch(`/api/tech_full${syms}`)
    .then(r => r.ok ? r.json() : null)
    .then(d => {
      if (d) {
        window.__techFull.items = Object.assign(window.__techFull.items || {}, d.items || {});
        window.__techFull.skipped = Object.assign(window.__techFull.skipped || {}, d.skipped || {});
      }
      return window.__techFull;
    })
    .catch(() => window.__techFull);
  return window.__techFullPromise;
}
window.ensureTechFull = ensureTechFull;

const _ID_SHAPE = /^(?:N|E|M|R-|TT-|CD-)[\w-]*$/;
function evidenceChips(ids, newsMap) {
  return (ids || []).map(raw => {
    const s = String(raw).replace(/[\[\]]/g, "").trim();
    // AI có thể trả "M2: tóm tắt tin" — tách id đứng đầu nếu có
    const head = s.split(":")[0].trim();
    const id = _ID_SHAPE.test(s) ? s : (_ID_SHAPE.test(head) ? head : null);
    if (id) {
      const n = newsMap[id];
      if (!n) return `<span class="evidence-chip missing" title="⚠ AI trích dẫn nguồn không tồn tại: ${_esc(id)}">${_esc(id)} ⚠</span>`;
      const tip = `(${fmtDateVN(n.date, false)}) ${n.symbol}: ${n.title}`;
      const inner = n.link
        ? `<a href="${_esc(n.link)}" target="_blank" rel="noopener">${_esc(id)}</a>`
        : _esc(id);
      return `<span class="evidence-chip" title="${_esc(tip)}">${inner}</span>`;
    }
    // không phải id → là mô tả dữ kiện của AI: chip trung tính, không cảnh báo
    return `<span class="evidence-chip" style="opacity:.75" title="dẫn chứng số liệu do AI nêu (không phải nguồn tin)">${_esc(s.length > 60 ? s.slice(0, 60) + "…" : s)}</span>`;
  }).join(" ");
}

/* Linkify mã bằng chứng [N1][TT-ACB]... trong text tự do, kèm cảnh báo id lạ. */
function linkEvidence(text, newsMap) {
  return _esc(String(text || "")).replace(/\[((?:N|E|M|R-|TT-|CD-)[\w-]*)\]/g, (m, id) => {
    const n = newsMap[id];
    if (!n) return `<span class="evidence-chip missing" title="⚠ nguồn không tồn tại">${id} ⚠</span>`;
    return `<span class="evidence-chip" title="${_esc(`(${fmtDateVN(n.date, false)}) ${n.symbol}: ${n.title}`)}">${id}</span>`;
  });
}

/* Ảnh 10 · Bản rút gọn (AI lượt 7) cho mode Cơ bản: ý chính ≤2 câu + tối đa 3
   gạch đầu dòng, kèm nút bung ra bản đầy đủ. Phần nào AI không rút gọn được thì
   `brief` rỗng → hiện thẳng bản đầy đủ (không bao giờ để trống). */
function briefBlock(brief) {
  if (!brief || (!brief.y_chinh && !(brief.gach_dau_dong || []).length)) return null;
  const li = (brief.gach_dau_dong || [])
    .map(t => `<li class="neu">${_esc(t)}</li>`).join("");
  return `<p class="brief-gist">${_esc(brief.y_chinh || "")}</p>`
       + (li ? `<ul class="auto-notes">${li}</ul>` : "");
}

/* Một card cho 1 phần: hiện skeleton khi đang chạy, nội dung khi xong, đỏ khi lỗi. */
function partCard(title, step, bodyFn, brief) {
  const status = step?.status || "pending";
  const badge = step?.detail ? `<span class="part-badge">${_esc(step.detail)}</span>` : "";
  if (status === "error") {
    return `<div class="card part-error"><h3>${title}</h3>
      <p class="warn-banner">Phần này lỗi: ${_esc(step?.detail || "?")}. Các phần khác vẫn hiển thị.</p></div>`;
  }
  if (status !== "done") {
    // phần đang chạy: giữ spinner ở tiêu đề (đây là bước AI đang xử lý) + skeleton thân đúng hình
    return `<div class="card part-pending"><h3>${title} <span class="spinner"></span></h3>
      ${skel("text", { rows: 3 })}</div>`;
  }
  const briefHtml = briefBlock(brief);
  if (!briefHtml) return `<div class="card"><h3>${title} ${badge}</h3>${bodyFn()}</div>`;
  // có bản rút gọn → 2 tầng: Cơ bản thấy gọn + nút bung; Chuyên sâu thấy đầy đủ.
  return `<div class="card ai-sec"><h3>${title} ${badge}</h3>
    <div class="ai-brief">${briefHtml}
      <button type="button" class="btn-expand" aria-expanded="false">Xem chuyên sâu ▾</button>
    </div>
    <div class="ai-full">${bodyFn()}</div>
  </div>`;
}

/* Bung / thu bản đầy đủ (uỷ quyền 1 lần cho cả trang). */
document.addEventListener("click", (e) => {
  const btn = e.target.closest && e.target.closest(".btn-expand");
  if (!btn) return;
  const sec = btn.closest(".ai-sec");
  const open = sec.classList.toggle("show-full");
  btn.setAttribute("aria-expanded", String(open));
  btn.textContent = open ? "Thu gọn ▴" : "Xem chuyên sâu ▾";
});

// ---- Chế độ thị trường (WS-B): badge + panel tín hiệu + chart RS ngành ----
const REGIME_COLOR = {
  "Uptrend": "#16a34a", "Phục hồi": "#65a30d", "Sideways": "#ca8a04",
  "Suy yếu": "#ea580c", "Downtrend": "#dc2626",
};

function regimeBadgeHtml(reg) {
  if (!reg?.available) return "";
  const c = REGIME_COLOR[reg.label] || "#64748b";
  return `<span class="mode-badge" style="background:${c};color:#fff"
    title="Điểm ${reg.score >= 0 ? "+" : ""}${reg.score}/${reg.max_score} tín hiệu">
    ${_esc(reg.label)} ${reg.score >= 0 ? "+" : ""}${reg.score}/${reg.max_score}</span>`;
}

function regimePanelHtml(reg, liq) {
  if (!reg?.available) return "";
  const rows = (reg.signals || []).map(s => {
    const mark = s.dat === true ? "✓" : (s.dat === false ? "✗" : "–");
    const col = s.dat === true ? "var(--good,#16a34a)" : (s.dat === false ? "var(--danger,#dc2626)" : "#94a3b8");
    return `<div class="fact-row">
      <span style="color:${col};font-weight:700;width:18px">${mark}</span>
      <span class="flabel">${_esc(s.ten)}</span>
      <span class="fval">${_esc(s.chi_tiet)}</span></div>`;
  }).join("");
  const liqLine = liq?.available
    ? `<p style="margin:8px 0 0;font-size:13px;color:var(--muted,#64748b)">
        Tập trung thanh khoản: top-10 mã chiếm <b>${liq.top10_pct}%</b> GTGD toàn thị trường
        (HHI ${Math.round(liq.hhi)}). ${_esc(liq.note || "")}</p>` : "";
  // §12: nhiệt kế thị trường — regime score (−max..+max) → 0–100 (phải = thuận lợi).
  const thermoId = "regime-thermo-" + Math.random().toString(36).slice(2, 7);
  const rows2 = rows;   // bảng tín hiệu chi tiết (Chuyên sâu)
  const bar = `<div id="${thermoId}"></div>`;
  const html = `<details class="card" style="margin-top:12px" open>
    <summary style="font-weight:700">Nhiệt kế thị trường (${reg.score >= 0 ? "+" : ""}${reg.score}/${reg.max_score})</summary>
    <p style="margin:6px 0 8px;font-size:12.5px;color:var(--muted,#64748b)">${_esc(reg.note || "")}</p>
    ${bar}
    <div data-advanced>${rows2}${liqLine}</div></details>`;
  // vẽ bar sau khi HTML gắn vào DOM
  setTimeout(() => {
    const box = document.getElementById(thermoId);
    if (!box || !window.MPChart) return;
    const max = reg.max_score || 5;
    const val = Math.max(0, Math.min(100, (reg.score + max) / (2 * max) * 100));
    const chips = (reg.signals || []).slice(0, 3).map(s => ({
      t: s.ten, kind: s.dat === true ? "ok" : s.dat === false ? "bad" : "neu" }));
    MPChart.mpBar(box, { value: val, labelLeft: "kém thuận lợi", labelRight: "thuận lợi hơn",
      verdict: reg.label, reasons: chips });
  }, 0);
  return html;
}

function rsChartHtml(rot) {
  if (!rot?.available || !rot.series?.length) return "";
  // chỉ top 6 ngành theo |RS gần nhất| cho đỡ rối
  const top = rot.series.slice(0, 6);
  const weeks = rot.weeks || [];
  const flat = top.flatMap(s => s.rs.filter(v => v !== null));
  if (!flat.length) return "";
  const lo = Math.min(...flat, 0), hi = Math.max(...flat, 0);
  const W = 640, H = 220, PL = 44, PR = 96, PT = 12, PB = 26;
  const x = i => PL + (W - PL - PR) * (weeks.length > 1 ? i / (weeks.length - 1) : 0.5);
  const y = v => PT + (H - PT - PB) * (1 - (v - lo) / (hi - lo || 1));
  const palette = ["#2563eb", "#16a34a", "#dc2626", "#ca8a04", "#9333ea", "#0891b2"];
  const zero = y(0);
  const lines = top.map((s, si) => {
    const pts = s.rs.map((v, i) => v === null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)
      .filter(Boolean).join(" ");
    const lastI = s.rs.length - 1;
    const lastV = s.rs_last;
    const col = palette[si % palette.length];
    const lbl = lastV !== null
      ? `<text x="${(W - PR + 4).toFixed(1)}" y="${(y(lastV) + 4).toFixed(1)}" font-size="11" fill="${col}">${_esc(secVI(s))} ${fmtPctSigned(lastV, 1)}</text>`
      : "";
    return `<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="2"/>${lbl}`;
  }).join("");
  const xlabels = weeks.map((w, i) =>
    (i % 3 === 0 || i === weeks.length - 1)
      ? `<text x="${x(i).toFixed(1)}" y="${H - 8}" font-size="10" fill="#94a3b8" text-anchor="middle">${_esc(w.slice(5))}</text>` : ""
  ).join("");
  return `<details class="card" style="margin-top:12px">
    <summary style="font-weight:700">Luân chuyển ngành — Sức mạnh tương đối (RS) 12 tuần</summary>
    <p style="margin:6px 0;font-size:12.5px;color:var(--muted,#64748b)">
      RS = trung vị return 20 phiên của ngành − VNINDEX cùng kỳ. Dương = khỏe hơn thị trường. Top 6 ngành theo |RS|.</p>
    <svg viewBox="0 0 ${W} ${H}" style="width:100%;height:auto">
      <line x1="${PL}" y1="${zero.toFixed(1)}" x2="${W - PR}" y2="${zero.toFixed(1)}" stroke="#cbd5e1" stroke-dasharray="4 3"/>
      <text x="${PL - 4}" y="${(zero + 3).toFixed(1)}" font-size="10" fill="#94a3b8" text-anchor="end">0</text>
      ${lines}${xlabels}
    </svg></details>`;
}

/* B12(c): đoạn văn AI dài (>~230 ký tự) tự cắt + nút "Xem thêm ▾". htmlContent
   đã là HTML an toàn (đã qua linkEvidence/_esc). Đo theo text thuần để quyết định. */
let _clampSeq = 0;
function clampText(htmlContent, plainLen, limit = 230) {
  if (plainLen == null) {
    const tmp = htmlContent.replace(/<[^>]+>/g, "");
    plainLen = tmp.length;
  }
  if (plainLen <= limit) return htmlContent;
  const id = "clamp-" + (++_clampSeq);
  return `<span class="clamp-wrap"><input type="checkbox" class="clamp-cb" id="${id}">
    <span class="clamp-body">${htmlContent}</span>
    <label class="clamp-more" for="${id}">Xem thêm ▾</label></span>`;
}

/* B12(b): tách mã CK đứng đầu 1 dòng đối chiếu (VD "FPT: ..."). Trả {sym, rest}. */
function _leadSymbol(text) {
  const m = String(text || "").match(/^\s*([A-Z]{3})\s*[:\-–]\s*(.+)$/s);
  return m ? { sym: m[1], rest: m[2] } : null;
}

/* B3: danh sách mã dài KHÔNG nhét vào .kpi .sub (vỡ layout). Trả về:
   dòng phụ = "N mã" + <details> chip 12 mã đầu + "+K nữa", mỗi chip link nội bộ. */
function symChips(syms, emptyLabel) {
  const list = (syms || []).filter(Boolean);
  if (!list.length) return `<span class="sub">${_esc(emptyLabel || "không có")}</span>`;
  const shown = list.slice(0, 12);
  const rest = list.length - shown.length;
  const chips = shown.map(s =>
    `<a class="sym-chip" href="/co-phieu/${encodeURIComponent(s)}">${_esc(s)}</a>`).join("");
  return `<details class="sym-more"><summary>${list.length} mã · xem ▸</summary>
    <div class="sym-chips">${chips}${rest > 0 ? `<span class="sym-chip more">+${rest} nữa</span>` : ""}</div>
  </details>`;
}

function renderOverviewResult(job) {
  const parts = job.parts || {};
  const steps = job.steps || [];
  const newsMap = {};
  (job.data?.news || []).forEach(n => newsMap[n.id] = n);
  (job.data?.flows || []).forEach(n => newsMap[n.id] = n);
  (job.data?.rss || []).forEach(n => newsMap[n.id] = n);
  (job.data?.market_news || []).forEach(n => newsMap[n.id] = { ...n, symbol: n.press || "thị trường" });
  const board = job.data?.board, tech = job.data?.technical;
  const mkt = job.data?.market || {};
  const src = job.data?.sources || {};

  // ---- KPI + nguồn/tuổi dữ liệu ----
  const boardSub = board?.live ? '<span class="dot-live"></span> bảng giá LIVE'
    : `<span class="dot-cache"></span> cache${src.board?.as_of ? " · " + _formatTs(src.board.as_of) : ""}`;
  const boardStale = !board?.live;
  const mb = mkt.breadth || {};
  const kpis =
    kpi("Toàn thị trường", mb.n_symbols ? `${fmtVN(mb.pct_above_ma20, 0)}%` : "—",
        mb.n_symbols ? `mã trên MA20 · ${fmtVN(mb.n_symbols, 0)} mã HOSE+HNX` : "chưa có dữ liệu P6",
        ((mb.pct_above_ma20 || 0) >= 50 ? "good" : "warn") + " hero") +
    kpi("Độ rộng phiên", board?.breadth ? `${board.breadth.up}▲ ${board.breadth.down}▼` : "—",
        boardSub, boardStale ? "warn" : "blue") +
    kpi("Khối ngoại ròng", board ? fmtVN(board.foreign_net_total, 0) : "—",
        "cổ phiếu, toàn bảng", board?.foreign_net_total >= 0 ? "good" : "warn") +
    kpi("Sát kháng cự / về hỗ trợ", tech ? `${tech.sr_at_resistance.length} / ${tech.sr_at_support.length}` : "—",
        "mã · xem danh sách dưới", "warn") +
    kpi("Vượt đỉnh (breakout)", tech ? tech.sr_breakout.length : "—",
        tech && tech.sr_breakout.length ? "mã · xem danh sách dưới" : "không mã nào", "good");

  // B3: danh sách mã dài tách khỏi card KPI → panel <details> chip dưới hàng KPI.
  const symLists = tech ? `<div class="sym-lists">
      <div class="sym-list-item"><span class="sll num-down">Sát kháng cự</span> ${symChips(tech.sr_at_resistance, "không mã nào")}</div>
      <div class="sym-list-item"><span class="sll num-ref">Về hỗ trợ</span> ${symChips(tech.sr_at_support, "không mã nào")}</div>
      <div class="sym-list-item"><span class="sll num-up">Vượt đỉnh</span> ${symChips(tech.sr_breakout, "không mã nào")}</div>
    </div>` : "";

  // ---- banner cảnh báo trích dẫn sai ----
  const badCites = job.invalid_citations || [];
  const citeBanner = badCites.length
    ? `<div class="warn-banner">⚠ AI trích dẫn ${badCites.length} mã bằng chứng không tồn tại: ${badCites.map(_esc).join(", ")}. Đã đánh dấu đỏ trong nội dung.</div>`
    : "";

  // ---- phần 2: độ rộng & dòng tiền ----
  const p2 = parts.cung_cau || {};
  const cungCauBody = () => `
    <ul class="ov-list">${(p2.cung_cau || []).map(x => `<li>${linkEvidence(x, newsMap)}</li>`).join("")}</ul>
    <p><b>Độ rộng:</b> ${linkEvidence(p2.do_rong_thi_truong || "—", newsMap)}</p>
    <p><b>Khối ngoại:</b> ${linkEvidence(p2.dong_tien_khoi_ngoai || "—", newsMap)}</p>`;

  // ---- phần 3: kháng cự / hỗ trợ ----
  const p3 = parts.khang_cu_ho_tro || {};
  const posColor = p => p === "sát kháng cự" ? "var(--warn)" :
    p === "về hỗ trợ" ? "var(--accent)" :
    (p || "").startsWith("vượt đỉnh") ? "var(--accent2)" : "var(--muted)";
  // B8: fmtVN thống nhất dấu phẩy/chấm; mã vượt đỉnh → "không còn KC trên".
  const brokeOut = x => (x.position || "").startsWith("vượt đỉnh");
  const srCell = (val, distPct, sign) => val == null ? "—"
    : `${fmtVN(val, 2)} <span style="color:var(--muted)">(${sign}${fmtVN(distPct, 1)}%)</span>`;
  /* Ảnh 11 · Bù chỉ báo còn thiếu từ /api/tech_full (tính từ market.db cho 1.541
     mã) — trước đây bảng này nhiều ô "—" vì subset cũ không có RSI/S-R cho mọi mã.
     Mã thật sự thiếu lịch sử thì hiện "—" kèm TOOLTIP LÝ DO, không im lặng. */
  const TF = window.__techFull || { items: {}, skipped: {} };
  const _pad = (x) => {
    const t = TF.items[x.symbol];
    if (!t) return x;
    return {
      ...x,
      close: x.close ?? t.price,
      rsi14: x.rsi14 ?? t.rsi14,
      nearest_support: x.nearest_support ?? (t.sr.support[0] ?? null),
      nearest_resistance: x.nearest_resistance ?? (t.sr.resistance[0] ?? null),
      dist_support_pct: x.dist_support_pct ?? (t.sr.support[0]
        ? (t.price / t.sr.support[0] - 1) * 100 : null),
      dist_resistance_pct: x.dist_resistance_pct ?? (t.sr.resistance[0]
        ? (t.sr.resistance[0] / t.price - 1) * 100 : null),
      vbp_nodes: (x.vbp_nodes && x.vbp_nodes.length) ? x.vbp_nodes
        : (t.vbp || []).map(p => ({ price: p })),
      position: x.position || _POS_VI[t.pos] || "",
    };
  };
  const _why = (sym) => TF.skipped[sym] ? ` title="${_esc(TF.skipped[sym])}"` : "";
  const techRows = (tech?.symbols || []).slice(0, 12).map(_pad).map(x => `<tr>
    <td><b>${_esc(x.symbol)}</b></td><td class="num-mono">${fmtVN(x.close, 2)}</td>
    <td style="color:${posColor(x.position)}">${_esc(x.position)}</td>
    <td${x.nearest_support == null ? _why(x.symbol) : ""}>${srCell(x.nearest_support, x.dist_support_pct, "-")}</td>
    <td>${brokeOut(x) ? '<span style="color:var(--muted)">không còn KC trên</span>' : srCell(x.nearest_resistance, x.dist_resistance_pct, "+")}</td>
    <td>${(x.vbp_nodes || []).map(n => fmtVN(n.price, 2)).join(", ") || "—"}</td>
    <td${x.rsi14 == null ? _why(x.symbol) : ""}>${x.rsi14 != null ? fmtVN(x.rsi14, 0) : "—"}</td>
    <td class="num-mono" style="color:${x.chg_20d_pct >= 0 ? "var(--accent2)" : "var(--danger)"}">${fmtPctSigned(x.chg_20d_pct, 1)}</td></tr>`).join("");
  const srBody = () => `
    <ul class="ov-list">${(p3.khang_cu_ho_tro || []).map(x => `<li>${linkEvidence(x, newsMap)}</li>`).join("")}</ul>
    <div class="table-wrap"><table class="mini-table">
      <tr><th>Mã</th><th>Giá</th><th>Vị trí</th><th>Hỗ trợ gần</th><th>Kháng cự gần</th><th>Vùng KL dày</th><th>RSI</th><th>20 phiên</th></tr>
      ${techRows}</table></div>`;

  // ---- phần 4: nguyên nhân + đối chiếu ----
  const p4 = parts.nguyen_nhan || {};
  // Ảnh 13: schema mới có 'co_che' (chuỗi tác động 2-3 câu), 'phan_de' (dữ kiện
  // ngược chiều) và 'do_tin_cay_vi_sao'. Vẫn đọc được job cũ (chỉ có 'ly_giai').
  const reasons = (p4.nguyen_nhan || []).map(n => {
    const than = n.co_che || n.ly_giai || "";
    const conf = n.do_tin_cay
      ? `<span class="conf ${confClass(n.do_tin_cay)}" title="${_esc(n.do_tin_cay_vi_sao
          || "phân loại theo loại nguồn (tin gốc / mô hình / AI), không phải đo lường")}">${_esc(n.do_tin_cay)}</span>`
      : "";
    const phanDe = n.phan_de
      ? `<div class="r-counter"><b>Dữ kiện ngược chiều:</b> ${linkEvidence(n.phan_de, newsMap)}</div>`
      : "";
    const why = n.do_tin_cay_vi_sao
      ? `<div class="r-why" data-advanced>Vì sao ${_esc(String(n.do_tin_cay || "").toLowerCase())}: ${_esc(n.do_tin_cay_vi_sao)}</div>`
      : "";
    return `<div class="reason-row">
      <div class="r-obs">↳ ${_esc(n.quan_sat || "")}</div>
      <div>${clampText(linkEvidence(than, newsMap), than.length)} ${evidenceChips(n.bang_chung, newsMap)} ${conf}</div>
      ${phanDe}${why}
    </div>`;
  }).join("");
  // B12(b): dòng đối chiếu bắt đầu bằng mã CK → card mini (logo + mã + nội dung).
  const crossCheck = (p4.doi_chieu_luong_khac || []).map(n => {
    const lead = _leadSymbol(n.noi_dung);
    if (lead) {
      const logo = window.MPChart ? MPChart.symLogoHTML(lead.sym) : "";
      return `<div class="xcheck-card">
        <a class="xcheck-head" href="/co-phieu/${encodeURIComponent(lead.sym)}">${logo}<b>${_esc(lead.sym)}</b></a>
        <div class="xcheck-body">${linkEvidence(lead.rest, newsMap)} ${evidenceChips(n.bang_chung, newsMap)}</div>
      </div>`;
    }
    return `<div class="reason-row">${linkEvidence(n.noi_dung, newsMap)} ${evidenceChips(n.bang_chung, newsMap)}</div>`;
  }).join("");
  const hasCardX = (p4.doi_chieu_luong_khac || []).some(n => _leadSymbol(n.noi_dung));
  const reasonBody = () => `${reasons || "—"}
    <h4 style="margin-top:12px">Đối chiếu luồng khác (Bảng giá / Crawl Data)</h4>
    ${crossCheck
      ? (hasCardX ? `<div class="xcheck-grid">${crossCheck}</div>` : crossCheck)
      : "<p class='disclaimer'>Chưa có kết quả đối chiếu.</p>"}`;

  // ---- phần 5: rủi ro & thiếu dữ liệu ----
  const p5 = parts.rui_ro || {};
  const risks = (p5.rui_ro_tiem_an || []).map(n => `
    <div class="reason-row">${clampText(linkEvidence(n.rui_ro, newsMap), (n.rui_ro || "").length)} ${evidenceChips(n.bang_chung, newsMap)}
      <span class="conf thap" title="phân loại theo loại nguồn, không phải đo lường">${_esc(n.muc_do || "")}</span></div>`).join("");
  const riskBody = () => `${risks || "—"}
    <h4 style="margin-top:12px">Thiếu dữ liệu</h4>
    <ul class="ov-list">${(p5.thieu_du_lieu || []).map(x => `<li>${_esc(x)}</li>`).join("") || "<li>—</li>"}</ul>`;

  // ---- phần 6: tổng hợp ----
  const p6 = parts.summary || {};
  // B2: AI đôi khi trả điểm nhấn dạng OBJECT {y|text|noi_dung, bang_chung|evidence[]}
  // thay vì string → String(obj) = "[object Object]". Chuẩn hóa phòng thủ 2 đầu.
  const dnItem = (d) => {
    if (d && typeof d === "object" && !Array.isArray(d)) {
      const txt = d.y || d.text || d.noi_dung || d.diem || "";
      const ev = d.bang_chung || d.evidence || d.chung_cu;
      return `${linkEvidence(txt, newsMap)} ${ev ? evidenceChips(ev, newsMap) : ""}`;
    }
    return linkEvidence(d, newsMap);
  };
  const summaryBody = () => `
    <p style="font-size:14.5px;line-height:1.75">${linkEvidence(p6.tong_quan || "", newsMap)}</p>
    <ul class="ov-list">${(p6.diem_nhan || []).map(d => `<li>${dnItem(d)}</li>`).join("")}</ul>
    <h4 style="margin-top:12px">Theo dõi tuần tới</h4>
    <ul class="ov-list">${(p6.theo_doi || []).map(x => `<li>${dnItem(x)}</li>`).join("")}</ul>`;

  // ---- kho bằng chứng ----
  const evid = [...(job.data?.market_news || []).map(n => ({ ...n, symbol: "thị trường", type: "tin thị trường" })),
                ...(job.data?.flows || []), ...(job.data?.news || []), ...(job.data?.rss || [])].map(n => `
    <div class="fact-row ev-row" id="${_evAnchor(n.id)}" data-ev-id="${_esc(n.id)}">
      <span class="fid">${_esc(n.id)}</span>
      <span class="flabel">${_esc(n.symbol)} · ${_esc(fmtDateVN(n.date, false))}</span>
      <span class="fval">${n.link ? `<a href="${_esc(n.link)}" target="_blank" rel="noopener">${_esc(n.title)}</a>` : _esc(n.title)}</span>
      <span class="conf ${String(n.id).startsWith("TT") || String(n.id).startsWith("CD") ? "trung" : "cao"}">${_esc(n.type)}</span>
      ${n.link ? `<a class="ev-src" href="${_esc(n.link)}" target="_blank" rel="noopener">Mở nguồn →</a>` : ""}
    </div>`).join("");

  const title = _esc(p6.tieu_de || "Báo cáo tổng quan thị trường");
  const regimeBadge = regimeBadgeHtml(job.data?.regime);
  const regimePanel = regimePanelHtml(job.data?.regime, job.data?.liquidity_concentration);
  const rsChart = rsChartHtml(job.data?.rotation);
  $("#overview-result").innerHTML = `
    <div class="copilot-block">
      <div class="ov-title">${title}
        ${regimeBadge}
        <span class="mode-badge">${_esc(job.transport || "")}</span></div>
      ${regimePanel}
      ${rsChart}
      ${citeBanner}
      <div class="kpi-row" style="margin-top:14px">${kpis}</div>
      ${symLists}
      ${partCard("Tổng hợp", steps[6], summaryBody, p6.brief)}
      ${partCard("Độ rộng & dòng tiền", steps[2], cungCauBody, job.parts?.cung_cau?.brief)}
      ${partCard("Kháng cự / Hỗ trợ / VBP", steps[3], srBody, job.parts?.khang_cu_ho_tro?.brief)}
      ${partCard("Nguyên nhân (kèm bằng chứng)", steps[4], reasonBody, job.parts?.nguyen_nhan?.brief)}
      ${partCard("Rủi ro & thiếu dữ liệu", steps[5], riskBody, job.parts?.rui_ro?.brief)}
      <details class="facts-panel card">
        <summary>Kho bằng chứng — ${(job.data?.flows || []).length} luồng khác + ${(job.data?.news || []).length} tin CBTT + ${(job.data?.rss || []).length} tin RSS</summary>
        ${evid}</details>
      <div class="disclaimer">${_esc(p6.disclaimer || "Thông tin giáo dục, không phải khuyến nghị đầu tư.")}</div>
    </div>`;
}

let overviewTimer = null;
const OV_JOB_KEY = "mp_overview_job";  // lưu job_id để tab chuyển đi/về không mất kết quả

/* Bám theo 1 job: poll status tới khi xong, render kết quả. Dùng cho cả
   lần chạy mới lẫn lần khôi phục sau khi quay lại tab. */
function trackOverviewJob(job_id) {
  const btn = $("#overview-btn");
  btn.disabled = true;
  clearInterval(overviewTimer);
  const poll = async () => {
    let j;
    try {
      const res = await fetch(`/api/overview/status/${job_id}`);
      if (res.status === 404) {           // gateway đã restart → job không còn
        clearInterval(overviewTimer);
        localStorage.removeItem(OV_JOB_KEY);
        btn.disabled = false;
        return;
      }
      j = await res.json();
    } catch (_) { return; }               // lỗi mạng tạm thời → thử lại lần sau
    renderSteps(j.steps);
    // Render dần: chừng nào đã thu thập xong dữ liệu (bước 0) thì vẽ các card,
    // mỗi phần tự hiện skeleton/nội dung/lỗi theo trạng thái step của nó.
    if (j.data && (j.steps?.[0]?.status === "done")) {
      renderOverviewResult(j);
    }
    if (j.status === "done" || j.status === "error") {
      clearInterval(overviewTimer);
      btn.disabled = false;
      if (j.status === "error" && !j.data)
        $("#overview-result").innerHTML =
          `<div class="warn-banner">Lỗi luồng phân tích: ${_esc(j.error || "?")}</div>`;
    }
  };
  poll();                                 // chạy ngay 1 lần (khôi phục kết quả tức thì)
  overviewTimer = setInterval(poll, 2500);
}

async function startOverview() {
  const btn = $("#overview-btn");
  btn.disabled = true;
  $("#overview-result").innerHTML = "";
  ensureTechFull(); // nạp song song với tiến trình AI
  try {
    const r = await fetch("/api/overview/start", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ prefer: "auto" }),
    });
    const { job_id } = await r.json();
    localStorage.setItem(OV_JOB_KEY, job_id);   // nhớ để khôi phục khi quay lại tab
    trackOverviewJob(job_id);
  } catch (e) {
    btn.disabled = false;
    $("#overview-result").innerHTML = `<div class="warn-banner">Lỗi: ${e.message}</div>`;
  }
}
$("#overview-btn").addEventListener("click", startOverview);

/* Khôi phục kết quả Tổng quan gần nhất khi mở lại trang (chuyển tab rồi về). */
(function restoreOverview() {
  const job_id = localStorage.getItem(OV_JOB_KEY);
  if (job_id) trackOverviewJob(job_id);
})();

async function refreshCdpStatus() {
  try {
    const s = await (await fetch("/api/gemini/cdp/status")).json();
    const el = $("#cdp-status");
    const L = s.local_api || {};
    // Kênh MẶC ĐỊNH nay là server AI local (:4000). Trình duyệt/CDP chỉ còn là
    // dự phòng, nên chỉ báo khi kênh local chưa dùng được.
    if (L.has_key && L.up) {
      el.textContent = "kênh AI: server local — không tốn phí API";
      el.classList.remove("offline");
    } else if (s.running && s.logged_in) {
      el.textContent = "kênh AI: trình duyệt (dự phòng)";
      el.classList.remove("offline");
    } else if (L.has_key && !L.up) {
      el.textContent = "kênh AI: server local chưa bật";
      el.classList.add("offline");
    } else if (s.running) {
      el.textContent = "kênh AI: trình duyệt đang mở, chưa đăng nhập";
    } else {
      el.textContent = "kênh AI: tự động";
    }
  } catch (_) { /* gateway chưa sẵn sàng */ }
}
$("#cdp-btn").addEventListener("click", async () => {
  $("#cdp-btn").disabled = true;
  await fetch("/api/gemini/cdp/start", { method: "POST" });
  setTimeout(() => { refreshCdpStatus(); $("#cdp-btn").disabled = false; }, 6000);
});
refreshCdpStatus();
setInterval(refreshCdpStatus, 15000);

/* ==========================================================================
   Heatmap toàn cảnh thị trường — treemap squarified thuần JS (không thư viện)
   Ô = mã · diện tích = vốn hóa · màu = %phiên · nhóm theo ngành.
   ========================================================================== */

/* Squarify (Bruls et al.): chia hình chữ nhật theo trọng số, giữ ô gần vuông. */
function squarify(items, x, y, w, h) {
  const out = [];
  let rest = items.slice();
  while (rest.length) {
    const total = rest.reduce((s, it) => s + it._w, 0);
    const vertical = w < h;                 // cạnh ngắn để xếp hàng hiện tại
    const side = vertical ? w : h;
    let row = [], rowSum = 0, bestRatio = Infinity;
    for (let i = 0; i < rest.length; i++) {
      const cand = rest[i];
      const sum = rowSum + cand._w;
      const rowLen = (sum / total) * (vertical ? h : w);
      // tỉ lệ xấu nhất trong hàng nếu thêm cand
      let worst = 0;
      for (const it of [...row, cand]) {
        const cellLen = (it._w / sum) * side;
        worst = Math.max(worst, rowLen / cellLen, cellLen / rowLen);
      }
      if (worst > bestRatio) break;         // thêm nữa chỉ xấu đi → chốt hàng
      row.push(cand); rowSum = sum; bestRatio = worst;
    }
    const rowLen = (rowSum / total) * (vertical ? h : w);
    let off = 0;
    for (const it of row) {
      const cellLen = (it._w / rowSum) * side;
      out.push(vertical
        ? { ...it, x: x + off, y, w: cellLen, h: rowLen }
        : { ...it, x, y: y + off, w: rowLen, h: cellLen });
      off += cellLen;
    }
    if (vertical) { y += rowLen; h -= rowLen; } else { x += rowLen; w -= rowLen; }
    rest = rest.slice(row.length);
  }
  return out;
}

function heatColor(p) {
  // -3%..+3% → đỏ..xám..xanh (kẹp biên)
  const t = Math.max(-3, Math.min(3, p || 0)) / 3;
  if (t >= 0) { const k = t; return `rgb(${Math.round(42 - 20 * k)},${Math.round(52 + 120 * k)},${Math.round(74 + 30 * k)})`; }
  const k = -t; return `rgb(${Math.round(42 + 160 * k)},${Math.round(52 + 10 * k)},${Math.round(74 + 10 * k)})`;
}

async function renderHeatmap() {
  const box = $("#heatmap");
  if (!box) return;
  let d;
  try { d = await (await fetch("/api/market/heatmap")).json(); }
  catch (_) { box.innerHTML = "<div class='disclaimer'>Không tải được dữ liệu heatmap.</div>"; return; }
  const items = d.items || [];
  if (!items.length) { box.innerHTML = "<div class='disclaimer'>Chưa có dữ liệu — chạy P6 bên Crawl Data.</div>"; return; }

  $("#heatmap-meta").innerHTML =
    `${items.length} mã · ${d.board_live ? '<span class="dot-live"></span> %phiên LIVE' : '<span class="dot-cache"></span> %phiên gần nhất'} · ${_formatTs(d.as_of)}`;

  const W = box.clientWidth || 1100, H = Math.max(420, Math.round(W * 0.42));
  // gom ngành, trọng số = tổng vốn hóa
  const bySec = {};
  items.forEach(it => (bySec[it.sector] = bySec[it.sector] || []).push(it));
  const secs = Object.entries(bySec)
    .map(([sec, arr]) => ({ sec, arr, _w: arr.reduce((s, x) => s + x.cap, 0) }))
    .sort((a, b) => b._w - a._w);
  const HEAD = 15;                          // dải tên ngành trong mỗi khối
  const secRects = squarify(secs, 0, 0, W, H);

  let html = "";
  for (const sr of secRects) {
    if (sr.w < 30 || sr.h < 26) continue;   // khối quá bé → bỏ nhãn + ô lẻ
    html += `<div style="position:absolute;left:${sr.x}px;top:${sr.y}px;width:${sr.w - 1}px;height:${HEAD}px;
      overflow:hidden;font-size:9.5px;letter-spacing:.4px;color:var(--muted);padding:1px 4px;
      text-transform:uppercase;white-space:nowrap">${_esc(secVI(sr.sec))}</div>`;
    const cells = squarify(
      sr.arr.map(x => ({ ...x, _w: x.cap })).sort((a, b) => b._w - a._w),
      sr.x, sr.y + HEAD, sr.w, sr.h - HEAD);
    for (const c of cells) {
      if (c.w < 3 || c.h < 3) continue;
      const border = c.near_high52 ? "1.5px solid var(--warn)"
        : c.near_low52 ? "1.5px solid var(--purple, #9b7bff)" : "1px solid rgba(0,0,0,.35)";
      const showTxt = c.w > 34 && c.h > 22;
      const showPct = c.w > 44 && c.h > 34;
      const tip = `${c.symbol} · ${secVI(c)}\n${fmtPctSigned(c.chg_pct, 2)} ${c.live ? "(LIVE)" : "(phiên gần nhất)"}` +
        `\nVốn hóa ${fmtMoney(c.cap)} · ${c.above_ma20 ? "trên" : "dưới"} MA20` +
        (c.near_high52 ? "\nSát đỉnh 52 tuần" : "") + (c.near_low52 ? "\nSát đáy 52 tuần" : "");
      html += `<div title="${_esc(tip)}" style="position:absolute;left:${c.x}px;top:${c.y}px;
        width:${Math.max(1, c.w - 1)}px;height:${Math.max(1, c.h - 1)}px;background:${heatColor(c.chg_pct)};
        border:${border};box-sizing:border-box;overflow:hidden;cursor:default;
        display:flex;flex-direction:column;align-items:center;justify-content:center;line-height:1.15">
        ${showTxt ? `<b style="font-size:${Math.min(13, Math.max(9, c.w / 5))}px;color:#eef3fa">${_esc(c.symbol)}</b>` : ""}
        ${showPct ? `<span style="font-size:10px;color:#dbe6f5">${fmtPctSigned(c.chg_pct, 2)}</span>` : ""}
      </div>`;
    }
  }
  box.style.height = H + "px";
  box.innerHTML = html;
}
renderHeatmap();
let _hmResize;
window.addEventListener("resize", () => { clearTimeout(_hmResize); _hmResize = setTimeout(renderHeatmap, 300); });
setInterval(renderHeatmap, 60000);   // %phiên LIVE → làm mới mỗi phút

/* ══════════════════════════════════════════════════════════════════════════
   RADAR DỮ KIỆN — viết lại: gom nhóm, xếp hạng theo độ mạnh, 1 dòng số đậm,
   bấm ra chi tiết. Trước đây đổ ~60 dòng gần giống hệt → người dùng bỏ qua.
   Nguyên tắc pháp lý: chỉ MÔ TẢ dữ kiện định lượng, không quy kết thao túng.
   ══════════════════════════════════════════════════════════════════════════ */
const RADAR_KIND = {
  stacked:           { icon: "🎯", label: "Chồng nhiều tín hiệu", hint: "Một mã dính từ 2 loại dữ kiện trở lên — đáng chú ý nhất." },
  price_run_no_news: { icon: "🚀", label: "Giá chạy không tin nền", hint: "Giá biến động mạnh nhưng KHÔNG có công bố thông tin đi kèm trong 30 ngày." },
  divergence:        { icon: "🔀", label: "Phân kỳ giá–khối lượng", hint: "Giá tăng nhưng khối lượng cạn dần — lực mua không xác nhận." },
  vol_spike:         { icon: "📊", label: "Khối lượng đột biến", hint: "Khối lượng phiên vượt xa trung bình 20 phiên." },
  limit_streak:      { icon: "🧱", label: "Chuỗi trần/sàn", hint: "Nhiều phiên liên tiếp đóng cửa sát biên độ." },
};
const RADAR_ORDER = ["stacked", "price_run_no_news", "divergence", "vol_spike", "limit_streak"];
let _radarData = null, _radarFilter = "all";

/* Độ mạnh để xếp hạng trong mỗi nhóm (số càng lớn càng đáng chú ý). */
function radarMag(s) {
  const m = s.metrics || {};
  switch (s.kind) {
    case "vol_spike": return m.vol_ratio || 0;
    case "price_run_no_news": return Math.abs(m.run_pct || 0);
    case "divergence": return Math.abs(m.chg_5d || 0) + Math.abs(m.vol_trend || 0);
    case "limit_streak": return (m.streak || 0) * 10;
    default: return s._stackCount ? s._stackCount * 1000 : 0;
  }
}

/* 1 dòng dữ kiện DÀY: số in đậm, không câu giải thích lặp (đưa vào tooltip nhóm). */
function radarLine(s) {
  const m = s.metrics || {};
  const dir = m.chg_1d != null ? (m.chg_1d >= 0 ? "up" : "down")
    : (m.run_pct >= 0 || m.chg_5d >= 0 ? "up" : "down");
  let facts = "", note = "";
  if (s.kind === "vol_spike") {
    facts = `KL <b>×${fmtVN(m.vol_ratio, 1)}</b> TB20 · ${fmtPctSigned(m.chg_1d, 1)} phiên`;
    if (s.note) note = s.note;   // cờ nghi GD thỏa thuận/sự kiện vốn (×>20)
  } else if (s.kind === "price_run_no_news") {
    // 3 nhãn tin khác nhau theo coverage — KHÔNG dùng "0 tin" cho mã chưa crawl.
    const ns = m.news_status;
    let tag;
    if (ns === "none_confirmed")
      tag = '<b class="warn-txt">0 tin CBTT</b> 30 ngày';       // vàng — khẳng định
    else if (ns === "rss_found")
      tag = `<b style="color:#22d3a5">${m.rss_count} bài báo chí</b> (chưa phải CBTT)`;  // xanh nhạt
    else
      tag = '<span style="color:#8a97ab">chưa crawl tin</span>';  // xám — trung tính
    facts = `<b>${fmtPctSigned(m.run_pct, 1)}</b>/${m.days} phiên · ${tag}`;
  } else if (s.kind === "divergence")
    facts = `giá <b>${fmtPctSigned(m.chg_5d, 1)}</b>/5 phiên · KL <b>${fmtPctSigned(m.vol_trend, 0)}</b>`;
  else if (s.kind === "limit_streak")
    facts = `<b>${m.streak}</b> phiên ${m.direction} sát biên ±${fmtVN(m.limit_pct, 0)}%`;
  else if (s.kind === "stacked")
    facts = s._stackKinds.map(k => (RADAR_KIND[k] || {}).icon || "•").join(" ") +
      ` <b>${s._stackCount} loại tín hiệu</b>`;
  const sev = s.severity === "cao"
    ? '<span class="rd-sev hi">CAO</span>'
    : s.severity === "thap"
      ? '<span class="rd-sev" style="opacity:.6">thấp</span>'
      : '<span class="rd-sev">vừa</span>';
  const noteHtml = note
    ? `<div class="rd-note" style="font-style:italic;color:#e0a02a;font-size:11px;margin-top:2px">⚠ ${_esc(note)}</div>` : "";
  return `<a class="rd-row rd-${dir}" href="http://127.0.0.1:5000/app/?sym=${encodeURIComponent(s.symbol)}"
      target="_blank" rel="noopener" title="${_esc(s.verify || RADAR_KIND[s.kind]?.hint || "")}">
    ${sev}<b class="rd-sym">${_esc(s.symbol)}</b>
    <span class="rd-facts">${facts}${noteHtml}</span>
    <span class="rd-go">xem ›</span></a>`;
}

function renderRadarBody() {
  const box = $("#radar-body"); if (!box || !_radarData) return;
  const d = _radarData;

  // gom nhóm; xếp hạng trong nhóm theo độ mạnh
  const groups = {};
  d.signals.forEach(s => (groups[s.kind] = groups[s.kind] || []).push(s));
  Object.values(groups).forEach(g => g.sort((a, b) => radarMag(b) - radarMag(a)));

  // chồng tín hiệu: mã xuất hiện ở ≥2 loại → nhóm "stacked" lên đầu
  const bySym = {};
  d.signals.forEach(s => (bySym[s.symbol] = bySym[s.symbol] || new Set()).add(s.kind));
  const stacked = Object.entries(bySym).filter(([, ks]) => ks.size >= 2)
    .map(([sym, ks]) => ({ symbol: sym, kind: "stacked", severity: "cao",
      _stackKinds: [...ks], _stackCount: ks.size,
      verify: `Dính ${ks.size} loại dữ kiện: ${[...ks].map(k => RADAR_KIND[k]?.label).join(", ")}` }));
  if (stacked.length) groups.stacked = stacked;

  // thanh lọc theo loại
  const kinds = RADAR_ORDER.filter(k => groups[k]?.length);
  const tabs = `<div class="rd-tabs">
    <button class="rd-tab ${_radarFilter === "all" ? "on" : ""}" data-k="all">Tất cả</button>
    ${kinds.map(k => `<button class="rd-tab ${_radarFilter === k ? "on" : ""}" data-k="${k}">
      ${RADAR_KIND[k].icon} ${RADAR_KIND[k].label} <span class="rd-n">${groups[k].length}</span></button>`).join("")}
  </div>`;

  const showKinds = _radarFilter === "all" ? kinds : kinds.filter(k => k === _radarFilter);
  const TOP = _radarFilter === "all" ? 4 : 30;   // Tất cả: 4 mã/nhóm; lọc 1 loại: xem hết
  const blocks = showKinds.map(k => {
    const g = groups[k], head = RADAR_KIND[k];
    const top = g.slice(0, TOP).map(radarLine).join("");
    const more = g.length > TOP
      ? `<details class="rd-more"><summary>…và ${g.length - TOP} mã khác cùng loại</summary>
         ${g.slice(TOP).map(radarLine).join("")}</details>` : "";
    return `<div class="rd-group">
      <div class="rd-ghead" title="${_esc(head.hint)}">${head.icon} ${head.label}
        <span class="rd-n">${g.length}</span> <span class="rd-i">ⓘ</span></div>
      ${top}${more}</div>`;
  }).join("");

  const nSym = Object.keys(bySym).length;
  const meta = $("#radar-meta");
  if (d.stale) {
    meta.innerHTML = `<span style="color:#f0556d">⚠ dữ liệu phiên ${_esc(String(d.as_of).slice(0,10))} — chưa có phiên hôm nay</span>`
      + ` · ${d.n_signals} dữ kiện · ${nSym} mã`
      + ` <button id="rd-refresh" class="rd-tab" style="margin-left:6px">⟳ Cập nhật giá</button>`;
  } else {
    meta.textContent = `${d.n_signals} dữ kiện · ${nSym} mã · ${_formatTs(d.as_of)}`;
  }
  // Dòng vốn ngoại: có tín hiệu → liệt kê; thiếu dữ liệu → message tích lũy chính xác.
  let fx = "";
  const ff = d.foreign_flip;
  if (ff && ff.available && (ff.signals || []).length) {
    fx = `<div class="disclaimer" style="margin-top:10px">🌐 Dòng vốn ngoại đảo chiều: `
      + ff.signals.map(x => `<b>${_esc(x.symbol)}</b> ${_esc(x.flip)}`).join(" · ") + `</div>`;
  } else if (ff) {
    fx = `<div class="disclaimer" style="margin-top:10px">🌐 Dòng vốn ngoại: ${_esc(ff.reason)}</div>`;
  }
  box.innerHTML = tabs + blocks + fx +
    `<div class="disclaimer" style="margin-top:8px">Đây là dữ kiện định lượng để bạn TỰ kiểm tra — không kết luận đúng/sai, không phải khuyến nghị.</div>`;
  box.querySelectorAll(".rd-tab").forEach(b =>
    b.addEventListener("click", () => { _radarFilter = b.dataset.k; renderRadarBody(); }));
  const rb = $("#rd-refresh");
  if (rb) rb.addEventListener("click", (e) => { e.stopPropagation(); refreshPrices(rb); });
}

/* A4: bấm ⟳ → chạy P6 nền, poll 5s, xong tự nạp lại radar + heatmap. */
async function refreshPrices(btn) {
  btn.disabled = true;
  btn.textContent = "⏳ đang cập nhật…";
  try {
    await fetch("/api/market/refresh_prices", { method: "POST" });
  } catch (_) { btn.textContent = "⟳ thử lại"; btn.disabled = false; return; }
  const poll = setInterval(async () => {
    let st;
    try { st = await (await fetch("/api/market/refresh_prices/status")).json(); }
    catch (_) { return; }
    if (st.done || !st.running) {
      clearInterval(poll);
      btn.textContent = st.error ? "⚠ lỗi — thử lại" : "✓ xong";
      btn.disabled = false;
      if (!st.error) {
        renderRadar();
        if (typeof renderHeatmap === "function") renderHeatmap();
      }
    }
  }, 5000);
}

async function renderRadar() {
  const box = $("#radar-body"); if (!box) return;
  let d;
  try { d = await (await fetch("/api/market/anomalies")).json(); }
  catch (_) { box.innerHTML = "<div class='disclaimer'>Không tải được Radar dữ kiện.</div>"; return; }
  if (!d.available || !(d.signals || []).length) {
    box.innerHTML = "<div class='disclaimer'>Chưa phát hiện dữ kiện bất thường (hoặc chưa có dữ liệu giá).</div>";
    return;
  }
  _radarData = d;
  renderRadarBody();
}
renderRadar();
// (làm mới radar gộp vào vòng refresh trực tiếp 60s ở cuối file — không lặp riêng)

/* ══════════════════════════════════════════════════════════════════════════
   A7 — 3 section tự nạp (không cần AI), mỗi section 1 guardSection độc lập:
   Nhịp thị trường · Biến động trong phiên · Xu hướng ngành.
   Nguyên tắc pháp lý: chỉ MÔ TẢ dữ kiện định lượng, KHÔNG khuyến nghị.
   ══════════════════════════════════════════════════════════════════════════ */

/* Bảng giá dùng chung cho Nhịp + Biến động — fetch 1 lần, cache promise. */
let _boardPromise = null;
function loadBoard() {
  if (!_boardPromise) {
    _boardPromise = fetch("/api/market/board").then(r => {
      if (!r.ok) throw new Error("bảng giá chưa sẵn sàng (" + r.status + ")");
      return r.json();
    });
  }
  return _boardPromise;
}

/* Row hợp lệ: có mã + giá khớp + tham chiếu (>0). */
function _validBoardRows(board) {
  return (board?.rows || []).filter(r =>
    r && r.symbol && Number(r.matchPrice) > 0 && Number(r.ref) > 0);
}

/* %phiên + trạng thái 1 mã (trần/sàn/tăng/giảm/đứng) → class màu VN. */
function _boardRowState(r) {
  const ref = Number(r.ref), mp = Number(r.matchPrice);
  const chg = r.matchChange;
  const pct = (isFinite(ref) && ref !== 0)
    ? ((chg != null && isFinite(Number(chg)) ? Number(chg) : (mp - ref)) / ref * 100)
    : null;
  let cls = "is-ref";                       // đứng giá / không xác định
  if (r.ceil != null && mp >= Number(r.ceil)) cls = "is-ceil";
  else if (r.floor != null && mp <= Number(r.floor)) cls = "is-floor";
  else if (pct != null && pct > 0) cls = "is-up";
  else if (pct != null && pct < 0) cls = "is-down";
  return { pct, cls };
}

/* ---- A · ⚡ Nhịp thị trường ---- */
async function renderPulse() {
  const board = await loadBoard();
  const rows = _validBoardRows(board);
  const box = $("#pulse-body");
  if (!rows.length) { box.innerHTML = emptyState("Chưa có dữ liệu bảng giá."); return; }

  let up = 0, down = 0, flat = 0, ceil = 0, floor = 0, totVol = 0;
  for (const r of rows) {
    const st = _boardRowState(r);
    if (st.cls === "is-ceil") ceil++;
    else if (st.cls === "is-floor") floor++;
    if (st.pct > 0) up++; else if (st.pct < 0) down++; else flat++;
    totVol += Number(r.totalVol) || 0;
  }
  const n = rows.length;

  let range = null;
  try { range = await getData("market_range"); } catch (_) { /* thiếu → hiện — */ }
  const idxCard = (range?.available && range.base != null)
    ? kpi("VNINDEX", fmtVN(range.base, 2),
        "tính đến " + (_formatTs(range.as_of) || "—"), "blue hero")
    : kpi("VNINDEX", "—", "chưa có market_range", "blue hero");

  // Ảnh 6: mỗi con số mang màu ĐÚNG NGHĨA của nó (tăng xanh / đứng vàng / giảm đỏ,
  // trần tím / sàn cyan) thay vì tô cả cụm một màu theo class card.
  // Ảnh 7: bỏ dòng interp lặp lại y nguyên số của KPI — gộp "nghiêng bên nào" vào sub.
  const lean = up > down ? "nghiêng về bên mua" : (down > up ? "nghiêng về bên bán" : "cân bằng");
  const kpis = idxCard +
    kpi("Tăng / Đứng / Giảm",
        `<span class="num-up">${up}</span> / <span class="num-ref">${flat}</span> / <span class="num-down">${down}</span>`,
        `trên ${n} mã bảng giá · độ rộng ${lean}`, "plain") +
    kpi("Trần / Sàn",
        `<span class="num-ceil">${ceil}</span> / <span class="num-floor">${floor}</span>`,
        "mã kịch biên", "plain") +
    kpi("Tổng KLGD", fmtVN(totVol, 0), "cổ phiếu khớp toàn bảng", "blue");

  const meta = board?.live
    ? `<div style="font-size:12px;color:var(--muted);margin-top:2px"><span class="dot-live"></span> bảng giá LIVE</div>`
    : `<div style="margin-top:2px">${badge("cache", "warn")} ${sourceTag(board?.source || "bảng giá", board?.as_of, true)}</div>`;

  box.innerHTML = `<div class="kpi-row">${kpis}</div>${meta}`;
}

/* ---- B · 🌊 Biến động trong phiên (tab client-side) ---- */
let _intradayRows = null, _intradayTab = "vol", _intradayBoard = null;
const _INTRADAY_TABS = [
  { k: "vol", label: "Khối lượng" },
  { k: "gain", label: "Tăng mạnh" },
  { k: "lose", label: "Giảm mạnh" },
];

function _intradayTop(rows, tab) {
  // Loại mã thanh khoản quá thấp khỏi 2 tab xếp theo %phiên — cùng tiêu chí
  // `tradable` do server gắn (modules/market_overview/liquidity.py) như bảng Top
  // ở trang chủ, để 2 chỗ không đưa ra 2 danh sách mâu thuẫn.
  // Tab "Khối lượng" GIỮ NGUYÊN: nó vốn đã sắp theo khối lượng nên mã chết tự
  // rớt xuống, và ở đây khối lượng lớn mới là điều đáng xem.
  const arr = rows.map(r => ({ r, ...(_boardRowState(r)) }));
  if (tab === "vol")
    return arr.sort((a, b) => (Number(b.r.totalVol) || 0) - (Number(a.r.totalVol) || 0)).slice(0, 5);
  const withPct = arr.filter(x => x.pct != null && isFinite(x.pct) && x.r.tradable !== false);
  return (tab === "gain"
    ? withPct.sort((a, b) => b.pct - a.pct)
    : withPct.sort((a, b) => a.pct - b.pct)).slice(0, 5);
}

function renderIntradayBody() {
  const box = $("#intraday-body");
  if (!box) return;
  const rows = _intradayRows || [];
  if (!rows.length) { box.innerHTML = emptyState("Chưa có dữ liệu bảng giá."); return; }

  const tabs = `<div class="tabbar">${_INTRADAY_TABS.map(t =>
    `<div class="tabpill ${t.k === _intradayTab ? "active" : ""}" data-itab="${t.k}">${t.label}</div>`
  ).join("")}</div>`;

  const body = _intradayTop(rows, _intradayTab).map(({ r, pct, cls }) => `
    <tr>
      <td><a href="/co-phieu/${encodeURIComponent(r.symbol)}" class="${cls}"
             style="font-weight:700;text-decoration:none">${_esc(r.symbol)}</a></td>
      <td class="num num-mono ${cls}">${fmtVN(r.matchPrice, 2)}</td>
      <td class="num num-mono ${cls}">${fmtPctSigned(pct, 2)}</td>
      <td class="num num-mono">${fmtVN(r.totalVol, 0)}</td>
    </tr>`).join("");

  const b = _intradayBoard;
  const foot = `<div style="font-size:12px;color:var(--muted);margin-top:6px">`
    + `${b?.live ? '<span class="dot-live"></span> bảng giá LIVE' : '<span class="dot-cache"></span> phiên gần nhất (cache)'} · ${_formatTs(b?.as_of)}</div>`;
  box.innerHTML = tabs + `<div class="table-wrap"><table class="mini-table">
    <tr><th>Mã</th><th class="num">Giá khớp</th><th class="num">% phiên</th><th class="num">Khối lượng</th></tr>
    ${body}</table></div>${foot}`;
  box.querySelectorAll(".tabpill[data-itab]").forEach(p =>
    p.addEventListener("click", () => { _intradayTab = p.dataset.itab; renderIntradayBody(); }));
}

async function renderIntraday() {
  const board = await loadBoard();
  _intradayBoard = board;
  _intradayRows = _validBoardRows(board);
  renderIntradayBody();
}

/* ---- C · 🏭 Xu hướng ngành (bar ± thuần CSS, %phiên bình quân tính theo quy mô công ty) ---- */
async function renderSectorTrend() {
  const box = $("#sector-trend-body");
  const d = await (await fetch("/api/market/heatmap")).json();
  const items = (d.items || []).filter(it =>
    it && it.sector && isFinite(Number(it.cap)) && isFinite(Number(it.chg_pct)));
  if (!items.length) {
    box.innerHTML = emptyState("Chưa có dữ liệu ngành — chạy P6 bên Crawl Data."); return;
  }

  const bySec = {};
  for (const it of items) {
    const s = bySec[it.sector] || (bySec[it.sector] = { sector: it.sector, sector_vi: it.sector_vi, capSum: 0, wSum: 0, n: 0 });
    const cap = Number(it.cap) || 0;
    s.capSum += cap; s.wSum += cap * Number(it.chg_pct); s.n++;
  }
  const secs = Object.values(bySec)
    .map(s => ({ sector: s.sector, sector_vi: s.sector_vi, n: s.n, avg: s.capSum > 0 ? s.wSum / s.capSum : 0 }))
    .sort((a, b) => b.avg - a.avg);
  const maxAbs = Math.max(0.1, ...secs.map(s => Math.abs(s.avg)));

  const rows = secs.map(s => {
    const up = s.avg >= 0;
    const w = Math.min(100, Math.abs(s.avg) / maxAbs * 100);
    const col = up ? "var(--up)" : "var(--down)";
    return `<div style="display:flex;align-items:center;gap:10px;margin:6px 0;font-size:13px">
      <div style="flex:0 0 190px;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis"
           title="${_esc(secVI(s))} · ${s.n} mã">${_esc(secVI(s))} <span style="color:var(--muted)">(${s.n})</span></div>
      <div style="flex:1;display:flex;align-items:center">
        <div style="flex:1;display:flex;justify-content:flex-end">
          ${!up ? `<div style="height:16px;width:${w}%;background:${col};border-radius:4px 0 0 4px;opacity:.85"></div>` : ""}
        </div>
        <div style="width:1px;height:20px;background:var(--border)"></div>
        <div style="flex:1;display:flex;justify-content:flex-start">
          ${up ? `<div style="height:16px;width:${w}%;background:${col};border-radius:0 4px 4px 0;opacity:.85"></div>` : ""}
        </div>
      </div>
      <div class="num-mono ${up ? "is-up" : "is-down"}" style="flex:0 0 64px;text-align:right">${fmtPctSigned(s.avg, 2)}</div>
    </div>`;
  }).join("");

  const strong = secs[0], weak = secs[secs.length - 1];
  const interp = `<div class="interp-line">Ngành <b>${_esc(secVI(strong))}</b> mạnh nhất ${fmtPctSigned(strong.avg, 2)}`
    + ` · ngành <b>${_esc(secVI(weak))}</b> yếu nhất ${fmtPctSigned(weak.avg, 2)} —`
    + ` theo %phiên bình quân tính theo quy mô công ty (${secs.length} ngành, ${items.length} mã).</div>`;

  const foot = `<div style="font-size:12px;color:var(--muted);margin-top:4px">`
    + `${d.board_live ? '<span class="dot-live"></span> %phiên LIVE' : '<span class="dot-cache"></span> %phiên phiên gần nhất'} · ${_formatTs(d.as_of)}</div>`;

  box.innerHTML = `<div style="margin-top:4px">${rows}</div>${interp}${foot}`;
}

/* Nạp lần đầu 3 section A7 (lỗi độc lập qua guardSection). */
guardSection("#pulse-body", renderPulse);
guardSection("#intraday-body", renderIntraday);
guardSection("#sector-trend-body", renderSectorTrend);

/* Làm mới ĐỒNG BỘ mọi phần lấy dữ liệu TRỰC TIẾP từ bảng giá + heatmap mỗi phút:
   Nhịp · Biến động · Xu hướng ngành · Toàn cảnh · Radar. Bỏ cache promise để
   mỗi nhịp đều fetch tươi (LIVE khi Bảng giá :5555 chạy, cache khi tắt). */
function refreshLiveSections() {
  _boardPromise = null;                     // buộc fetch bảng giá mới
  guardSection("#pulse-body", renderPulse);
  guardSection("#intraday-body", renderIntraday);
  guardSection("#sector-trend-body", renderSectorTrend);
  if (typeof renderHeatmap === "function") renderHeatmap();  // toàn cảnh — fetch tươi
  renderRadar();                                             // radar — fetch tươi
}
/* R1: theo nhịp chung LivePoll (15s trong phiên · 120s ngoài giờ · dừng khi tab
   ẩn) thay setInterval 60s cứng. Đồng thời cập nhật badge tuổi dữ liệu ở tiêu đề
   Nhịp thị trường để người dùng luôn biết số đang xem mới đến mức nào. */
LivePoll.on((d) => {
  refreshLiveSections();
  const h = document.querySelector("#pulse h2");
  if (!h) return;
  let b = h.querySelector(".age-badge-slot");
  if (!b) {
    b = document.createElement("span");
    b.className = "age-badge-slot";
    b.style.marginLeft = "8px";
    h.appendChild(b);
  }
  b.innerHTML = dataAge(d.as_of, d.live);
});
