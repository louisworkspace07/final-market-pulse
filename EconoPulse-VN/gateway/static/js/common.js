/* Market Pulse — helpers dùng chung mọi trang */
const $ = (s) => document.querySelector(s);

/* ==========================================================================
   Chuẩn ĐỊNH DẠNG SỐ Việt Nam — DÙNG CHO MỌI CON SỐ TRÊN TOÀN HỆ THỐNG.
   Quy ước VN: dấu CHẤM ngăn cách hàng nghìn, dấu PHẨY thập phân.
   (1.234.567,89). Trước đây chấm/phẩy lẫn lộn giữa các trang gây hiểu nhầm
   "1.907" là một-nghìn hay một-phẩy-chín → nay thống nhất 1 hàm duy nhất.
   ========================================================================== */
function fmtVN(v, decimals = 0) {
  if (v === null || v === undefined || v === "" || (typeof v === "number" && !isFinite(v)))
    return "—";
  const n = typeof v === "number" ? v : Number(String(v).replace(/[^\d.,-]/g, "").replace(",", "."));
  if (!isFinite(n)) return "—";
  return n.toLocaleString("vi-VN", {
    minimumFractionDigits: decimals, maximumFractionDigits: decimals,
  });
}
/* Số phần trăm có dấu +/- (cho biến động giá). */
function fmtPctSigned(v, decimals = 2) {
  if (v === null || v === undefined || !isFinite(Number(v))) return "—";
  const n = Number(v);
  return (n >= 0 ? "+" : "") + fmtVN(n, decimals) + "%";
}
/* Giá cổ phiếu (đồng, không lẻ): 73.500. Dùng cho mọi cột giá/bảng giá/ticker. */
function fmtPrice(v) { return fmtVN(v, 0); }
/* Điểm chỉ số (2 lẻ): 1.848,25. Dùng cho VN-INDEX / VN30 / HNX-INDEX. */
function fmtIndex(v) { return fmtVN(v, 2); }

/* Số tiền VND rút gọn: tỷ / nghìn tỷ. */
function fmtMoney(v) {
  if (v === null || v === undefined || !isFinite(Number(v))) return "—";
  const n = Number(v);
  if (Math.abs(n) >= 1e12) return fmtVN(n / 1e12, 1) + " nghìn tỷ";
  if (Math.abs(n) >= 1e9) return fmtVN(n / 1e9, 0) + " tỷ";
  if (Math.abs(n) >= 1e6) return fmtVN(n / 1e6, 0) + " triệu";
  return fmtVN(n, 0);
}

/* ==========================================================================
   Ảnh 8 · VIỆT HÓA — tên ngành ICB + ngày tháng.
   Bản sao của modules/common/sector_vi.py (sửa 1 bên thì sửa cả 2). API mới đã
   trả sẵn `sector_vi`; hàm dưới là lớp đỡ cho payload cũ/cache chưa có field đó.
   ========================================================================== */
const SECTOR_VI = {
  "Banks": "Ngân hàng",
  "Real Estate": "Bất động sản",
  "Construction & Materials": "Xây dựng & Vật liệu",
  "Industrial Goods & Services": "Hàng & Dịch vụ công nghiệp",
  "Food & Beverage": "Thực phẩm & Đồ uống",
  "Utilities": "Điện, nước & Tiện ích",
  "Basic Resources": "Tài nguyên cơ bản",
  "Personal & Household Goods": "Hàng tiêu dùng cá nhân",
  "Chemicals": "Hóa chất",
  "Health Care": "Y tế",
  "Financial Services": "Dịch vụ tài chính",
  "Travel & Leisure": "Du lịch & Giải trí",
  "Media": "Truyền thông",
  "Technology": "Công nghệ",
  "Retail": "Bán lẻ",
  "Automobiles & Parts": "Ô tô & Phụ tùng",
  "Insurance": "Bảo hiểm",
  "Oil & Gas": "Dầu khí",
  "Telecommunications": "Viễn thông",
  "Khác": "Khác",
};
/* Ưu tiên sector_vi do API trả; không có thì tra bảng; vẫn không có thì giữ nguyên. */
function secVI(sectorOrItem) {
  if (sectorOrItem && typeof sectorOrItem === "object")
    return sectorOrItem.sector_vi || secVI(sectorOrItem.sector);
  const s = String(sectorOrItem || "").trim();
  return SECTOR_VI[s] || s || "Khác";
}

/* Ngày kiểu Việt: "T5 · 09/07/2026". Nhận ISO hoặc chuỗi ngày kiểu Anh
   ("Mon, 01 Jul 2019" — thứ phạm ở timeline tin). Không parse được → giữ nguyên. */
const _THU_VN = ["CN", "T2", "T3", "T4", "T5", "T6", "T7"];
function fmtDateVN(v, withWeekday = true) {
  if (!v) return "—";
  const d = v instanceof Date ? v : new Date(v);
  if (isNaN(d.getTime())) return String(v);
  const p = (n) => String(n).padStart(2, "0");
  const dmy = `${p(d.getDate())}/${p(d.getMonth() + 1)}/${d.getFullYear()}`;
  return withWeekday ? `${_THU_VN[d.getDay()]} · ${dmy}` : dmy;
}

/* Màu chart đọc từ CSS var → tự khớp theme sáng/tối tại thời điểm nạp trang. */
function chartColors() {
  const cs = getComputedStyle(document.documentElement);
  const v = (name, fb) => (cs.getPropertyValue(name) || "").trim() || fb;
  return {
    text: v("--muted", "#8b96b3"),
    grid: v("--border", "#24304f"),
    accent: v("--accent", "#4f8cff"),
    up: v("--up", "#22d3a5"),
    down: v("--down", "#f0616d"),
    ref: v("--ref", "#f4b942"),
  };
}
if (window.Chart) {
  const c = chartColors();
  Chart.defaults.color = c.text;
  Chart.defaults.borderColor = c.grid;
}
/* Đổi theme → chart đã vẽ giữ màu cũ; reload để mọi canvas vẽ lại đúng palette.
   (Trang chỉ-DOM không có chart thì CSS var tự áp, không cần reload.) */
window.addEventListener("mp:theme", () => {
  if (window.Chart && Object.keys(Chart.instances || {}).length) location.reload();
});

/* ==========================================================================
   R1 · REALTIME — 1 poller dùng chung cho toàn app.
   Trước đây mỗi section tự setInterval gọi /api/market/board → N request trùng
   nhau. Nay mọi nơi đăng ký callback vào LivePoll, chỉ 1 request /api/live.
   - Trong giờ giao dịch (server báo live=true): 15s/lần.
   - Ngoài giờ / dữ liệu cache: giãn 120s (tránh ảo giác "live" — giá vốn delay
     ≥15s và ngoài phiên chỉ là giá đóng cửa).
   - Tab ẩn → dừng hẳn; quay lại tab → nạp ngay 1 phát.
   ========================================================================== */
const LivePoll = (() => {
  const subs = new Set();
  let timer = null, last = null, inflight = false;
  const FAST = 15000, SLOW = 120000;

  async function tick() {
    if (inflight || document.hidden) return schedule();
    inflight = true;
    try {
      const symbols = [...new Set([...subs].flatMap(s => s.symbols || []))];
      const q = symbols.length ? "?symbols=" + encodeURIComponent(symbols.join(",")) : "";
      const d = await fetch("/api/live" + q).then(r => r.ok ? r.json() : null);
      if (d) { last = d; subs.forEach(s => { try { s.fn(d); } catch (_) {} }); }
    } catch (_) { /* mạng chập chờn → giữ số cũ, thử lại lượt sau */ }
    inflight = false;
    schedule();
  }
  function schedule() {
    clearTimeout(timer);
    if (document.hidden) return;                  // tab ẩn: không tiêu tài nguyên
    timer = setTimeout(tick, last && last.live ? FAST : SLOW);
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) tick(); });

  return {
    /** on(fn, symbols?) — fn(data) gọi mỗi nhịp; symbols để xin báo giá riêng. */
    on(fn, symbols) {
      const s = { fn, symbols: symbols || null };
      subs.add(s);
      if (last) { try { fn(last); } catch (_) {} }
      if (subs.size === 1) tick(); else schedule();
      return () => subs.delete(s);
    },
    get last() { return last; },
    refresh: tick,
  };
})();

/* Badge tuổi dữ liệu: xanh <1 phút · vàng trong ngày · đỏ cũ hơn (kèm "x ngày trước").
   Mục đích R1: mọi con số phải tự trả lời được "số này mới đến mức nào". */
function dataAge(ts, live) {
  if (live) return `<span class="age-badge age-fresh"><span class="dot-live"></span>LIVE</span>`;
  if (!ts) return `<span class="age-badge age-old">chưa rõ thời điểm</span>`;
  const d = new Date(ts);
  if (isNaN(d.getTime())) return `<span class="age-badge age-old">${_esc(String(ts))}</span>`;
  const mins = (Date.now() - d.getTime()) / 60000;
  if (mins < 1) return `<span class="age-badge age-fresh">vừa xong</span>`;
  if (mins < 60) return `<span class="age-badge age-fresh">${Math.round(mins)} phút trước</span>`;
  if (mins < 1440) return `<span class="age-badge age-day">${Math.round(mins / 60)} giờ trước</span>`;
  const days = Math.round(mins / 1440);
  return `<span class="age-badge age-old">${days} ngày trước · ${fmtDateVN(d, false)}</span>`;
}

async function getData(name) {
  const r = await fetch(`/api/data/${name}`);
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  return r.json();
}

function kpi(label, value, sub, cls = "blue") {
  return `<div class="kpi ${cls}"><div class="label">${label}</div>
    <div class="value">${value}</div><div class="sub">${sub || ""}</div></div>`;
}

/* ==========================================================================
   Component factory dùng chung (P2) — MỌI trang render section qua bộ này để
   loading / lỗi / rỗng trông đồng nhất. KHÔNG đổi class hook cũ, chỉ THÊM.
   ========================================================================== */
function badge(text, tone = "muted") {
  // tone: up | down | warn | muted — màu theo token VN
  const map = { up: "var(--up)", down: "var(--down)", warn: "var(--ref)", muted: "var(--muted)" };
  return `<span class="badge" style="color:${map[tone] || map.muted}">${_esc(text)}</span>`;
}

/* ==========================================================================
   HỆ SKELETON THỐNG NHẤT (§9) — skel(type, opts) trả HTML placeholder ĐÚNG HÌNH
   & ĐÚNG CHIỀU CAO nội dung thật để layout không nhảy (CLS≈0). Dùng THAY spinner
   + chữ "Đang tải…" ở MỌI section. Spinner chỉ còn cho nút bấm & step AI.
   type: kpi · table · chart · text · gauge · radar · orderbook · bars-h
   opts: {rows, cols, height, cards, cta} — tùy variant. CSS ở style-v3.css (.sk-*).
   ========================================================================== */
function skel(type = "text", opts = {}) {
  const bar = (w, h, extra = "") =>
    `<div class="mp-skeleton" style="height:${h}px;width:${w};${extra}"></div>`;
  let inner = "";
  switch (type) {
    case "kpi": {                       // hàng thẻ KPI (label + số lớn + sub)
      const n = opts.cards || 4;
      inner = `<div class="sk-kpi-row">` + Array.from({ length: n }, () =>
        `<div class="sk-kpi">${bar("54%", 11, "margin-bottom:9px")}${bar("72%", 22, "margin-bottom:8px")}${bar("40%", 10)}</div>`
      ).join("") + `</div>`;
      break;
    }
    case "table": {                     // bảng: header + N hàng đều nhau
      const rows = opts.rows || 6, cols = opts.cols || 4;
      const cell = (h) => `<div class="sk-td">${bar("78%", h)}</div>`;
      inner = `<div class="sk-table">
        <div class="sk-tr sk-thead">${Array.from({ length: cols }, () => cell(10)).join("")}</div>`
        + Array.from({ length: rows }, () =>
          `<div class="sk-tr">${Array.from({ length: cols }, () => cell(13)).join("")}</div>`).join("")
        + `</div>`;
      break;
    }
    case "chart": {                     // biểu đồ: trục giả + cột/đường mờ
      const h = opts.height || 220;
      const bars = 12, gap = 4;
      let cols = "";
      for (let i = 0; i < bars; i++) {
        const bh = 26 + ((i * 37) % 62);   // chiều cao "ngẫu nhiên tĩnh" (không Math.random)
        cols += `<div class="mp-skeleton sk-bar" style="height:${bh}%"></div>`;
      }
      inner = `<div class="sk-chart" style="height:${h}px">
        <div class="sk-chart-bars" style="gap:${gap}px">${cols}</div>
        <div class="sk-chart-axis">${Array.from({ length: 5 }, () => `<span></span>`).join("")}</div>
      </div>`;
      break;
    }
    case "gauge": {                     // đồng hồ tròn (sức khỏe)
      const h = opts.height || 150;
      inner = `<div class="sk-gauge" style="height:${h}px">
        <div class="mp-skeleton sk-gauge-ring"></div>${bar("40%", 12, "margin:12px auto 0")}</div>`;
      break;
    }
    case "radar": {                     // pentagon nhấp nháy (Phân tích 360)
      const h = opts.height || 300;
      inner = `<div class="sk-radar" style="height:${h}px">
        <div class="mp-skeleton sk-radar-poly"></div></div>`;
      break;
    }
    case "orderbook": {                 // sổ lệnh mua/bán 3 mức
      const side = () => Array.from({ length: 3 }, () =>
        `<div class="sk-ob-row">${bar("46%", 12)}${bar("38%", 12)}</div>`).join("");
      inner = `<div class="sk-orderbook"><div class="sk-ob-col">${side()}</div><div class="sk-ob-col">${side()}</div></div>`;
      break;
    }
    case "bars-h": {                    // thanh ngang (top tăng/giảm, %ngành)
      const rows = opts.rows || 6;
      inner = Array.from({ length: rows }, (_, i) =>
        `<div class="sk-hbar-row">${bar("22%", 13)}<div class="mp-skeleton sk-hbar" style="width:${72 - (i * 9) % 46}%"></div></div>`
      ).join("");
      inner = `<div class="sk-hbars">${inner}</div>`;
      break;
    }
    case "text":
    default: {                          // đoạn văn bản nhiều dòng
      const rows = opts.rows || 3;
      inner = Array.from({ length: rows }, (_, i) =>
        bar(`${92 - i * 12}%`, i === 0 ? 22 : 14, "margin:9px 0")).join("");
    }
  }
  const cta = opts.cta === false ? "" : "";
  return `<div class="sk-wrap" aria-busy="true" aria-live="polite">
    <span class="sr-only">Đang tải…</span>${inner}${cta}</div>`;
}

/* Giữ chữ ký cũ — nhiều nơi còn gọi skeleton(); nay delegate sang hệ mới. */
function skeleton(rows = 3) {
  return skel("text", { rows });
}

function emptyState(msg, icon = "🗂️") {
  return `<div class="card" style="text-align:center;color:var(--muted);padding:26px">
    <div style="font-size:26px;margin-bottom:8px">${icon}</div>${_esc(msg)}</div>`;
}

function errorBox(msg, retryFn) {
  const id = "retry-" + Math.random().toString(36).slice(2, 8);
  setTimeout(() => {
    const b = document.getElementById(id);
    if (b && retryFn) b.onclick = retryFn;
  }, 0);
  return `<div class="card" style="border-color:rgba(240,97,109,.4)">
    <div style="color:var(--danger);font-weight:600;margin-bottom:6px">⚠️ Không tải được dữ liệu</div>
    <div style="color:var(--muted);font-size:12.5px;margin-bottom:10px">${_esc(msg)}</div>
    ${retryFn ? `<button id="${id}" class="ghost">↻ Thử lại</button>` : ""}</div>`;
}

/* Nạp 1 section chuẩn: skeleton → render(data) → errorBox(+retry).
   el: element hoặc selector; name: tên file /api/data/<name>; render(data) tự vẽ.
   opts.skel: loại skeleton ('table'|'chart'|'kpi'|…) + opts còn lại truyền cho skel(). */
async function loadSection(el, name, render, opts = {}) {
  const node = typeof el === "string" ? document.querySelector(el) : el;
  if (!node) return;
  node.innerHTML = typeof opts === "string" ? skel(opts) : skel(opts.skel || "text", opts);
  try {
    const data = await getData(name);
    node.innerHTML = "";
    await render(data, node);
  } catch (e) {
    node.innerHTML = errorBox(`${name}: ${e.message}`, () => loadSection(el, name, render, opts));
  }
}

/* ==========================================================================
   Watchlist (A6) — localStorage "mp_watchlist", chưa cần tài khoản.
   Neo mã cần theo dõi nhưng chưa nằm trong danh mục (PDF triage 19/27).
   ========================================================================== */
function wlGet() {
  try { return JSON.parse(localStorage.getItem("mp_watchlist") || "[]"); }
  catch { return []; }
}
function wlHas(sym) { return wlGet().includes(sym); }
function wlToggle(sym) {
  const list = wlGet();
  const i = list.indexOf(sym);
  i >= 0 ? list.splice(i, 1) : list.push(sym);
  localStorage.setItem("mp_watchlist", JSON.stringify(list));
  return i < 0; // true = vừa thêm
}
/* Nút sao gắn cạnh mã — tự cập nhật trạng thái khi bấm. */
function wlStar(sym) {
  const id = "wl-" + sym + "-" + Math.random().toString(36).slice(2, 6);
  setTimeout(() => {
    const b = document.getElementById(id);
    if (!b) return;
    const sync = () => {
      b.textContent = wlHas(sym) ? "★" : "☆";
      b.style.color = wlHas(sym) ? "var(--ref)" : "var(--muted)";
      b.title = wlHas(sym) ? "Bỏ khỏi danh sách theo dõi" : "Thêm vào danh sách theo dõi";
    };
    sync();
    b.onclick = (e) => { e.preventDefault(); e.stopPropagation(); wlToggle(sym); sync(); };
  }, 0);
  return `<button id="${id}" class="wl-star" aria-label="theo dõi ${sym}"
    style="background:none;border:0;cursor:pointer;font-size:16px;padding:0 4px">☆</button>`;
}

/* Chạy 1 hàm render section có sẵn (tự vẽ vào nhiều node) với lỗi hiển thị
   tại chỗ thay vì chết im lặng trong console. anchor: node hiện errorBox. */
function guardSection(anchor, fn) {
  const node = typeof anchor === "string" ? document.querySelector(anchor) : anchor;
  return fn().catch((e) => {
    console.error(e);
    if (node) node.innerHTML = errorBox(e.message, () => guardSection(anchor, fn));
  });
}

function confClass(c) {
  if (!c) return "thap";
  const s = String(c).toLowerCase();
  if (s.startsWith("cao")) return "cao";
  if (s.startsWith("trung")) return "trung";
  return "thap";
}

function linkFacts(text) {
  return String(text).replace(/\[(F\d+)\]/g,
    '<span class="fact-ref" data-fid="$1">[$1]</span>');
}

/* vẽ chuỗi lịch sử + dự báo + dải tin cậy */
function forecastChart(canvasId, histLabels, histValues, fc, unit) {
  const labels = [...histLabels, ...(fc.years || fc.dates)];
  const histData = [...histValues, ...Array((fc.years || fc.dates).length).fill(null)];
  const n = histValues.length;
  const fcMean = [...Array(n - 1).fill(null), histValues[n - 1], ...fc.mean];
  const fcLower = [...Array(n - 1).fill(null), histValues[n - 1], ...fc.lower];
  const fcUpper = [...Array(n - 1).fill(null), histValues[n - 1], ...fc.upper];

  // Palette phẳng v3 — đọc token runtime, không hardcode rainbow.
  const _cc = chartColors();
  const _pri = _cc.accent || "#006CEC", _up = _cc.up || "#25B770";
  new Chart($(canvasId), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Lịch sử", data: histData, borderColor: _pri,
          backgroundColor: _pri, pointRadius: 2, borderWidth: 2, tension: .3 },
        { label: "Dự báo", data: fcMean, borderColor: _up,
          borderDash: [6, 4], pointRadius: 3, borderWidth: 2, tension: .3 },
        { label: "Cận dưới 80%", data: fcLower, borderColor: "transparent",
          backgroundColor: "rgba(37,183,112,.12)", fill: "+1", pointRadius: 0 },
        { label: "Cận trên 80%", data: fcUpper, borderColor: "transparent",
          backgroundColor: "rgba(37,183,112,.12)", pointRadius: 0 },
      ],
    },
    options: {
      plugins: {
        legend: { labels: { filter: (i) => !i.text.includes("Cận") } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmtVN(c.parsed.y, 2)}${unit ? " " + unit : ""}` } },
      },
      scales: {
        x: { ticks: { autoSkip: true, maxTicksLimit: 10, maxRotation: 0 } },
        y: { title: { display: !!unit, text: unit || "" }, ticks: { callback: (v) => fmtVN(v, 1) } },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

/* ==========================================================================
   Explainability helpers
   ========================================================================== */

/**
 * Tạo HTML badge nguồn dữ liệu.
 * @param {string} source  - Tên nguồn, ví dụ "vnstock", "World Bank", "Crawl Data"
 * @param {string|null} ts - ISO timestamp hoặc chuỗi ngày; nếu null thì bỏ qua
 * @param {boolean} stale  - Nếu true, hiển thị màu vàng cảnh báo dữ liệu cũ
 */
/* Ảnh 5 · Ở mode Cơ bản, nhãn nguồn không được lộ tên file/tiến trình nội bộ
   ("Test tool temp_data/data.json (cache — server chưa bật)"). Vẫn GIỮ mốc thời
   gian vì đó là thông tin độ tươi dữ liệu người dùng cần (R1). Chi tiết kỹ thuật
   luôn còn trong tooltip cho ai muốn xem. */
const _SOURCE_VI = [
  [/test\s*tool|temp_data|:5555/i, "Bảng giá thị trường"],
  [/crawl\s*data|market\.db|market_index|financials/i, "Dữ liệu doanh nghiệp"],
  [/market_range/i, "Chỉ số VN-Index"],
  [/health_scores|business_health/i, "Chấm sức khỏe tài chính"],
  [/macro_plus|macro_forecast|world\s*bank/i, "Dữ liệu vĩ mô"],
  [/gemini|claude|cdp/i, "Phân tích AI"],
];
function _friendlySource(raw) {
  for (const [re, vi] of _SOURCE_VI) if (re.test(raw)) return vi;
  return null;
}
function sourceTag(source, ts = null, stale = false) {
  const tsText = ts ? ` · ${_formatTs(ts)}` : "";
  const cls = stale ? "source-tag stale" : "source-tag";
  // B11: gọn 1 cấp — nguồn ngoặc-lồng-ngoặc "market_range (VNINDEX thật
  // (market_index, VNDirect))" → nhãn 1 cấp; chi tiết kỹ thuật dồn vào title.
  const raw = String(source || "").replace(/\s+/g, " ").trim();
  const tech = _shortSource(raw);
  const basic = document.body.classList.contains("mode-basic");
  const label = (basic && _friendlySource(raw)) || tech;
  const titleAttr = label !== raw ? ` title="${_esc(raw)}${ts ? " · " + _esc(String(ts)) : ""}"` : "";
  return `<span class="${cls}"${titleAttr}>${_esc(label)}${tsText}</span>`;
}

/* B11: chỉ rút gọn khi nguồn có NGOẶC LỒNG (dấu hiệu chuỗi kỹ thuật). Nguồn 1
   cấp giữ nguyên. Có lồng → lấy provider quen thuộc, hoặc đoạn trước "(". */
function _shortSource(raw) {
  const firstOpen = raw.indexOf("(");
  const hasNested = firstOpen >= 0 && raw.indexOf("(", firstOpen + 1) >= 0;
  if (!hasNested) return raw;   // nguồn sạch 1 cấp → không đụng
  const PROVIDERS = ["VNDirect", "vnstock", "World Bank", "market.db", "VCI", "KBS", "TCBS", "SSI", "Gemini", "Claude"];
  for (const p of PROVIDERS) {
    if (raw.toLowerCase().includes(p.toLowerCase())) return p;
  }
  const head = raw.slice(0, firstOpen).trim();
  return head || raw.replace(/[()]/g, " ").replace(/\s+/g, " ").trim();
}

/** Định dạng timestamp thân thiện: "hôm nay 14:32" hoặc "12/06/2025" */
function _formatTs(ts) {
  if (!ts) return "";
  const d = new Date(ts);
  if (isNaN(d.getTime())) return ts;
  const now = new Date();
  const diffDays = Math.floor((now - d) / 86400000);
  if (diffDays === 0) {
    return `hôm nay ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
  }
  if (diffDays === 1) return "hôm qua";
  if (diffDays < 7) return `${diffDays} ngày trước`;
  return `${d.getDate().toString().padStart(2,"0")}/${(d.getMonth()+1).toString().padStart(2,"0")}/${d.getFullYear()}`;
}

function _esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

/**
 * Bao bọc nội dung card bằng drill-down toggle.
 * @param {string} label      - Nhãn nút toggle, ví dụ "Xem chi tiết kỹ thuật"
 * @param {string} innerHtml  - Nội dung ẩn bên trong panel
 * @param {string} [id]       - ID duy nhất (tự sinh nếu không truyền)
 */
function drillDown(label, innerHtml, id = null) {
  const pid = id || `drill-${Math.random().toString(36).slice(2,8)}`;
  return `
    <button class="drill-toggle" onclick="toggleDrill('${pid}')">
      <span class="toggle-arrow" id="arr-${pid}">▸</span> ${_esc(label)}
    </button>
    <div class="drill-panel" id="${pid}">${innerHtml}</div>`;
}

/** Bật/tắt drill-down panel */
function toggleDrill(id) {
  const panel = document.getElementById(id);
  const arrow = document.getElementById("arr-" + id);
  if (!panel) return;
  panel.classList.toggle("open");
  if (arrow) arrow.textContent = panel.classList.contains("open") ? "▾" : "▸";
}

/**
 * Tự động gắn source tags vào tất cả .card trên trang nếu API trả về
 * trường data_as_of hoặc updated_at.
 * @param {object} meta - { source, data_as_of, stale_days }
 */
function attachSourceTags(meta) {
  if (!meta || !meta.source) return;
  const staleDays = meta.stale_days || 7;
  const dataDate = meta.data_as_of || meta.updated_at;
  let isStale = false;
  if (dataDate) {
    const diff = (Date.now() - new Date(dataDate).getTime()) / 86400000;
    isStale = diff > staleDays;
  }
  const tag = sourceTag(meta.source, dataDate, isStale);
  document.querySelectorAll(".card h3, section h2").forEach(el => {
    if (!el.querySelector(".source-tag")) {
      el.insertAdjacentHTML("afterend", `<div style="margin:-8px 0 8px">${tag}</div>`);
    }
  });
}

/* ==========================================================================
   Topbar shell — đồng hồ realtime + trạng thái phiên giao dịch VN (HOSE)
   Tự khởi động nếu trang có #tb-clock / #tb-mkt.
   ========================================================================== */
function _pad(n) { return String(n).padStart(2, "0"); }

/** Phiên HOSE: 09:00–15:00, Thứ 2–Thứ 6 (giờ VN, GMT+7). */
function _vnMarketState() {
  // Quy đổi về giờ VN bất kể timezone máy người dùng
  const nowVN = new Date(Date.now() + (7 * 60 + new Date().getTimezoneOffset()) * 60000);
  const day = nowVN.getDay();          // 0 = CN, 6 = T7
  const mins = nowVN.getHours() * 60 + nowVN.getMinutes();
  const isWeekday = day >= 1 && day <= 5;
  const open = isWeekday && mins >= 540 && mins <= 900;   // 9:00–15:00
  return { open, nowVN };
}

function _startClock() {
  const clockEl = document.getElementById("tb-clock");
  const mktEl = document.getElementById("tb-mkt");
  if (!clockEl && !mktEl) return;

  const tick = () => {
    const { open, nowVN } = _vnMarketState();
    if (clockEl) {
      clockEl.textContent =
        `${_pad(nowVN.getHours())}:${_pad(nowVN.getMinutes())}:${_pad(nowVN.getSeconds())}`;
    }
    if (mktEl) {
      mktEl.className = "mkt-status " + (open ? "open" : "closed");
      mktEl.innerHTML = `<span class="dot"></span>${open ? "Đang giao dịch" : "Ngoài giờ"}`;
    }
  };
  tick();
  setInterval(tick, 1000);
}

document.addEventListener("DOMContentLoaded", _startClock);


/* ==========================================================================
   embedApp — nhúng 1 app con (:5000/:5555/:3333) vào iframe trong cổng :9999.
   Chờ app con sống (poll /api/children/status) rồi mới gán iframe.src (1 lần).
   Chưa sống → overlay "đang khởi động…" tự thử lại; hết hạn → nút khởi động lại.
   ========================================================================== */
async function _childRunning(childId) {
  try {
    const st = await (await fetch("/api/children/status")).json();
    return !!(st[childId] && st[childId].running);
  } catch (_) {
    return false;
  }
}

function embedApp(containerId, childId, url, opts) {
  opts = opts || {};
  const fullBleed = !!opts.fullBleed;   // trang Bảng giá / Dữ liệu: iframe tràn khung
  const box = document.getElementById(containerId);
  if (!box) return;
  box.style.position = "relative";

  // full-bleed: dùng class .embed-frame (CSS lo kích thước, chạm mép, id để fullscreen).
  // Trang khác (copilot): giữ nguyên style inline cũ để không đổi giao diện.
  const frameId = `${containerId}-frame`;
  const iframeStyle =
    "width:100%;height:calc(100vh - 130px);border:0;border-radius:12px;background:var(--bg2)";
  const frameAttr = fullBleed
    ? `id="${frameId}" class="embed-frame"`
    : `style="${iframeStyle}"`;

  // Nút "cửa sổ riêng" nổi góc iframe — full-bleed đã có nút trên topbar nên bỏ.
  const openBtn = () => fullBleed ? "" :
    `<button onclick="window.open('${url}')" title="Mở cửa sổ riêng"
       style="position:absolute;top:10px;right:10px;z-index:3;padding:6px 10px;
       border-radius:8px;border:1px solid var(--border-hi);background:var(--card);
       color:var(--text);cursor:pointer;font-size:13px">↗ Cửa sổ riêng</button>`;

  const ovH = fullBleed ? "calc(100vh - 52px)" : "calc(100vh - 130px)";
  const ovRadius = fullBleed ? "0" : "12px";

  const mount = () => {
    box.innerHTML =
      `<iframe src="${url}" ${frameAttr} allow="clipboard-read; clipboard-write"></iframe>` +
      openBtn();
  };

  const overlay = (msg, showRetry) => {
    box.innerHTML =
      `<div style="height:${ovH};display:flex;flex-direction:column;
        align-items:center;justify-content:center;gap:16px;border-radius:${ovRadius};
        background:var(--bg2);border:1px solid var(--border);color:var(--muted)">
        <div style="font-size:15px;text-align:center;max-width:460px;padding:0 20px">${msg}</div>` +
      (showRetry
        ? `<button id="${containerId}-retry" style="padding:9px 16px;border-radius:9px;
            border:1px solid var(--border-hi);background:var(--grad-soft);color:#fff;
            cursor:pointer;font-size:14px;font-weight:600">⟳ Khởi động lại</button>`
        : `<div class="spinner" style="width:26px;height:26px;border:3px solid var(--border);
            border-top-color:var(--accent);border-radius:50%;animation:spin 0.9s linear infinite"></div>`) +
      openBtn();

    if (showRetry) {
      const btn = document.getElementById(`${containerId}-retry`);
      if (btn) btn.onclick = async () => {
        overlay("⏳ Đang khởi động lại…", false);
        try { await fetch(`/api/children/restart/${childId}`, { method: "POST" }); } catch (_) {}
        poll(0);
      };
    }
  };

  let mounted = false;
  const MAX = 40;
  const poll = async (n) => {
    if (mounted) return;
    if (await _childRunning(childId)) {
      mounted = true;
      mount();
      return;
    }
    if (n >= MAX) {
      overlay(`⚠️ App <b>${childId}</b> chưa phản hồi. Bấm để thử khởi động lại.`, true);
      return;
    }
    overlay(`⏳ Đang khởi động <b>${childId}</b>… (${n + 1}/${MAX})`, false);
    setTimeout(() => poll(n + 1), 3000);
  };

  poll(0);
  return { frameId, childId, url };   // controller cho topbar (fullscreen/restart)
}

/* ==========================================================================
   Topbar trang embed full-bleed: chip trạng thái child + restart + cửa sổ riêng
   + fullscreen. Poll /api/children/status mỗi 5s. Gọi sau embedApp.
   ========================================================================== */
function initEmbedTopbar(controller) {
  if (!controller) return;
  const { frameId, childId, url } = controller;
  const chip = document.getElementById("child-chip");

  async function refreshChip() {
    if (!chip) return;
    let up = false;
    try {
      const st = await (await fetch("/api/children/status")).json();
      up = !!(st[childId] && st[childId].running);
    } catch (_) { up = false; }
    chip.className = "child-chip " + (up ? "up" : "down");
    chip.innerHTML = `<span class="dot"></span>${up ? "đang chạy" : "đã ngừng"}`;
  }
  refreshChip();
  setInterval(refreshChip, 5000);

  const restart = document.getElementById("tb-restart");
  if (restart) restart.onclick = async () => {
    restart.disabled = true;
    try { await fetch(`/api/children/restart/${childId}`, { method: "POST" }); } catch (_) {}
    setTimeout(() => { restart.disabled = false; refreshChip(); location.reload(); }, 1500);
  };

  const openWin = document.getElementById("tb-open");
  if (openWin) openWin.onclick = () => window.open(url);

  const fs = document.getElementById("tb-fullscreen");
  if (fs) fs.onclick = () => {
    const f = document.getElementById(frameId);
    if (f && f.requestFullscreen) f.requestFullscreen().catch(() => {});
  };
}

/* ==========================================================================
   Thu gọn sidebar thành rail 56px — MỌI trang (base.html tự gọi). Nhớ
   localStorage để giữ trạng thái sau F5. Khi rail, nhãn ẩn → gán title để
   hover vẫn biết tên chức năng (PDF triage 28.2).
   ========================================================================== */
function initSidebarToggle() {
  const body = document.body;
  const KEY = "mp_embed_rail"; // giữ key cũ để không mất trạng thái đã lưu
  if (localStorage.getItem(KEY) === "1") body.classList.add("rail");

  // tooltip tên chức năng khi rail (nhãn bị ẩn)
  document.querySelectorAll(".side-nav a").forEach((a) => {
    if (!a.title) a.title = a.textContent.trim();
  });

  const btn = document.getElementById("side-toggle");
  if (!btn) return;
  const sync = () => { btn.textContent = body.classList.contains("rail") ? "⟩" : "⟨"; };
  sync();
  btn.onclick = () => {
    const railed = body.classList.toggle("rail");
    localStorage.setItem(KEY, railed ? "1" : "0");
    sync();
  };
}

/* ==========================================================================
   §2.4/§2.5 · Khối "Bước tiếp theo" — dùng chung mọi trang.
   Đọc xong một trang, người mới thường không biết nên làm gì tiếp. Khối này
   đưa 2–3 việc CỤ THỂ, đều là "xem gì tiếp", KHÔNG bao giờ là gợi ý mua/bán.
   Mọi đường dẫn dưới đây đều là route đang tồn tại trong app.py:
     /so-sanh · /bo-loc · /kien-thuc · /bat-dau · /market.html
     /methodology.html · /co-phieu/<MÃ>
   Cách dùng: renderNextSteps("next-steps", { symbol: "FPT", sector: "Banks" })
   Không tìm thấy phần tử đích thì thoát êm, không báo lỗi.
   ========================================================================== */
function nextStepsHTML(ctx) {
  const c = ctx || {};
  const sym = String(c.symbol || "").toUpperCase().trim();
  const secLabel = typeof secVI === "function" ? secVI(c.sector || c) : (c.sector || "");
  const items = Array.isArray(c.items) && c.items.length ? c.items.slice(0, 3) : null;

  const steps = items || (sym ? [
    {
      href: "/so-sanh?a=" + encodeURIComponent(sym),
      title: "So " + sym + " với một công ty cùng ngành",
      desc: secLabel && secLabel !== "Khác"
        ? "Một con số chỉ có ý nghĩa khi đặt cạnh công ty làm cùng nghề. Mở trang so sánh và chọn thêm một mã ngành " + secLabel + "."
        : "Một con số chỉ có ý nghĩa khi đặt cạnh công ty làm cùng nghề. Mở trang so sánh và chọn thêm một mã cùng ngành.",
    },
    {
      href: "/kien-thuc",
      title: "Tra nghĩa những chữ viết tắt trên trang này",
      desc: "Trang thuật ngữ giải thích từng chữ viết tắt bằng câu tiếng Việt thường ngày, không dùng từ chuyên môn để giải thích từ chuyên môn.",
    },
    {
      href: "/methodology.html",
      title: "Xem cách các con số này được tính",
      desc: "Trang phương pháp nói rõ số liệu lấy từ nguồn nào, tính theo công thức nào và cập nhật lúc nào.",
    },
  ] : [
    {
      href: "/bat-dau",
      title: "Đi theo hướng dẫn 3 bước cho người mới",
      desc: "Xem thị trường hôm nay, tra một mã, rồi đọc điểm sức khỏe doanh nghiệp — theo đúng thứ tự đó.",
    },
    {
      href: "/bo-loc",
      title: "Lọc ra danh sách công ty theo tiêu chí bạn quan tâm",
      desc: "Chọn điều kiện như quy mô công ty hay mức sinh lời, hệ thống trả về danh sách mã thỏa điều kiện.",
    },
    {
      href: "/kien-thuc",
      title: "Tra nghĩa những chữ viết tắt trên trang này",
      desc: "Mỗi thuật ngữ được giải thích bằng một câu tiếng Việt thường ngày.",
    },
  ]);

  const esc = typeof _esc === "function" ? _esc : (s) => String(s == null ? "" : s);
  /* Bản cũ là 3 thẻ to có số thứ tự + đoạn mô tả dài, chiếm gần hết màn cuối
     trang cho thứ chỉ là điều hướng. Rút thành một hàng chip: vẫn dẫn đi đúng
     chỗ, nhưng không giành chỗ của nội dung. Mô tả chuyển vào `title` để hover
     mới hiện. */
  const links = steps.map((s) =>
    `<a class="next-chip" href="${esc(s.href)}" title="${esc(s.desc || "")}">`
    + `${esc(s.title)}</a>`).join("");

  return `
    <nav class="next-steps-box" aria-label="Nội dung nên xem tiếp">
      <span class="next-steps-lead">Xem tiếp</span>
      ${links}
      <span class="next-steps-note">gợi ý nội dung, không phải lời khuyên mua bán</span>
    </nav>`;
}

function renderNextSteps(hostId, ctx) {
  const host = typeof hostId === "string"
    ? (document.getElementById(hostId) || document.getElementById("next-steps"))
    : (hostId || document.getElementById("next-steps"));
  if (!host) return false;              // trang chưa có chỗ đặt → thoát êm
  host.innerHTML = nextStepsHTML(ctx);
  if (window.MPTerm && typeof window.MPTerm.scan === "function") {
    try { window.MPTerm.scan(host); } catch (_) { }
  }
  return true;
}

/* Gom các helper dùng chung vào một chỗ để WS khác gọi qua M.* cho rõ nguồn. */
window.M = Object.assign(window.M || {}, {
  fmtVN, fmtMoney, fmtPrice, fmtIndex, fmtPctSigned,
  secVI, fmtDateVN,
  renderNextSteps, nextStepsHTML,
});
