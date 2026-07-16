/* Trang cổ phiếu v3 — /co-phieu/<sym>. Sub-header + tabs + Tổng quan a→k.
   Dữ liệu: /api/stock/<sym> (+ /api/market/board cho order book/khối ngoại).
   Tab "Phân tích" do stock-analysis.js đảm nhiệm (lazy khi mở tab). */

const SYM = window.MP_SYMBOL;
const M = window.MPChart;
let STOCK = null;         // cache /api/stock
let _boardRow = undefined; // cache dòng board của mã (undefined=chưa nạp)
let _chartsLoaded = false; // tab "Biểu đồ" chỉ nạp 1 lần (Phụ lục D)
let _sourcesLoaded = false; // tab "Dữ liệu gốc" chỉ nạp 1 lần

/* ---------- tabs ---------- */
function initTabs() {
  const tabs = document.querySelectorAll("#stock-tabs .ptab");
  const panels = document.querySelectorAll(".tab-panel");
  tabs.forEach(t => t.addEventListener("click", () => {
    tabs.forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    const name = t.dataset.tab;
    panels.forEach(p => p.hidden = p.dataset.panel !== name);
    if (name === "analysis" && window.renderAnalysis) window.renderAnalysis();
    /* Tab "Lịch sử giá" đã bỏ — nến ở Tổng quan, chuỗi giá đầy đủ ở Dữ liệu gốc. */
    /* Phụ lục D · nạp lười, chỉ 1 lần: 20 biểu đồ là payload lớn, không nên
       tải khi người dùng còn chưa mở tab. */
    if (name === "charts" && !_chartsLoaded && window.MPCharts) {
      _chartsLoaded = true;
      window.MPCharts.load("charts-root", SYM);
    }
    if (name === "sources" && !_sourcesLoaded && window.MPSources) {
      _sourcesLoaded = true;
      window.MPSources.load("sources-root", SYM);
    }
  }));
}

async function _board() {
  if (_boardRow !== undefined) return _boardRow;
  try {
    const b = await (await fetch("/api/market/board")).json();
    _boardRow = (b.rows || []).find(r => r.symbol === SYM) || null;
  } catch (_) { _boardRow = null; }
  return _boardRow;
}

async function renderStock() {
  const r = await fetch(`/api/stock/${SYM}`);
  if (!r.ok) {
    const e = await r.json().catch(() => ({}));
    document.querySelector("#stock-subhead .sh-inner").innerHTML =
      `<div style="color:var(--muted)">${_esc(e.error || "Không có dữ liệu cho " + SYM)}</div>`;
    return;
  }
  STOCK = await r.json();
  const d = STOCK, i = d.info;

  /* --- (1) sub-header --- */
  const chg = d.price ? d.price.change_pct : null;
  const cls = chg == null ? "" : chg > 0 ? "chg-up" : chg < 0 ? "chg-down" : "chg-ref";
  const arw = chg == null ? "" : chg > 0 ? "▲" : chg < 0 ? "▼" : "";
  const px = d.price ? d.price.last : i.current_price;
  document.querySelector("#stock-subhead .sh-inner").innerHTML = `
    <div class="sh-sym">${M.symLogoHTML(i.symbol)}${_esc(i.symbol)} ${wlStar(i.symbol)}</div>
    <div><div class="sh-name">${_esc(i.name || "")}</div>
      <div class="sh-name">${_esc(i.exchange || "")} · ${_esc(secVI(i.sector) || "—")}</div></div>
    <div class="sh-price">
      <div class="p ${cls}">${px != null ? fmtVN(px, 2) : "—"}</div>
      <div class="c ${cls}">${chg != null ? arw + " " + fmtPctSigned(chg) : ""}
        <span style="color:var(--muted)">${d.price ? "· " + fmtDateVN(d.price.as_of) : ""}</span></div>
      <div class="f0-age-row" id="px-age"></div>
    </div>`;

  /* §1.3 · badge tuổi dữ liệu đặt CẠNH chính con số giá */
  mountPriceAge(d);

  renderOverview(d);
  renderNewsTab(d);
  renderFinTab(d);

  /* §2.5 · "Bước tiếp theo nên xem gì" — khối cuối trang, gợi ý NỘI DUNG đọc
     tiếp (so sánh cùng ngành / tra thuật ngữ / xem cách tính), tuyệt đối không
     phải gợi ý mua bán. Component nằm ở common.js.

     BẪY: trong file này `M` là biến cục bộ trỏ tới window.MPChart (dòng 6),
     KHÔNG phải window.M của common.js. Phải gọi qua `window.M` đầy đủ —
     viết `M.renderNextSteps` sẽ luôn undefined và im lặng không render. Cùng
     kiểu che tên này có ở home-v3.js, stock-analysis.js, chat-blocks.js. */
  if (window.M && typeof window.M.renderNextSteps === "function") {
    window.M.renderNextSteps("next-steps", { symbol: i.symbol, sector: i.sector });
  }
}

/* ---------- TAB TỔNG QUAN ---------- */
function renderOverview(d) {
  /* §18 · nạp chỉ báo kỹ thuật rồi vẽ lại chart kèm vùng S/R + bảng đầy đủ */
  loadStockTech(d.info.symbol).then(() => { drawPrice(120); renderTechCard(); });

  /* a. chart giá (nến khi có OHLC; area cho khung dài) */
  drawPrice(120);
  document.querySelectorAll("#ov-price-pills .tfpill").forEach(p =>
    p.addEventListener("click", () => {
      document.querySelectorAll("#ov-price-pills .tfpill").forEach(x => x.classList.remove("active"));
      p.classList.add("active"); drawPrice(+p.dataset.n);
    }));

  /* b. range thấp–cao + KPI cơ bản (S2: dòng so trung vị ngành ngay dưới mỗi số) */
  drawRange();
  const f = d.fund || {};
  const pk = d.peers && !d.peers.error ? d.peers : null;
  // so 1 chỉ số với trung vị ngành → câu ngắn "cao/thấp hơn trung vị ngành (X)"
  const vsSector = (key, unit, decimals) => {
    if (!pk || !pk.benchmark || pk.benchmark[key] == null || !pk.self || pk.self[key] == null) return "trung vị ngành: —";
    const me = pk.self[key], med = pk.benchmark[key];
    const rel = me > med ? "cao hơn" : me < med ? "thấp hơn" : "ngang";
    return `${rel} trung vị ngành (${fmtVN(med, decimals)}${unit || ""})`;
  };
  // §12: micro-bar chuẩn hóa chiều dưới mỗi KPI (trái=kém, phải=thuận lợi).
  // Dùng percentile ngành đã đảo chiều (peers.pct). Thiếu dữ liệu → thanh xám.
  const pct = pk && pk.pct ? pk.pct : {};
  const microBar = (key) => {
    const v = pct[key];
    if (v == null) return `<span class="mpbar-micro missing" title="chưa đủ mã ngành để xếp hạng"></span>`;
    return `<span class="mpbar-micro" title="Percentile ngành (đã chuẩn hóa chiều): ${fmtVN(v,0)}/100 — phải = thuận lợi hơn"><i style="left:${Math.max(0,Math.min(100,v))}%"></i></span>`;
  };
  const kpiWithBar = (label, value, sub, cls, key) =>
    kpi(label, value, `${sub}${microBar(key)}`, cls);
  $("#ov-kpis").innerHTML =
    kpiWithBar("P/E", f.pe != null ? fmtVN(f.pe, 1) : "—", vsSector("pe", "", 1), "blue", "pe") +
    kpiWithBar("P/B", f.pb != null ? fmtVN(f.pb, 1) : "—", vsSector("pb", "", 1), "blue", "pb") +
    kpiWithBar("ROE", f.roe_pct != null ? fmtVN(f.roe_pct, 1) + "%" : "—", vsSector("roe", "%", 1), (f.roe_pct || 0) >= 15 ? "good" : "blue", "roe") +
    kpi("Vốn hóa", d.info.market_cap != null ? fmtMoney(d.info.market_cap) : "—", "quy mô công ty", "blue");

  /* i. tài chính nhanh: hiệu suất giá %7D/1M/3M + biên ròng */
  drawQuickPerf(d);

  /* c. order book (từ board) */
  drawOrderBook();
  /* d. volume profile (tính từ price series) */
  drawVProfile();
  /* e. khối ngoại (board snapshot + xu hướng nhiều ngày) */
  drawForeign(d);
  /* f. sức khỏe (gauge) */
  drawHealth(d);
  /* §3.1 · "Doanh nghiệp này làm gì?" — đặt trên mọi chỉ số */
  drawWhatCompanyDoes(d);
  /* g. timeline sự kiện DN (cổ tức chỉ là 1 loại) + h. thanh khoản & quy mô */
  drawEventTimeline(d);
  drawProfile(d);
  /* j. sở hữu & quản trị — trước đây cào về nhưng chưa từng nối ra trang mã */
  drawOwnership(d);
  /* k. có thể bạn quan tâm */
  drawRelated(d);
}

function _series() { return (STOCK.price && STOCK.price.series) || []; }

/* §18 · Chỉ báo kỹ thuật đầy đủ của mã này (/api/tech_full) — nạp 1 lần. */
let STOCK_TECH = null;
async function loadStockTech(sym) {
  try {
    const d = await (await fetch(`/api/tech_full?symbols=${encodeURIComponent(sym)}`)).json();
    STOCK_TECH = d.items?.[sym] || (d.skipped?.[sym] ? { skipped: d.skipped[sym] } : null);
  } catch (_) { STOCK_TECH = null; }
  return STOCK_TECH;
}

function drawPrice(n) {
  const host = $("#ov-price");
  const s = _series();
  if (!s.length) { M._empty(host, "Mã chưa nằm trong nhóm crawl giá (P6) — chỉ có dữ liệu BCTC."); return; }

  // §18 · Ưu tiên NẾN khi có OHLC thật và khung đủ thưa để đọc được; kèm KL.
  const ohlc = (STOCK.price && STOCK.price.ohlc) || [];
  let chart = null;
  if (ohlc.length > 2 && n <= 140) {
    const cs = ohlc.slice(-n);
    chart = M.lwcCandle(host, {
      ohlc: cs.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })),
      vol: cs.map(c => ({ time: c.time, value: c.volume || 0,
                          color: c.close >= c.open ? "rgba(37,183,112,.45)" : "rgba(225,64,64,.45)" })),
    }, { height: 240 });
  } else {
    const slice = s.slice(-n).map(p => ({ time: p[0], value: p[1] }));
    chart = M.lwcArea(host, slice, { title: "", source: STOCK.price.source, ts: STOCK.price.as_of, height: 240 });
  }

  // §18 · Vẽ THẲNG vùng hỗ trợ/kháng cự lên chart thay vì chỉ liệt kê số ở bảng.
  drawSRLines(chart);
  mountChartAI();
}

/* §18 · "AI đọc chart" — biểu đồ đẹp nhưng người mới vẫn không biết "vậy là sao".
   Nút này gửi CHÍNH các con số kỹ thuật (không gửi ảnh) cho AI mô tả thành lời.
   Chạy khi bấm (tốn 1 lượt AI), kết quả cache theo mã + ngày. */
function mountChartAI() {
  const host = document.getElementById("ov-price");
  if (!host || document.getElementById("chart-ai-box")) return;
  if (!STOCK_TECH || STOCK_TECH.skipped) return;      // thiếu chỉ báo thì không mời gọi

  host.insertAdjacentHTML("afterend", `
    <div id="chart-ai-box">
      <div class="ask-row" style="margin-top:8px">
        <button id="chart-ai-btn" class="ghost" type="button">Đọc giúp tôi biểu đồ này</button>
      </div>
      <div id="chart-ai-body"></div>
    </div>`);

  const cacheKey = `mp_chartai_${SYM}_${new Date().toISOString().slice(0, 10)}`;
  const cached = (() => { try { return JSON.parse(localStorage.getItem(cacheKey) || "null"); } catch { return null; } })();
  if (cached) renderChartAI(cached, true);

  document.getElementById("chart-ai-btn").addEventListener("click", async () => {
    const btn = document.getElementById("chart-ai-btn");
    const body = document.getElementById("chart-ai-body");
    btn.disabled = true; btn.textContent = "AI đang đọc biểu đồ…";
    body.innerHTML = skel("text", { rows: 3 });
    try {
      const r = await fetch(`/api/stock/${encodeURIComponent(SYM)}/chart_ai`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      const d = await r.json();
      if (d.error) throw new Error(d.error);
      try { localStorage.setItem(cacheKey, JSON.stringify(d)); } catch (_) {}
      renderChartAI(d, false);
    } catch (e) {
      body.innerHTML = `<div class="warn-banner">Chưa đọc được biểu đồ: ${_esc(e.message)}</div>`;
    } finally {
      btn.disabled = false; btn.textContent = "Đọc lại biểu đồ";
    }
  });
}

function renderChartAI(d, fromCache) {
  const body = document.getElementById("chart-ai-body");
  if (!body) return;
  const a = d.answer || {};
  const row = (label, text) => text
    ? `<div class="ca-row"><b>${label}</b><div>${_esc(text)}</div></div>` : "";
  const marks = (a.muc_theo_doi || []).map(x => `<li class="neu">${_esc(x)}</li>`).join("");
  body.innerHTML = `
    <div class="card" style="margin-top:8px">
      ${fromCache ? `<div class="disclaimer">Bản đọc đã lưu trong hôm nay — bấm nút để đọc lại.</div>` : ""}
      ${row("Xu hướng", a.xu_huong)}
      ${row("Vị trí giá", a.vi_tri)}
      ${row("Khối lượng", a.khoi_luong)}
      ${row("Biên 52 tuần", a.bien_52_tuan)}
      ${marks ? `<div class="ca-row"><b>Mốc đáng theo dõi</b><ul class="auto-notes">${marks}</ul></div>` : ""}
      ${a.luu_y ? `<div class="interp-line">${_esc(a.luu_y)}</div>` : ""}
      <div class="disclaimer">${_esc(a.disclaimer || "Mô tả dữ liệu quá khứ — KHÔNG phải khuyến nghị đầu tư.")}</div>
    </div>`;
}

/* §18 · Nút "Yêu cầu phân tích" + hỏi tiến độ.
   Hàng đợi nằm ở Crawl Data/temp; worker chạy bằng:
     py -3.12 -m scripts.p4_analyze --queue
   Worker chưa bật thì mã vẫn nằm hàng đợi (không mất), UI nói rõ trạng thái. */
let _reqPollTimer = null;
function initRequestAnalysis() {
  const btn = document.getElementById("req-analysis");
  const box = document.getElementById("req-analysis-state");
  if (!btn || !box) return;

  const paint = (s) => {
    if (!s || s.state === "none") { box.textContent = ""; return; }
    const label = {
      queued: s.msg || "Đã xếp hàng",
      running: "Đang phân tích… (mất vài phút)",
      done: "Đã phân tích xong — tải lại trang để xem kết quả.",
      error: "Phân tích lỗi: " + (s.msg || "không rõ"),
    }[s.state] || "";
    box.textContent = label;
    if (s.state === "done") {
      box.insertAdjacentHTML("beforeend",
        ` <a href="#" onclick="location.reload();return false">Tải lại →</a>`);
    }
    btn.disabled = s.state === "queued" || s.state === "running";
  };

  const poll = async () => {
    try {
      const s = await (await fetch(`/api/stock/${encodeURIComponent(SYM)}/analysis_status`)).json();
      paint(s);
      if (s.state === "done" || s.state === "error" || s.state === "none") {
        clearInterval(_reqPollTimer); _reqPollTimer = null;
      }
    } catch (_) { /* mạng chập chờn → thử lại nhịp sau */ }
  };

  btn.addEventListener("click", async () => {
    btn.disabled = true;
    box.textContent = "Đang gửi yêu cầu…";
    try {
      const r = await fetch(`/api/stock/${encodeURIComponent(SYM)}/request_analysis`,
                            { method: "POST" });
      const s = await r.json();
      if (s.error) { box.textContent = s.error; btn.disabled = false; return; }
      paint(s);
      clearInterval(_reqPollTimer);
      _reqPollTimer = setInterval(poll, 30000);      // hỏi tiến độ 30s/lần
    } catch (e) {
      box.textContent = "Không gửi được yêu cầu: " + e.message;
      btn.disabled = false;
    }
  });

  poll();      // vào trang mà mã đang trong hàng đợi → hiện luôn trạng thái
}

/* §18 · Card "Kỹ thuật đầy đủ" — bộ chỉ báo mà trước đây trang mã không có
   (S/R đa tầng, VBP, RSI14, MA20/50, %KL so TB20, vị trí trong biên 52 tuần).
   Mã thiếu lịch sử → card xám ghi rõ lý do (pattern B14), không im lặng. */
function renderTechCard() {
  const host = document.getElementById("ov-tech");
  if (!host) return;
  const t = STOCK_TECH;
  if (!t) { host.innerHTML = ""; return; }
  if (t.skipped) {
    host.innerHTML = `<div class="card stock-sec missing-card"><h3 class="sec-h">Kỹ thuật</h3>
      <div class="mc-body"><span>Chưa tính được chỉ báo — ${_esc(t.skipped)}.</span></div></div>`;
    return;
  }
  const lv = (arr) => (arr || []).length ? arr.map(x => fmtVN(x, 2)).join(" · ") : "—";
  const rsiNote = t.rsi14 == null ? "" :
    t.rsi14 >= 70 ? "vùng mua nhiều (quá mua)" :
    t.rsi14 <= 30 ? "vùng bán nhiều (quá bán)" : "vùng trung tính";
  const posVI = { breakout: "Vượt đỉnh", near_res: "Sát kháng cự",
                  near_sup: "Về hỗ trợ", mid: "Giữa vùng" }[t.pos] || "—";
  const row = (k, v, sub) => `<tr><td>${k}</td><td class="num">${v}</td>
    <td style="color:var(--muted);font-size:12.5px">${sub || ""}</td></tr>`;
  host.innerHTML = `
    <div class="card stock-sec">
      <h3 class="sec-h">Kỹ thuật đầy đủ
        <span class="src">Tính từ giá lịch sử ${t.bars} phiên — mô tả trạng thái, KHÔNG phải khuyến nghị</span>
        <span class="src src-tech">market.db · price → modules/market_overview/tech_full.py</span>
      </h3>
      <div class="table-wrap"><table>
        <tbody>
          ${row("Vị trí giá", posVI, `giá hiện tại ${fmtVN(t.price, 2)}`)}
          ${row("Hỗ trợ gần", lv(t.sr.support), t.sr.support?.length ? "vùng giá từng nhiều lần bật lên" : "chưa có đáy rõ dưới giá hiện tại")}
          ${row("Kháng cự gần", lv(t.sr.resistance), t.sr.resistance?.length ? "vùng giá từng nhiều lần quay đầu" : "không còn đỉnh cũ phía trên")}
          ${row("Vùng khối lượng dày", lv(t.vbp), "nơi tích tụ nhiều giao dịch nhất")}
          ${row("RSI 14", t.rsi14 != null ? fmtVN(t.rsi14, 0) : "—", rsiNote)}
          ${row("MA20 / MA50", `${fmtVN(t.ma20, 2)} / ${t.ma50 != null ? fmtVN(t.ma50, 2) : "—"}`,
                t.above_ma20 ? "giá trên trung bình 20 phiên" : "giá dưới trung bình 20 phiên")}
          ${row("KL so TB 20 phiên", t.vol_vs_20 != null ? fmtVN(t.vol_vs_20, 2) + " lần" : "—",
                t.vol_vs_20 != null && t.vol_vs_20 >= 1.5 ? "khối lượng cao bất thường" : "")}
          ${row("Biên 52 tuần", `${fmtVN(t.lo52, 2)} – ${fmtVN(t.hi52, 2)}`,
                `cách đỉnh ${fmtPctSigned(t.pct_from_hi52, 1)} · cách đáy ${fmtPctSigned(t.pct_from_lo52, 1)}`)}
        </tbody>
      </table></div>
    </div>`;
}

/* Kẻ đường hỗ trợ (xanh) / kháng cự (đỏ) / MA20 lên chart giá. */
function drawSRLines(chart) {
  if (!chart || !STOCK_TECH || STOCK_TECH.skipped) return;
  const t = STOCK_TECH;
  try {
    const series = chart.__mpSeries || null;   // charts-v3 chưa expose → dùng priceLine của chart
    const add = (price, color, title) => {
      if (price == null || !isFinite(price)) return;
      const s = series || chart;
      if (s && typeof s.createPriceLine === "function")
        s.createPriceLine({ price, color, lineWidth: 1, lineStyle: 2,
                            axisLabelVisible: true, title });
    };
    (t.sr.support || []).slice(0, 2).forEach((p, i) => add(p, "#25B770", i ? "HT2" : "Hỗ trợ"));
    (t.sr.resistance || []).slice(0, 2).forEach((p, i) => add(p, "#E14040", i ? "KC2" : "Kháng cự"));
  } catch (_) { /* thư viện đổi API → bỏ qua, chart vẫn hiển thị bình thường */ }
}

function drawRange() {
  const host = $("#ov-range");
  const b = _boardRowSync();
  const s = _series();
  // ưu tiên high/low board; fallback biên chuỗi giá
  let lo, hi, cur;
  if (b && b.low != null && b.high != null) { lo = b.low; hi = b.high; cur = b.matchPrice; }
  else if (s.length) { const vals = s.map(p => p[1]); lo = Math.min(...vals); hi = Math.max(...vals); cur = vals[vals.length - 1]; }
  if (lo == null) { host.innerHTML = `<div style="color:var(--muted);font-size:13px">Chưa có dữ liệu khoảng giá.</div>`; return; }
  const frac = hi > lo ? (cur - lo) / (hi - lo) * 100 : 50;
  host.innerHTML = `
    <div class="range-lh">
      <div class="rl-track"><div class="rl-fill" style="left:0;width:${Math.max(0, Math.min(100, frac)).toFixed(1)}%"></div>
        <div class="rl-dot" style="left:${Math.max(0, Math.min(100, frac)).toFixed(1)}%"></div></div>
      <div class="rl-ends"><span>Thấp ${fmtVN(lo, 2)}</span><span>Cao ${fmtVN(hi, 2)}</span></div>
    </div>
    <div style="font-size:12.5px;color:var(--muted);margin-top:8px">
      ${b ? "Biên trong phiên (bảng giá)" : "Biên chuỗi giá gần nhất"} · giá hiện tại
      <b style="color:var(--text)">${cur != null ? fmtVN(cur, 2) : "—"}</b></div>`;
}

function _boardRowSync() { return _boardRow && _boardRow !== undefined ? _boardRow : null; }

function drawQuickPerf(d) {
  const host = $("#ov-perf");
  const s = _series();
  if (s.length < 6) { host.innerHTML = `<h3 class="sec-h">Hiệu suất giá</h3><div style="color:var(--muted);font-size:13px">Chưa đủ dữ liệu giá.</div>`; return; }
  const last = s[s.length - 1][1];
  const pct = (nBack) => { const idx = s.length - 1 - nBack; if (idx < 0) return null; const past = s[idx][1]; return past ? (last - past) / past * 100 : null; };
  const rows = [["7 phiên", pct(5)], ["1 tháng", pct(21)], ["3 tháng", pct(63)], ["6 tháng", pct(126)]];
  host.innerHTML = `<h3 class="sec-h">Hiệu suất giá</h3><div class="quick-perf">` +
    rows.map(([lab, v]) => {
      const c = v == null ? "" : v > 0 ? "chg-up" : v < 0 ? "chg-down" : "";
      return `<div class="qp"><div class="lab">${lab}</div><div class="val ${c}">${v == null ? "—" : fmtPctSigned(v)}</div></div>`;
    }).join("") + `</div>
    <div class="disclaimer">Hiệu suất quá khứ, không đảm bảo tương lai — chỉ dữ kiện.</div>`;
}

async function drawOrderBook() {
  const host = $("#ov-orderbook");
  host.innerHTML = `<h3 class="sec-h">Sổ lệnh 3 bậc <span class="src">Bảng giá LIVE (:5555)</span></h3>${skel("orderbook")}`;
  const b = await _board();
  if (!b || b.buyP1 == null) { M._empty(host.querySelector(".spinner") ? host : host, "Cần bảng giá LIVE (:5555) để hiện sổ lệnh.");
    host.innerHTML = `<h3 class="sec-h">Sổ lệnh 3 bậc</h3><div class="chart-empty">Cần bảng giá LIVE (:5555) đang mở để hiện sổ lệnh.</div>`; return; }
  const maxV = Math.max(b.buyV1 || 0, b.buyV2 || 0, b.buyV3 || 0, b.sellV1 || 0, b.sellV2 || 0, b.sellV3 || 0, 1);
  const row = (bv, bp, sp, sv) => `<tr>
    <td class="ob-bid"><span class="ob-barbuy" style="width:${(bv || 0) / maxV * 100}%"></span><span class="ob-num">${bv != null ? fmtVN(bv, 0) : ""}</span></td>
    <td class="ob-bid"><span class="ob-num">${bp != null ? fmtVN(bp, 2) : ""}</span></td>
    <td class="ob-ask"><span class="ob-num">${sp != null ? fmtVN(sp, 2) : ""}</span></td>
    <td class="ob-ask"><span class="ob-barsell" style="width:${(sv || 0) / maxV * 100}%"></span><span class="ob-num">${sv != null ? fmtVN(sv, 0) : ""}</span></td></tr>`;
  // §12: tug "Lực đặt mua ↔ Lực đặt bán" (tổng KL 3 bậc) trên bảng chi tiết.
  const buyTot = (b.buyV1 || 0) + (b.buyV2 || 0) + (b.buyV3 || 0);
  const sellTot = (b.sellV1 || 0) + (b.sellV2 || 0) + (b.sellV3 || 0);
  const tot = buyTot + sellTot;
  const verdict = tot <= 0 ? "" : buyTot > sellTot
    ? `Lực đặt mua đang nhỉnh hơn (${fmtVN(buyTot / tot * 100, 0)}% tổng KL đặt 3 bậc)`
    : buyTot < sellTot
    ? `Lực đặt bán đang nhỉnh hơn (${fmtVN(sellTot / tot * 100, 0)}% tổng KL đặt 3 bậc)`
    : "Lực đặt mua và bán cân bằng";
  host.innerHTML = `<h3 class="sec-h">Sổ lệnh 3 bậc <span class="src">Bảng giá LIVE (:5555)</span></h3>`;
  const tugBox = document.createElement("div"); host.appendChild(tugBox);
  M.mpBar(tugBox, { variant: "tug", verdict,
    tug: { aLabel: "Lực đặt mua", bLabel: "Lực đặt bán", aValue: buyTot, bValue: sellTot } });
  host.insertAdjacentHTML("beforeend", `<table class="orderbook" data-advanced><thead><tr><th class="num">KL mua</th><th class="num">Giá mua</th><th class="num">Giá bán</th><th class="num">KL bán</th></tr></thead>
    <tbody>${row(b.buyV1, b.buyP1, b.sellP1, b.sellV1)}${row(b.buyV2, b.buyP2, b.sellP2, b.sellV2)}${row(b.buyV3, b.buyP3, b.sellP3, b.sellV3)}</tbody></table>`);
  host.insertAdjacentHTML("beforeend", obContext(b));
}

/* Nguồn bảng giá CHỈ có 3 bậc (buyP1..3 / sellP1..3) nên không thể thêm bậc.
   Nhưng cùng dòng đó còn trần/sàn/tham chiếu/khớp/khối ngoại đang bỏ không —
   thiếu chúng thì ba dòng số kia không nói lên điều gì: người đọc không biết
   giá đang ở đâu trong biên độ, chênh mua–bán bao nhiêu, đã khớp bao nhiêu. */
function obContext(b) {
  const px = b.matchPrice || b.ref;
  const pct = (v) => (b.ref && v != null) ? ` (${fmtPctSigned((v - b.ref) / b.ref * 100, 1)})` : "";
  const spread = (b.sellP1 != null && b.buyP1 != null) ? b.sellP1 - b.buyP1 : null;
  const cell = (lb, val, cls) =>
    `<div class="ob-stat"><span class="ob-stat-l">${lb}</span>`
    + `<span class="ob-stat-v ${cls || ""}">${val}</span></div>`;

  // Vị trí giá hiện tại trong biên độ sàn–trần của phiên.
  let band = "";
  if (b.floor != null && b.ceil != null && px != null && b.ceil > b.floor) {
    const at = Math.max(0, Math.min(100, (px - b.floor) / (b.ceil - b.floor) * 100));
    band = `<div class="ob-band" title="Vị trí giá trong biên độ hôm nay">
      <span class="ob-band-lab">Sàn ${fmtVN(b.floor, 2)}</span>
      <span class="ob-band-track"><i style="left:${at.toFixed(1)}%"></i></span>
      <span class="ob-band-lab">Trần ${fmtVN(b.ceil, 2)}</span>
    </div>`;
  }
  const fb = b.foreignBuy || 0, fs = b.foreignSell || 0;
  const fnet = fb - fs;
  return `<div class="ob-ctx">
    ${band}
    <div class="ob-stats">
      ${cell("Khớp gần nhất", px != null ? fmtVN(px, 2) + pct(px) : "—",
             b.ref && px > b.ref ? "up" : b.ref && px < b.ref ? "down" : "")}
      ${cell("Tham chiếu", b.ref != null ? fmtVN(b.ref, 2) : "—")}
      ${cell("Chênh mua–bán", spread != null ? fmtVN(spread, 2) : "—")}
      ${cell("KL khớp phiên", b.totalVol != null ? fmtVN(b.totalVol, 0) : "—")}
      ${cell("Cao – thấp", (b.high != null && b.low != null)
             ? `${fmtVN(b.low, 2)} – ${fmtVN(b.high, 2)}` : "—")}
      ${cell("Khối ngoại ròng", (fb || fs) ? fmtVN(fnet, 0) + " cp" : "—",
             fnet > 0 ? "up" : fnet < 0 ? "down" : "")}
    </div>
    <p class="ob-note">Ba bậc là toàn bộ độ sâu nguồn bảng giá cung cấp.
      Khối lượng đặt có thể thay đổi từng giây và không phải cam kết giao dịch.</p>
  </div>`;
}

function drawVProfile() {
  const host = $("#ov-vprofile");
  const s = _series();
  if (s.length < 10) { host.innerHTML = `<h3 class="sec-h">Phân bố giá</h3><div class="chart-empty">Chưa đủ dữ liệu giá.</div>`; return; }
  const vals = s.map(p => p[1]);
  const lo = Math.min(...vals), hi = Math.max(...vals);
  // 12 → 18 mức giá. Chiều cao biểu đồ = số mức × 18px, nên ở 12 mức nó chỉ cao
  // 220px trong khi ô bên cạnh (sổ lệnh) cao 457px — hụt 198px khoảng trắng.
  // Tăng số mức vừa lấp đầy ô vừa cho phân bố mịn hơn, không phải nhồi cho vừa.
  const BINS = 18, w = (hi - lo) / BINS || 1;
  const bins = Array.from({ length: BINS }, (_, k) => ({ price: +(lo + (k + 0.5) * w).toFixed(2), n: 0 }));
  vals.forEach(v => { const k = Math.min(BINS - 1, Math.floor((v - lo) / w)); bins[k].n++; });
  const tot = vals.length;
  const data = bins.reverse().map(b => ({ price: b.price, vol: b.n, pct: b.n / tot * 100 }));
  const cur = vals[vals.length - 1];
  // đánh dấu bin gần giá hiện tại
  let nearest = data[0]; data.forEach(b => { if (Math.abs(b.price - cur) < Math.abs(nearest.price - cur)) nearest = b; });
  M.svgVProfile(host, data, { title: "Phân bố mật độ giá (theo số phiên)", sub: "Xấp xỉ từ chuỗi giá đóng cửa", current: nearest.price, source: "market.db · price" });
}

/* §20 P5* · trước bản này chỉ có snapshot 1 phiên (bảng giá LIVE), không thấy
   XU HƯỚNG. foreign_history.jsonl (Crawl Data) tích lũy mỗi ngày 1 dòng —
   ai_analysis.py/anomaly.py đã đọc nó cho cảnh báo cấp thị trường (foreign_flip),
   giờ vẽ trực tiếp trên trang mã bằng dải cột ròng/ngày tự viết (không phụ
   thuộc thư viện chart ngoài — chỉ vài chục điểm, SVG tay là đủ). */
function _foreignTrendSVG(rows) {
  if (!rows || rows.length < 2) return "";
  const w = 640, h = 90, pad = 4, barGap = 2;
  const n = rows.length;
  const barW = Math.max(2, (w - pad * 2) / n - barGap);
  const maxAbs = Math.max(...rows.map(r => Math.abs(r.net || 0)), 1);
  const midY = h / 2;
  const bars = rows.map((r, idx) => {
    const x = pad + idx * (barW + barGap);
    const bh = Math.abs(r.net) / maxAbs * (h / 2 - 6);
    const y = r.net >= 0 ? midY - bh : midY;
    const cls = r.net >= 0 ? "var(--up)" : "var(--down)";
    return `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${barW.toFixed(1)}" height="${Math.max(bh, 1).toFixed(1)}" fill="${cls}"><title>${_esc(r.date)}: ${r.net >= 0 ? "+" : ""}${_fmtShares(r.net)}</title></rect>`;
  }).join("");
  return `<svg viewBox="0 0 ${w} ${h}" style="width:100%;height:${h}px;display:block;margin-top:10px">
    <line x1="${pad}" y1="${midY}" x2="${w - pad}" y2="${midY}" stroke="var(--muted)" stroke-width="1" opacity="0.35"/>
    ${bars}</svg>
    <div style="display:flex;justify-content:space-between;font-size:11px;color:var(--muted);margin-top:2px">
      <span>${_esc(rows[0].date)}</span><span>${_esc(rows[rows.length - 1].date)}</span></div>`;
}

async function drawForeign(d) {
  const host = $("#ov-foreign");
  const b = await _board();
  const hist = (d && d.foreign_history) || [];
  if ((!b || (b.foreignBuy == null && b.foreignSell == null)) && !hist.length) {
    host.innerHTML = `<h3 class="sec-h">Giao dịch khối ngoại</h3><div class="chart-empty">Chưa có dữ liệu khối ngoại (cần bảng giá LIVE).</div>`; return;
  }
  const net = b ? (b.foreignBuy || 0) - (b.foreignSell || 0) : null;
  const c = net != null && net >= 0 ? "chg-up" : "chg-down";
  // B9: đơn vị rõ ràng — cổ phiếu lớn co về "triệu cp"; kèm nhãn ròng mua/bán.
  host.innerHTML = `<h3 class="sec-h">Giao dịch khối ngoại <span class="src">Bảng giá phiên gần nhất · khối lượng khớp</span></h3>
    ${b ? `<div class="kpi-row">
      ${kpi("KL mua", _fmtShares(b.foreignBuy || 0), "khối ngoại mua vào", "good")}
      ${kpi("KL bán", _fmtShares(b.foreignSell || 0), "khối ngoại bán ra", "down")}
    </div>
    <div style="font-size:14px;margin-top:6px">Ròng phiên: <b class="${c}">${net >= 0 ? "+" : ""}${_fmtShares(net)}</b> — ${net >= 0 ? "khối ngoại MUA ròng" : "khối ngoại BÁN ròng"}</div>` : ""}
    ${hist.length >= 2 ? `<div style="margin-top:12px">
      <b style="color:var(--muted);font-size:12.5px">Xu hướng ròng ${hist.length} phiên gần nhất</b>
      ${_foreignTrendSVG(hist)}
    </div>` : hist.length ? `<div class="src" style="margin-top:8px">Mới tích lũy ${hist.length} phiên — cần thêm dữ liệu để thấy xu hướng.</div>` : ""}`;
}

/* B9: format khối lượng cổ phiếu — số lớn co về "triệu cp" để dễ đọc + rõ đơn vị. */
function _fmtShares(v) {
  if (v == null || !isFinite(v)) return "—";
  const a = Math.abs(v);
  if (a >= 1e6) return fmtVN(v / 1e6, 2) + " triệu cp";
  if (a >= 1e3) return fmtVN(v / 1e3, 1) + " nghìn cp";
  return fmtVN(v, 0) + " cp";
}

function drawHealth(d) {
  const host = $("#ov-health");
  const h = d.health;
  if (!h || h.health_score == null) { host.innerHTML = `<h3 class="sec-h">Sức khỏe doanh nghiệp</h3><div class="chart-empty">Mã này chưa được chấm điểm sức khỏe — cần đủ báo cáo tài chính đã kiểm toán.</div>`; return; }
  const notes = [];
  if (h.z_zone) notes.push({ t: `Altman Z'': ${h.z_score != null ? fmtVN(h.z_score, 2) : "—"} — vùng ${h.z_zone}`, kind: h.z_zone === "An toàn" ? "ok" : h.z_zone === "Nguy hiểm" ? "bad" : "neu" });
  notes.push({ t: `Piotroski F: ${h.f_score}/${h.f_max}`, kind: h.f_score >= 6 ? "ok" : h.f_score <= 3 ? "bad" : "neu" });
  if (h.roe != null) notes.push({ t: `ROE ${fmtVN(h.roe, 1)}% · ROA ${h.roa != null ? fmtVN(h.roa, 1) : "—"}%`, kind: h.roe >= 15 ? "ok" : "neu" });
  /* §1.1 · Đây là NGUỒN CHÂN LÝ DUY NHẤT cho "điểm sức khỏe" của trang, vì
     business_health có công thức công khai trên trang Phương pháp. Con số
     ai.data.metrics.health_score (thang /8, chốt theo quý) KHÔNG được render ở
     đâu dưới cùng tên — xem drawProfile() để biết cách đóng nhãn kỳ.
     §1.2 · KHÔNG truyền ts: h.year — h.year là NĂM TÀI CHÍNH (vd 2025), còn
     sourceTag() hiểu tham số thứ 2 là timestamp nên 2025 bị đọc thành 2025ms
     sau epoch → "01/01/1970". Năm tài chính đi vào nhãn `sub` dạng chữ. */
  host.innerHTML = `<h3 class="sec-h">Sức khỏe doanh nghiệp
    <span class="src">Altman Z'' + Piotroski F + ROA · công thức công khai trên trang Phương pháp</span></h3>`;
  const gbox = document.createElement("div"); gbox.className = "gauge-box"; host.appendChild(gbox);
  M.svgGauge(gbox, h.health_score, {
    sub: h.year ? `Điểm sức khỏe 0–100 · số liệu năm ${h.year}` : "Điểm sức khỏe 0–100",
    notes, source: "market.db · business_health",
  });
  host.insertAdjacentHTML("beforeend",
    `<div class="disclaimer">Đây là điểm sức khỏe duy nhất của trang. Các con số trong
     phần nhận xét bằng AI được chốt ở kỳ báo cáo khác nên có thể lệch chút ít —
     phần đó luôn ghi rõ kỳ.</div>`);
  if ((h.watch_flags || []).includes("weak_combo"))
    host.insertAdjacentHTML("beforeend", `<div class="disclaimer" style="color:var(--down)">⚠ Cờ theo dõi: Z'' nguy hiểm + F thấp — trạng thái mô tả, không phải khuyến nghị.</div>`);
}

/* §1.3 · Badge tuổi dữ liệu ĐẶT CẠNH con số giá. Ngưỡng theo PHIÊN giao dịch
   (bỏ cuối tuần), không theo giờ: xanh ≤1 phiên · vàng 2–5 · đỏ >5.
   Màu luôn kèm chữ + aria-label để không phụ thuộc vào việc phân biệt màu. */
function _sessionsSince(iso) {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return null;
  let n = 0;
  const cur = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const today = new Date();
  const end = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  while (cur < end) {
    cur.setDate(cur.getDate() + 1);
    const w = cur.getDay();
    if (w !== 0 && w !== 6) n++;
  }
  return n;
}

function mountPriceAge(d) {
  const host = document.getElementById("px-age");
  if (!host) return;
  const asOf = d.price && d.price.as_of;
  if (!asOf) {
    host.innerHTML = `<span class="f0-age f0-age-stale" role="status"
      aria-label="Chưa rõ thời điểm của dữ liệu giá"><span class="f0-dot" aria-hidden="true"></span>chưa rõ thời điểm</span>`;
    return;
  }
  const s = _sessionsSince(asOf);
  const cls = s == null ? "f0-age-stale" : s <= 1 ? "f0-age-fresh" : s <= 5 ? "f0-age-warn" : "f0-age-stale";
  const text = s == null ? "chưa rõ thời điểm"
    : s === 0 ? "số liệu phiên hôm nay"
    : s === 1 ? "số liệu phiên gần nhất"
    : `số liệu cũ ${s} phiên giao dịch`;
  host.innerHTML =
    `<span class="f0-age ${cls}" role="status" aria-label="Độ mới của dữ liệu giá: ${_esc(text)}, chốt ngày ${_esc(fmtDateVN(asOf, false))}">
       <span class="f0-dot" aria-hidden="true"></span>${_esc(text)}</span>
     <button type="button" class="f0-refresh" id="px-refresh">Cập nhật ngay</button>
     <span class="f0-age-note" id="px-refresh-state"></span>`;
  document.getElementById("px-refresh").addEventListener("click", _runPriceRefresh);
  _dbAgeNote();
}

/* Dòng phụ về tuổi cơ sở dữ liệu — /api/health chỉ có db_age_s và tuổi các file
   JSON, KHÔNG có tuổi bảng price, nên nó là thông tin bổ trợ chứ không phải
   nguồn chính cho badge trên (badge tính từ price.as_of). */
async function _dbAgeNote() {
  try {
    const h = await (await fetch("/api/health")).json();
    if (h.db_age_s == null) return;
    const hrs = Math.round(h.db_age_s / 3600);
    const txt = hrs < 24 ? `${hrs} giờ trước` : `${Math.round(hrs / 24)} ngày trước`;
    const el = document.getElementById("px-refresh-state");
    if (el && !el.textContent) el.textContent = `· cơ sở dữ liệu ghi lần cuối ${txt}`;
  } catch (_) { /* không có /api/health thì badge vẫn đủ dùng */ }
}

let _pxPoll = null;
async function _runPriceRefresh() {
  const btn = document.getElementById("px-refresh");
  const box = document.getElementById("px-refresh-state");
  btn.disabled = true; box.textContent = "· đang cập nhật giá, mất 1–2 phút…";
  try {
    const r = await (await fetch("/api/market/refresh_prices", { method: "POST" })).json();
    if (r.msg) box.textContent = "· " + r.msg;
    clearInterval(_pxPoll);
    _pxPoll = setInterval(async () => {
      try {
        const s = await (await fetch("/api/market/refresh_prices/status")).json();
        if (s.running) return;
        clearInterval(_pxPoll); _pxPoll = null; btn.disabled = false;
        box.innerHTML = s.error
          ? "· cập nhật lỗi: " + _esc(String(s.error).slice(0, 120))
          : `· đã cập nhật xong — <a href="#" onclick="location.reload();return false">tải lại trang</a>`;
      } catch (_) { /* mạng chập chờn → thử lại nhịp sau */ }
    }, 5000);
  } catch (e) {
    btn.disabled = false;
    box.textContent = "· không gửi được yêu cầu: " + e.message;
  }
}

/* §3.1 · "Doanh nghiệp này làm gì?" — hiện NGAY khi API trả company_profile.
   WS-4 chưa mở whitelist _SAFE_PROFILE_KEYS thì phần mô tả tự vắng và card chỉ
   còn bảng dữ kiện; nếu vắng cả hai thì card tự ẩn, không để lại ô rỗng. */
function drawWhatCompanyDoes(d) {
  const host = document.getElementById("ov-what");
  if (!host) return;
  const i = d.info || {};
  const text = String(i.company_profile || "").trim();
  const fact = (k, v) => v == null || v === "" ? "" : `<div><span class="k">${k}:</span> ${v}</div>`;
  const pct = (v) => v == null ? null : fmtVN(v * (Math.abs(v) <= 1 ? 100 : 1), 2) + "%";
  /* Chỉ nhận giá trị THẬT: secVI() luôn trả "Khác" và i.exchange hay được thay
     bằng "—", nếu tính chúng là "có dữ liệu" thì card không bao giờ ẩn được. */
  const facts = [
    fact("Tên đầy đủ", i.organ_name || i.name ? _esc(i.organ_name || i.name) : null),
    fact("Ngành", i.sector ? _esc(secVI(i.sector)) : null),
    fact("Sàn niêm yết", i.exchange ? _esc(i.exchange) : null),
    fact("Số lượng cổ phiếu lưu hành", i.issue_share != null ? _fmtShares(i.issue_share) : null),
    fact("Nhà đầu tư nước ngoài đang giữ", pct(i.foreigner_percentage)),
    fact("Giới hạn sở hữu nước ngoài", pct(i.maximum_foreign_percentage)),
    fact("Nhà nước đang giữ", pct(i.state_percentage)),
  ].join("");
  if (!text && !facts) { host.hidden = true; return; }
  host.hidden = false;
  const long = text.length > 420;
  host.innerHTML = `<h3 class="sec-h">Doanh nghiệp này làm gì?
      <span class="src">Hồ sơ doanh nghiệp đã lưu · dữ kiện, không phải nhận định</span></h3>
    ${text ? `<div class="f0-profile-text${long ? " clamped" : ""}" id="f0-prof">${_esc(text)}</div>
      ${long ? `<button type="button" class="f0-more" id="f0-prof-more"
        aria-expanded="false" aria-controls="f0-prof">Đọc tiếp</button>` : ""}`
      : `<div class="f0-kicker">Chưa có phần mô tả hoạt động kinh doanh cho mã này.</div>`}
    ${facts ? `<div class="f0-facts">${facts}</div>` : ""}`;
  const more = document.getElementById("f0-prof-more");
  if (more) more.addEventListener("click", () => {
    const box = document.getElementById("f0-prof");
    const open = box.classList.toggle("clamped") === false;
    more.textContent = open ? "Thu gọn" : "Đọc tiếp";
    more.setAttribute("aria-expanded", String(open));
  });
}

/* §3.2 + Phase 2.4 · Card cổ tức rỗng → TIMELINE mọi sự kiện doanh nghiệp,
   cổ tức chỉ là một loại. Lịch sử cổ tức lấy bổ sung từ /analysis vì
   /api/stock/<sym> hiện chỉ trả 8 sự kiện mới nhất — với FPT cả 8 dòng đều là
   phát hành/giao dịch nội bộ, value_per_share NULL, nên bộ lọc cổ tức cũ luôn
   rỗng dù DB có dữ liệu thật. */
const _EV_KIND = [
  [/cổ tức/i,                             "cash",    "Cổ tức"],
  [/phát hành|niêm yết|cổ phiếu thưởng/i, "share",   "Cổ phiếu"],
  [/nội bộ/i,                             "insider", "Giao dịch nội bộ"],
  [/cổ đông|đhđcđ|đại hội/i,              "meeting", "Đại hội cổ đông"],
];
function _evKind(label) {
  for (const [re, k, vi] of _EV_KIND) if (re.test(label)) return { k, vi };
  return { k: "other", vi: "Khác" };
}

async function drawEventTimeline(d) {
  const host = document.getElementById("ov-events") || document.getElementById("ov-dividends");
  if (!host) return;
  const HEAD = `<h3 class="sec-h">Sự kiện doanh nghiệp
      <span class="src">Cổ tức, phát hành, niêm yết thêm, giao dịch nội bộ · dữ kiện đã công bố</span></h3>`;
  /* CHỒNG CHÉO ĐÃ SỬA: cùng một lần trả cổ tức tới đây từ HAI nguồn — `events`
     (nhãn dài: "Trả cổ tức bằng tiền mặt Trả cổ tức bằng tiền mặt - Đợt 2 2025
     - 1,000 VND") và `dividends.history` (nhãn ngắn: "Trả cổ tức bằng tiền
     mặt"). Khóa chống trùng cũ là `ngày|nhãn` nên hai nhãn khác nhau lọt cả
     hai ⇒ cổ tức 22/05/2026 hiện đúng 2 dòng liền nhau. Với cổ tức tiền mặt,
     một NGÀY chỉ có một lần chi trả, nên khóa theo `ngày|cash` là đủ; bản ghi
     nào có số tiền/cổ phiếu thì thắng. */
  const seen = new Map();
  const items = [];
  const push = (date, label, vps) => {
    if (!date) return;
    const kind = _evKind(label);
    const key = kind.k === "cash" ? `${date}|cash` : `${date}|${label}`;
    const old = seen.get(key);
    if (old) {
      if (old.vps == null && vps != null) { old.vps = vps; old.label = label; }
      return;
    }
    const row = { date, label, vps: vps == null ? null : vps, ...kind };
    seen.set(key, row);
    items.push(row);
  };
  (d.events || []).forEach(e => push(e.date, `${e.event || ""} ${e.title || ""}`.trim(), e.value_per_share));

  host.innerHTML = HEAD + `<div class="f0-kicker">Đang tải lịch sử cổ tức…</div>`;

  /* Bổ sung cổ tức tiền mặt. Lỗi/thiếu → vẫn vẽ timeline từ d.events. */
  let dy = null;
  try {
    const a = await (await fetch(`/api/stock/${encodeURIComponent(SYM)}/analysis`)).json();
    const dv = a && a.dividends;
    if (dv) {
      dy = dv.dividend_yield;
      (dv.history || []).forEach(x => push(x.date, x.event || "Trả cổ tức bằng tiền mặt", x.value_per_share));
    }
  } catch (_) { /* endpoint phân tích chưa sẵn → bỏ qua, không làm vỡ card */ }
  /* Nếu backend nâng LIMIT hoặc thêm khóa `dividends` vào /api/stock thì tự dùng. */
  ((d.dividends && d.dividends.history) || []).forEach(
    x => push(x.date, x.event || "Trả cổ tức bằng tiền mặt", x.value_per_share));

  if (!items.length) {
    host.innerHTML = HEAD + `<div class="chart-empty">Chưa ghi nhận sự kiện đã công bố nào của mã này.</div>`;
    return;
  }
  items.sort((a, b) => String(b.date).localeCompare(String(a.date)));
  const kinds = [...new Set(items.map(x => x.k))];
  const kindVI = Object.fromEntries(items.map(x => [x.k, x.vi]));
  const cash = items.filter(x => x.k === "cash" && x.vps != null);

  /* MẶC ĐỊNH BỎ GIAO DỊCH NỘI BỘ khỏi dòng thời gian này. FPT có 21/30 sự kiện
     là giao dịch nội bộ, tất cả dồn vào 2 ngày — chúng chiếm trọn 20 dòng hiển
     thị và đẩy cổ tức, phát hành, ĐHĐCĐ ra khỏi tầm nhìn, đúng thứ người ta mở
     card này để xem. Chúng không mất đi: có nút lọc ngay bên cạnh, và tab
     "Tin & Sự kiện" có hẳn một khối riêng cho chúng. */
  const insiderN = items.filter(x => x.k === "insider").length;
  const shown = insiderN && items.length > insiderN
    ? items.filter(x => x.k !== "insider") : items;

  const li = (x) => `<li class="is-${x.k}">
      <div><span class="f0-tl-date">${_esc(fmtDateVN(x.date, false))}</span>
        · ${_esc(x.label || "Sự kiện")}${x.vps != null
          ? ` <span class="f0-tl-val">${fmtVN(x.vps, 0)} đồng/cổ phiếu</span>` : ""}</div></li>`;

  host.innerHTML = HEAD +
    `${cash.length ? `<div class="f0-kicker">Lần trả cổ tức tiền mặt gần nhất:
      <b>${fmtVN(cash[0].vps, 0)} đồng/cổ phiếu</b> ngày ${_esc(fmtDateVN(cash[0].date, false))}${
      dy != null ? ` · tỷ suất cổ tức ${fmtVN(dy, 2)}% (cổ tức một năm chia cho giá hiện tại)` : ""}.</div>`
      : `<div class="f0-kicker">Chưa ghi nhận cổ tức tiền mặt trong dữ liệu đã lưu.</div>`}
    ${kinds.length > 1 ? `<div class="f0-tl-filter" role="group" aria-label="Lọc sự kiện theo loại">
        <button type="button" data-k="corp" aria-pressed="true">Sự kiện doanh nghiệp</button>
        <button type="button" data-k="all" aria-pressed="false">Tất cả</button>
        ${kinds.map(k => `<button type="button" data-k="${k}" aria-pressed="false">${_esc(kindVI[k])}${
          k === "insider" ? ` (${insiderN})` : ""}</button>`).join("")}
      </div>` : ""}
    <ul class="f0-tl">${shown.slice(0, 20).map(li).join("")}</ul>
    ${insiderN && shown !== items
      ? `<p class="f0-tl-note">Đã ẩn ${insiderN} giao dịch nội bộ để cổ tức và phát hành
           không bị lấp — bấm “Giao dịch nội bộ” ở trên để xem.</p>` : ""}
    <div style="margin-top:8px">${sourceTag("market.db · events")}</div>`;

  host.querySelectorAll(".f0-tl-filter button").forEach(b =>
    b.addEventListener("click", () => {
      const k = b.dataset.k;
      host.querySelectorAll(".f0-tl-filter button").forEach(x =>
        x.setAttribute("aria-pressed", String(x === b)));
      const list = k === "all" ? items
        : k === "corp" ? shown
        : items.filter(x => x.k === k);
      host.querySelector(".f0-tl").innerHTML = list.slice(0, 20).map(li).join("");
    }));
}

/* §1.1 · Card này TỪNG mang tên "Hồ sơ doanh nghiệp" và đứng cạnh card sức khỏe,
   nên hai bộ chỉ số (business_health chốt theo năm vs AI chốt theo quý) đọc như
   mâu thuẫn — ROE 25,7% ở card bên, 23,59% trong đoạn văn AI. Nay đổi tên thành
   "Thanh khoản & quy mô", và mọi số của AI phải đi kèm nhãn kỳ báo cáo. */
function drawProfile(d) {
  const host = $("#ov-profile");
  const i = d.info, a = d.ai && d.ai.data;
  const per = a && a.metrics && a.metrics.net_profit && a.metrics.net_profit.period;
  host.innerHTML = `<h3 class="sec-h">Thanh khoản &amp; quy mô
      <span class="src">Bình quân một tháng · market.db + hồ sơ doanh nghiệp</span></h3>
    <div style="font-size:13.5px;line-height:1.7">
      <div><span style="color:var(--muted)">Vốn hóa thị trường:</span> ${i.market_cap != null ? fmtMoney(i.market_cap) : "—"}</div>
      <div><span style="color:var(--muted)">Khối lượng khớp bình quân:</span> ${i.average_match_volume1_month != null ? _fmtShares(i.average_match_volume1_month) : "—"}</div>
      <div><span style="color:var(--muted)">Giá trị khớp bình quân:</span> ${i.average_match_value1_month != null ? fmtMoney(i.average_match_value1_month) : "—"}</div>
      <div><span style="color:var(--muted)">Cao – thấp 52 tuần:</span> ${i.lowest_price1_year != null && i.highest_price1_year != null
        ? fmtVN(i.lowest_price1_year, 0) + " – " + fmtVN(i.highest_price1_year, 0) : "—"}</div>
    </div>
    ${a && a.fundamental_summary ? `
      <div class="disclaimer-box" style="margin-top:12px">
        <b style="color:var(--muted)">Nhận xét của AI${per ? ` · số liệu kỳ ${_esc(per)}` : ""}</b>
        <div style="margin-top:4px">${_esc(String(a.fundamental_summary))}</div>
        <div style="margin-top:6px">Các chỉ số trong đoạn này được AI chốt ở kỳ báo cáo
          riêng, nên có thể lệch so với điểm sức khỏe (chốt theo năm tài chính).
          Điểm sức khỏe ở card bên là con số chính thức của trang.</div>
      </div>` : ""}`;
}

/* §20 · Sở hữu & Quản trị (P1-P4 kế hoạch đưa dữ liệu Crawl Data lên 9999) —
   4 khối cào sẵn ở companies/<mã>/ownership/*.json nhưng chưa từng nối ra API
   trước bản này (xem api.py::stock_detail, "ownership"). Thuần dữ kiện mô tả
   (ai giữ chức gì, sở hữu bao nhiêu, công ty con nào, vốn điều lệ qua các đợt),
   không có rating/target nên không vướng legal.py. */
function drawOwnership(d) {
  const host = $("#ov-ownership");
  if (!host) return;
  const o = d.ownership || {};
  const hasAny = (o.officers || []).length || (o.subsidiaries || []).length
    || (o.shareholders || []).length || (o.capital_history || []).length;
  if (!hasAny) {
    host.innerHTML = `<h3 class="sec-h">Sở hữu &amp; quản trị</h3>
      <div class="chart-empty">Chưa có hồ sơ sở hữu của mã này trong dữ liệu đã cào.</div>`;
    return;
  }
  const pct = (v) => v != null ? fmtVN(v * 100, 2) + "%" : "—";
  const officersHTML = (o.officers || []).length ? `<div>
      <b style="color:var(--muted);font-size:12.5px">Ban lãnh đạo</b>
      <div class="table-wrap" style="margin-top:4px"><table><thead><tr>
        <th>Họ tên</th><th>Chức vụ</th><th class="num">Sở hữu</th></tr></thead><tbody>
        ${o.officers.map(x => `<tr><td>${_esc(x.name || "")}</td><td>${_esc(x.position || "—")}</td>
          <td class="num">${pct(x.own_percent)}</td></tr>`).join("")}
      </tbody></table></div></div>` : "";

  const subsHTML = (o.subsidiaries || []).length ? `<div style="margin-top:14px">
      <b style="color:var(--muted);font-size:12.5px">Công ty con / liên kết <span class="pill-n">${o.subsidiaries.length}</span></b>
      <div class="table-wrap" style="margin-top:4px"><table><thead><tr>
        <th>Tên</th><th class="num">Sở hữu</th></tr></thead><tbody>
        ${o.subsidiaries.map(x => `<tr><td>${_esc(x.name || "")}${x.code ? ` <span class="src">(${_esc(x.code)})</span>` : ""}</td>
          <td class="num">${pct(x.own_percent)}</td></tr>`).join("")}
      </tbody></table></div></div>` : "";

  const shHTML = (o.shareholders || []).length ? `<div style="margin-top:14px">
      <b style="color:var(--muted);font-size:12.5px">Cổ đông lớn${o.shareholders_total > o.shareholders.length
        ? ` <span class="src">— top ${o.shareholders.length}/${o.shareholders_total}</span>` : ""}</b>
      <div class="table-wrap" style="margin-top:4px"><table><thead><tr>
        <th>Cổ đông</th><th class="num">Số lượng CP</th><th class="num">Tỷ lệ</th></tr></thead><tbody>
        ${o.shareholders.map(x => `<tr><td>${_esc(x.name || "")}</td>
          <td class="num">${x.quantity != null ? _fmtShares(x.quantity) : "—"}</td>
          <td class="num">${pct(x.own_percent)}</td></tr>`).join("")}
      </tbody></table></div></div>` : "";

  const capHTML = (o.capital_history || []).length ? `<div style="margin-top:14px">
      <b style="color:var(--muted);font-size:12.5px">Lịch sử vốn điều lệ</b>
      <div class="table-wrap" style="margin-top:4px"><table><thead><tr>
        <th>Ngày</th><th class="num">Vốn điều lệ</th></tr></thead><tbody>
        ${o.capital_history.map(x => `<tr><td>${_esc(x.date || "")}</td>
          <td class="num">${x.charter_capital != null ? fmtMoney(x.charter_capital) : "—"}</td></tr>`).join("")}
      </tbody></table></div></div>` : "";

  host.innerHTML = `<h3 class="sec-h">Sở hữu &amp; quản trị
      <span class="src">companies/${SYM}/ownership · dữ kiện mô tả, không phải khuyến nghị</span></h3>
    ${officersHTML}${subsHTML}${shHTML}${capHTML}`;
}

function drawRelated(d) {
  const host = $("#ov-related");
  const rows = (d.peer_rows || []).slice(0, 6);
  if (!rows.length) { host.innerHTML = `<h3 class="sec-h">Có thể bạn quan tâm</h3><div class="chart-empty">Chưa có mã cùng ngành được chấm điểm.</div>`; return; }
  host.innerHTML = `<h3 class="sec-h">Có thể bạn quan tâm <span class="src">Cùng ngành ${_esc(d.peers && d.peers.sector || "")}</span></h3>
    <div class="rel-chips">` + rows.map(r => `
      <a class="rel-chip" href="/co-phieu/${r.symbol}">${M.symLogoHTML(r.symbol)}
        <span><span class="rc-sym">${r.symbol}</span> <span class="rc-ex">${_esc((r.name || "").slice(0, 24))}</span></span>
        <span style="margin-left:auto;font-size:12.5px;color:var(--muted)">SK ${r.health != null ? fmtVN(r.health, 0) : "—"} · ROE ${r.roe != null ? fmtVN(r.roe, 1) + "%" : "—"}</span>
      </a>`).join("") + `</div>`;
}

/* ---------- TAB TIN & SỰ KIỆN ---------- */
/* B13: mọi hàng tin/sự kiện LUÔN bấm được → mở panel chi tiết nội bộ.
   Có source_link thật → icon ↗ mở tab mới; không có → nút "Tìm bài gốc" (Google). */
function _newsSearchUrl(title) {
  return "https://www.google.com/search?q=" + encodeURIComponent(`${SYM} ${title || ""}`.trim());
}
function toggleNewsDetail(id) {
  const el = document.getElementById(id);
  if (el) el.hidden = !el.hidden;
}

/* Ảnh 12 · Nói rõ độ tươi của tin thay vì để người đọc tự đoán. Kiểm kê thực tế
   (scripts/audit_news_coverage.py) cho thấy 0 mã trắng tin, 8 mã UPCOM tin cũ
   >180 ngày — nên vấn đề là THIẾU BỐI CẢNH, không phải thiếu dữ liệu. */
function newsFreshnessNote(news) {
  if (!news.length) return "";
  const times = news.map(n => new Date(n.date).getTime()).filter(t => isFinite(t));
  if (!times.length) return "";
  const days = Math.floor((Date.now() - Math.max(...times)) / 86400000);
  if (days <= 30) return "";
  const muc = days > 180 ? "age-old" : "age-day";
  return `<div class="disclaimer" style="margin:0 0 10px">
    <span class="age-badge ${muc}">tin mới nhất ${days} ngày trước</span>
    Chưa ghi nhận công bố mới trong ${days} ngày — có thể doanh nghiệp không phát sinh
    thông tin phải công bố. Nguồn: CBTT trong market.db, không phải toàn bộ báo chí.</div>`;
}

/* Nhúng chuỗi vào thuộc tính onclick an toàn (tin có dấu nháy, xuống dòng). */
function _jsq(s) {
  return JSON.stringify(String(s == null ? "" : s)).replace(/"/g, "&quot;");
}

/* Nhờ AI giải thích 1 bản tin — CHẠY KHI BẤM, không tự gọi.
   Tiêu đề công bố viết theo văn phong pháp lý nên người mới đọc xong vẫn không
   hiểu chuyện gì; đây là chỗ 1 lượt AI đáng giá nhất. Kết quả nhớ theo tiêu đề
   trong phiên để bấm lại không tốn thêm lượt. */
const _newsAiCache = new Map();
async function askNewsAI(btn, title, date, content, link, publisher) {
  const out = btn.closest(".news-detail").querySelector(".news-ai-out");
  const key = title + "|" + date;
  if (_newsAiCache.has(key)) {
    out.innerHTML = _newsAiCache.get(key);
    return;
  }
  btn.disabled = true;
  const old = btn.textContent;
  // Có link bài gốc thì server sẽ TẢI NGUYÊN BÀI về trước khi hỏi AI — mất vài
  // giây, nên nói rõ đang làm gì thay vì để nút đứng im.
  btn.textContent = link ? "AI đang đọc bài gốc…" : "AI đang đọc…";
  out.innerHTML = "";
  try {
    const r = await fetch(`/api/stock/${encodeURIComponent(SYM)}/news_ai`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, date, content, link: link || "", publisher: publisher || "" }),
    });
    const j = await r.json();
    if (!j.ok) throw new Error(j.msg || "lỗi không rõ");
    /* Nói THẬT AI vừa đọc được gì. "Đọc nguyên bài 3.812 ký tự" và "chỉ có mỗi
       tiêu đề" là hai mức độ tin cậy khác hẳn nhau, người đọc phải phân biệt
       được trước khi tin lời giải thích. */
    const prov = j.read_source
      ? `<div class="news-ai-src">✓ AI đã đọc nguyên bài gốc (${(j.chars || 0).toLocaleString("vi-VN")} ký tự)</div>`
      : `<div class="news-ai-src warn">⚠ AI chỉ đọc được tiêu đề${j.note ? " — " + _esc(j.note) : ""}</div>`;
    const html = `<div class="news-ai-txt">${_esc(j.answer)}</div>` + prov;
    _newsAiCache.set(key, html);
    out.innerHTML = html;
  } catch (e) {
    out.innerHTML = `<div class="news-ai-txt err">Không giải thích được: ${_esc(e.message)}</div>`;
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

/* Một hàng tin dùng chung cho cả 4 khối (báo chí / CBTT / sự kiện / nội bộ) —
   trước đây mỗi khối tự dựng HTML riêng nên sửa một chỗ là lệch ba chỗ kia. */
function newsRow(o) {
  const pid = o.pid;
  const ext = o.link
    ? `<a class="news-ext" href="${_esc(o.link)}" target="_blank" rel="noopener" title="Mở bài gốc ở tab mới" onclick="event.stopPropagation()">↗ Bài gốc</a>`
    : `<a class="news-ext" href="${_esc(_newsSearchUrl(o.title))}" target="_blank" rel="noopener" title="Tìm bài gốc trên Google" onclick="event.stopPropagation()">🔍 Tìm bài gốc</a>`;
  return `<div class="news-row" role="button" tabindex="0" onclick="toggleNewsDetail('${pid}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();toggleNewsDetail('${pid}')}">
    <div class="news-line">
      <span class="news-date">${_esc(fmtDateVN(o.date))}</span>
      <span class="news-title">${o.badge || ""}${_esc(o.title)}</span>
      ${o.publisher ? `<span class="news-pub">${_esc(o.publisher)}</span>` : ""}
      ${o.right || ""}
      <span class="news-caret">▸</span>
    </div>
    <div class="news-detail" id="${pid}" hidden>
      ${o.body ? `<p>${_esc(o.body)}</p>` : `<p class="muted">${_esc(o.emptyText || "Bản tin không có nội dung tóm tắt trong dữ liệu.")}</p>`}
      <div class="news-acts">
        <button type="button" class="news-ai-btn"
          onclick="event.stopPropagation();askNewsAI(this,${_jsq(o.title)},${_jsq(o.date)},${_jsq(o.body || "")},${_jsq(o.link || "")},${_jsq(o.publisher || "")})">
          ${o.link ? "Nhờ AI đọc bài này" : "Nhờ AI giải thích"}</button>
        ${ext}
        <span class="news-cite"><span class="badge">[${_esc(o.id)}]</span> ${_esc(o.cite)}</span>
      </div>
      <div class="news-ai-out"></div>
    </div></div>`;
}

function renderNewsTab(d) {
  /* (1) BÁO CHÍ — đặt trên cùng vì đây là khối DUY NHẤT có toà soạn đứng tên và
     link kiểm chứng được, cũng là khối duy nhất AI đọc được nguyên bài. Nguồn:
     companies/<mã>/news/press.json + articles.json, trước đây chỉ xem được ở
     tab "Dữ liệu gốc" nên coi như không tồn tại với người dùng. */
  const press = d.press || [];
  $("#press-body").innerHTML = `<h3 class="sec-h">Báo chí viết gì
      <span class="src">Google News RSS + Vietstock · có tên toà soạn và link bài gốc · AI đọc được nguyên bài</span></h3>`
    + (press.length
      ? press.map(p => newsRow({
          pid: `pd-${p.id}`, id: p.id, cite: p.publisher || "báo chí",
          title: p.title, date: p.date, body: p.summary, link: p.link,
          publisher: p.publisher,
          emptyText: "Chưa tải nội dung — bấm “Nhờ AI đọc bài này” để hệ thống tải bài gốc về.",
        })).join("")
      : `<div class="chart-empty">Chưa cào được bài báo nào cho mã này.
           Chạy lại bước P2 (crawler_company) để lấy báo chí.</div>`);

  /* (2) TIN CBTT — chỉ có tiêu đề pháp lý. Đo thật: 0/50 bản ghi của FPT có
     source_link hoặc short_content, nên nói thẳng thay vì để ô trống khó hiểu. */
  const news = d.news || [];
  $("#news-body").innerHTML = `<h3 class="sec-h">Công bố thông tin
      <span class="src">market.db · vnstock — chỉ có tiêu đề, nguồn không kèm nội dung</span></h3>`
    + newsFreshnessNote(news) + (news.length
      ? news.map(n => newsRow({
          pid: `nd-${n.id}`, id: n.id, cite: "CBTT",
          title: n.title, date: n.date,
          body: (n.content || n.summary || "").trim(), link: n.link,
          emptyText: "Nguồn CBTT chỉ cung cấp tiêu đề, không kèm nội dung.",
        })).join("")
      : `<div class="chart-empty">Chưa có tin CBTT của mã này trong DB.</div>`);

  /* (3) SỰ KIỆN DOANH NGHIỆP — đã bỏ giao dịch nội bộ ra (xem khối 4). Gateway
     cũ chưa trả `corp_events` thì lùi về `events` để trang không trắng. */
  const events = d.corp_events || d.events || [];
  $("#events-body").innerHTML = `<h3 class="sec-h">Sự kiện doanh nghiệp
      <span class="src">Cổ tức, phát hành, niêm yết thêm, ĐHĐCĐ — không gồm giao dịch nội bộ</span></h3>`
    + (events.length
      ? events.map(e => {
          const label = `${e.event || ""} ${e.title || ""}`.trim();
          return newsRow({
            pid: `ed-${e.id}`, id: e.id, cite: "công bố sự kiện",
            title: label || "Sự kiện", date: e.date,
            badge: e.upcoming ? badge("SẮP TỚI", "warn") + " " : "",
            right: e.value_per_share
              ? `<span class="news-val">${fmtVN(e.value_per_share, 0)} đ/cp</span>` : "",
            body: label + (e.value_per_share
              ? ` — giá trị ${fmtVN(e.value_per_share, 0)} đ/cp` : ""),
          });
        }).join("")
      : `<div class="chart-empty">Chưa có sự kiện doanh nghiệp của mã này trong DB.</div>`);

  /* (4) GIAO DỊCH NỘI BỘ — tách hẳn ra. Chúng chiếm 21/30 sự kiện của FPT; để
     lẫn thì đẩy hết cổ tức và phát hành ra khỏi tầm nhìn. Đồng thời đây chính
     là chỗ trước đây bị hiểu nhầm là "không có dữ liệu": nguồn KBS chuyên trách
     (ownership/insider_deals.json) trả rỗng, còn dữ liệu thật thì nằm ở đây. */
  const ins = d.insider || [];
  const insHost = $("#insider-body");
  if (insHost) {
    insHost.innerHTML = `<h3 class="sec-h">Giao dịch nội bộ <span class="pill-n">${ins.length}</span>
        <span class="src">Lãnh đạo và người liên quan đăng ký mua/bán — trích từ nguồn sự kiện của market.db.
        Nguồn KBS chuyên trách không trả dữ liệu cho hầu hết mã, nên đây mới là chỗ có số thật.</span></h3>`
      + (ins.length
        ? `<div class="ins-list">` + ins.map(e => {
            const label = `${e.event || ""} ${e.title || ""}`.trim();
            return newsRow({
              pid: `id-${e.id}`, id: e.id, cite: "giao dịch nội bộ",
              title: e.title || label, date: e.date, body: label,
            });
          }).join("") + `</div>`
        : `<div class="chart-empty">Không ghi nhận giao dịch nội bộ nào trong 40 sự kiện gần nhất.</div>`);
  }

  const ai = d.ai && d.ai.data;
  if (ai) {
    /* §21 · aspects{financial,valuation,growth,risk} là bản ĐẦY ĐỦ (điểm số +
       tín hiệu + kết luận riêng) của đúng nội dung mà fundamental_summary/
       valuation_comment/growth_comment/peer_comment tóm tắt lại — so hai bên
       thấy văn bản gần như trùng nhau (Crawl Data user.html đã chứng minh điều
       này bằng cách chỉ hiện aspects). Hiện CẢ HAI là lặp — gây rối mắt, đúng
       như phản hồi thực tế. Ưu tiên aspects (giàu hơn), CHỈ lùi về 4 đoạn văn
       phẳng khi mã chưa chạy multipass (ai.aspects rỗng — bản phân tích cũ). */
    const RISK_TONE = { low: "up", medium: "warn", high: "down" };
    const riskBadge = ai.risk_level
      ? badge(`Rủi ro: ${ { low: "thấp", medium: "vừa", high: "cao" }[ai.risk_level] || ai.risk_level }`,
          RISK_TONE[ai.risk_level] || "muted")
      : "";

    const IMPACT_LABEL = { positive: "Tích cực", negative: "Tiêu cực" };
    const impactBadge = (imp) => badge(IMPACT_LABEL[imp] || imp || "—",
      imp === "positive" ? "up" : imp === "negative" ? "down" : "muted");
    const scoreTone = (sc) => sc >= 70 ? "up" : sc >= 45 ? "warn" : "down";

    const asp = ai.aspects && typeof ai.aspects === "object" ? ai.aspects : null;
    let aspectsHTML = "";
    if (asp && Object.keys(asp).length) {
      const cards = Object.keys(asp).map(k => {
        const x = asp[k] || {};
        const sc = Number(x.score);
        const sig = (x.signals || []).map(s => `<div style="padding:4px 0;font-size:12.5px">
            ${impactBadge(s.impact)} <b>${_esc(s.label || "")}</b>
            <div style="color:var(--muted);margin-top:2px">${_esc(s.detail || "")}</div></div>`).join("");
        return `<div class="card" style="padding:12px">
          <div style="display:flex;justify-content:space-between;align-items:baseline">
            <b style="font-size:13.5px">${_esc(x.title || k)}</b>
            ${!isNaN(sc) ? badge(`${sc}/100`, scoreTone(sc)) : ""}
          </div>
          <div style="font-size:13px;margin-top:6px">${_esc(x.summary || "")}</div>
          ${sig ? `<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:6px">${sig}</div>` : ""}
          ${x.verdict ? `<div style="font-size:12.5px;color:var(--muted);margin-top:8px;border-left:2px solid var(--muted);padding-left:8px">${_esc(x.verdict)}</div>` : ""}
        </div>`;
      }).join("");
      aspectsHTML = `<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px">${cards}</div>`;
    } else {
      const TEXT_LABELS = {
        fundamental_summary: "Tóm tắt cơ bản", growth_comment: "Tăng trưởng",
        valuation_comment: "Định giá", peer_comment: "So sánh ngành",
      };
      aspectsHTML = Object.keys(TEXT_LABELS)
        .filter(k => ai[k])
        .map(k => `<div style="padding:6px 0"><b style="color:var(--muted);font-size:12.5px">${TEXT_LABELS[k]}</b>
          <div style="font-size:13.5px">${_esc(String(ai[k]))}</div></div>`).join("");
    }

    const drivers = Array.isArray(ai.key_drivers) && ai.key_drivers.length
      ? `<div style="padding:6px 0;margin-top:4px"><b style="color:var(--muted);font-size:12.5px">Động lực chính</b>
          <ul style="margin:4px 0 0 18px;font-size:13.5px">${ai.key_drivers.map(x => `<li>${_esc(String(x))}</li>`).join("")}</ul></div>`
      : "";

    const causesTbl = Array.isArray(ai.causes) && ai.causes.length
      ? `<div style="padding:6px 0"><b style="color:var(--muted);font-size:12.5px">Nguyên nhân chính</b>
          <div class="table-wrap" style="margin-top:4px"><table><thead><tr>
            <th>Nguyên nhân</th><th>Chiều</th><th class="num">Trọng số</th><th class="num">Độ tin cậy</th>
          </tr></thead><tbody>${ai.causes.map(c => `<tr>
            <td style="font-size:13px">${_esc(String(c.factor || ""))}</td>
            <td>${impactBadge(c.impact)}</td>
            <td class="num">${c.weight != null ? _esc(String(c.weight)) : "—"}</td>
            <td class="num">${c.confidence != null ? fmtVN(c.confidence * 100, 0) + "%" : "—"}</td>
          </tr>`).join("")}</tbody></table></div></div>`
      : "";

    $("#ai-body").innerHTML = `<div class="card">
      ${riskBadge ? `<div style="margin-bottom:6px">${riskBadge}</div>` : ""}
      ${aspectsHTML || "<div style='color:var(--muted)'>Bản phân tích không có trường hiển thị.</div>"}
      ${drivers}${causesTbl}
      <div style="margin-top:10px">${sourceTag(`[${d.ai.citation}] · ${d.ai.source}`, d.ai.updated_at)}</div>
      <div class="disclaimer">Phân tích dữ kiện tự động — KHÔNG phải khuyến nghị đầu tư.</div></div>`;
  } else {
    /* §18 · Mã chưa chạy P4: thay vì ngõ cụt, cho người dùng ĐẶT YÊU CẦU —
       worker `p4_analyze --queue` sẽ nhặt và chạy, UI tự hỏi tiến độ. */
    $("#ai-body").innerHTML = `
      <div class="card missing-card">
        <div class="mc-body"><span>Mã này chưa có bản phân tích báo cáo tài chính bằng AI.</span></div>
        <div class="ask-row" style="margin-top:10px">
          <button id="req-analysis" type="button">Yêu cầu phân tích mã này</button>
        </div>
        <div id="req-analysis-state" class="disclaimer" style="margin-top:8px"></div>
      </div>`;
    initRequestAnalysis();
  }
  const ac = document.getElementById("ask-copilot");
  if (ac) ac.onclick = () => location.href = "/copilot.html?q=" +
    encodeURIComponent(`${SYM} đang có những dữ kiện gì đáng chú ý theo BCTC và tin CBTT mới nhất?`);
}

/* ---------- TAB SỐ LIỆU TÀI CHÍNH ---------- */
function renderFinTab(d) {
  const f = d.fund || {};
  if (!f.error && (f.revenue_quarters || []).length) {
    const qcols = f.revenue_quarters.map(q => `<th class="num">${_esc(q.period)}</th>`).join("");
    const rrow = f.revenue_quarters.map(q => `<td class="num">${_esc(q.value_bn)}</td>`).join("");
    const prow = (f.profit_quarters || []).map(q => `<td class="num">${_esc(q.value_bn)}</td>`).join("");
    $("#fund-body").innerHTML = `<div class="table-wrap"><table>
      <thead><tr><th>Chỉ tiêu (tỷ đồng)</th>${qcols}</tr></thead>
      <tbody><tr><td>Doanh thu thuần</td>${rrow}</tr><tr><td>LNST</td>${prow}</tr></tbody></table></div>
      <div style="margin-top:8px;font-size:12.5px;color:var(--muted)">YoY năm — DT: <b>${_esc(f.revenue_yoy_year || "n/a")}</b> · LNST: <b>${_esc(f.profit_yoy_year || "n/a")}</b> · Nợ/VCSH: <b>${f.debt_to_equity != null ? fmtVN(f.debt_to_equity, 2) : "—"}</b></div>
      <div style="margin-top:6px">${sourceTag("market.db · BCTC chuẩn hóa (vnstock)")}</div>`;
  } else {
    $("#fund-body").innerHTML = `<div class="chart-empty">Chưa có dữ liệu BCTC — mã chưa crawl P1.</div>`;
  }
  renderPeers(d);
}

function renderPeers(d) {
  const p = d.peers, rows = d.peer_rows || [];
  if ((!p || p.error) && !rows.length) { $("#peers-body").innerHTML = `<div class="chart-empty">Chưa xác định được ngành / thiếu dữ liệu peer.</div>`; return; }
  let benchLine = "";
  if (p && !p.error) {
    benchLine = `<div class="interp-line">Trung vị ngành <b>${_esc(p.sector)}</b> (${p.n_peers} mã):
      P/E <b>${p.benchmark.pe != null ? fmtVN(p.benchmark.pe, 1) : "—"}</b> ·
      P/B <b>${p.benchmark.pb != null ? fmtVN(p.benchmark.pb, 1) : "—"}</b> ·
      ROE <b>${p.benchmark.roe != null ? fmtVN(p.benchmark.roe, 1) + "%" : "—"}</b>.
      ${_esc(SYM)}: P/E <b>${p.self.pe != null ? fmtVN(p.self.pe, 1) : "—"}</b> (${_esc(p.position && p.position.pe || "—")}) ·
      ROE <b>${p.self.roe != null ? fmtVN(p.self.roe, 1) + "%" : "—"}</b> (${_esc(p.position && p.position.roe || "—")}).</div>`;
  }
  const body = rows.map(r => `<tr>
    <td><a href="/co-phieu/${r.symbol}" style="color:var(--primary);font-weight:600">${r.symbol}</a></td>
    <td title="${_esc(r.name)}">${_esc((r.name || "").slice(0, 30))}</td>
    <td class="num">${r.health != null ? fmtVN(r.health, 0) : "—"}</td>
    <td class="num">${r.z_score != null ? fmtVN(r.z_score, 2) : "—"}</td>
    <td>${_esc(r.z_zone || "—")}</td>
    <td class="num">${r.f_score != null ? r.f_score + "/" + r.f_max : "—"}</td>
    <td class="num">${r.roe != null ? fmtVN(r.roe, 1) : "—"}</td></tr>`).join("");
  $("#peers-body").innerHTML = benchLine + `<div class="table-wrap"><table>
    <thead><tr><th>Mã</th><th>Công ty</th><th class="num">SK</th><th class="num">Z''</th><th>Vùng</th><th class="num">F</th><th class="num">ROE%</th></tr></thead>
    <tbody>${body || `<tr><td colspan="7" style="color:var(--muted)">Chưa có peer được chấm điểm.</td></tr>`}</tbody></table></div>
    <div style="margin-top:6px">${sourceTag("companies + health_scores.json + peers.py")}</div>`;
}

/* ---------- TAB LỊCH SỬ GIÁ ---------- */
let _priceDrawn = false;
function renderPriceTab() {
  if (_priceDrawn || !STOCK) return;
  _priceDrawn = true;
  const s = _series();
  if (!s.length) { $("#price-candle").innerHTML = `<div class="chart-empty">Mã chưa có dữ liệu giá (P6).</div>`; return; }
  // không có OHLC → dùng area thay nến
  M.lwcArea("#price-candle", s.map(p => ({ time: p[0], value: p[1] })), { source: STOCK.price.source, ts: STOCK.price.as_of, height: 320 });
  const recent = s.slice(-40).reverse();
  $("#price-table").innerHTML = `<div class="table-wrap"><table><thead><tr><th>Ngày</th><th class="num">Giá đóng cửa</th></tr></thead>
    <tbody>${recent.map(p => `<tr><td>${_esc(p[0])}</td><td class="num">${fmtVN(p[1], 2)}</td></tr>`).join("")}</tbody></table></div>`;
}

initTabs();
guardSection("#stock-subhead", renderStock);
