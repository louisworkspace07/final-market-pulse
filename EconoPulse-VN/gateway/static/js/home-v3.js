/* ==========================================================================
   home-v3.js — các section MỚI của trang chủ v3 (Simplize-style, §5.1)
   Nạp SAU overview.js. Chỉ dùng hook riêng (hero-*, top-*, foreign-*), KHÔNG
   đụng vào hook của overview.js (#pulse-body, #heatmap, #radar-body, …).
   Nguyên tắc pháp lý: chỉ MÔ TẢ dữ kiện định lượng — KHÔNG phải khuyến nghị đầu tư.
   ========================================================================== */
(function () {
  "use strict";
  const M = window.MPChart;

  /* CSS riêng của WS-6 (f0-market.css) — nạp bằng JS vì template không thuộc
     quyền sửa của workstream này. Idempotent: nhiều trang gọi cũng chỉ 1 <link>. */
  (function ensureF0MarketCss() {
    const href = "/static/css/f0-market.css";
    if (document.querySelector(`link[href="${href}"]`)) return;
    const l = document.createElement("link");
    l.rel = "stylesheet"; l.href = href;
    document.head.appendChild(l);
  })();

  /* Ảnh 8: bảng tên ngành đã chuyển lên common.js (secVI dùng chung mọi trang,
     ưu tiên field sector_vi do API trả). Bản cục bộ ở đây đã gỡ để tránh 2 nguồn. */

  /* ---- %phiên 1 row bảng giá (matchChange/ref) ---- */
  function rowPct(r) {
    const ref = Number(r.ref);
    if (!isFinite(ref) || ref === 0) return null;
    const chg = (r.matchChange != null && isFinite(Number(r.matchChange)))
      ? Number(r.matchChange) : (Number(r.matchPrice) - ref);
    return chg / ref * 100;
  }
  const validRows = (b) => (b?.rows || []).filter(r =>
    r && r.symbol && Number(r.matchPrice) > 0 && Number(r.ref) > 0);

  /* fetch bảng giá 1 lần cho các section trang chủ (tách khỏi cache overview.js) */
  let _bp = null;
  function board() {
    if (!_bp) _bp = fetch("/api/market/board").then(r => {
      if (!r.ok) throw new Error("bảng giá chưa sẵn sàng (" + r.status + ")");
      return r.json();
    });
    return _bp;
  }
  function boardFoot(b) {
    return `<div class="home-foot">${b?.live ? '<span class="dot-live"></span> bảng giá LIVE' : '<span class="dot-cache"></span> phiên gần nhất (cache)'}`
      + ` · ${_formatTs(b?.as_of) || "—"}</div>`;
  }

  /* ══════════════════════════════════════════════════════════════════════
     §1.3 · TUỔI DỮ LIỆU TÍNH THEO PHIÊN GIAO DỊCH
     Đếm ngày lịch thì cuối tuần luôn bị báo "cũ 2-3 ngày" dù dữ liệu vẫn là
     phiên gần nhất. Ở đây chỉ đếm thứ 2–thứ 6 SAU mốc as_of (chưa trừ nghỉ lễ —
     nghỉ lễ sẽ làm số phiên đếm ra HƠI cao, ghi rõ để không hiểu sai).
     ══════════════════════════════════════════════════════════════════════ */
  function parseDay(v) {
    if (!v) return null;
    const d = new Date(String(v).slice(0, 10) + "T00:00:00");
    return isNaN(d.getTime()) ? null : d;
  }

  function sessionsSince(asOf, now) {
    const a = parseDay(asOf);
    if (!a) return null;
    const b = parseDay((now || new Date()).toISOString());
    if (!b || b <= a) return 0;
    let n = 0;
    const cur = new Date(a.getTime());
    while (cur < b) {
      cur.setDate(cur.getDate() + 1);
      const wd = cur.getDay();          // 0=CN, 6=T7
      if (wd !== 0 && wd !== 6) n++;
    }
    return n;
  }

  /* Badge 3 màu đặt CẠNH con số. Màu KHÔNG bao giờ là tín hiệu duy nhất:
     luôn có chữ trong badge + aria-label đầy đủ cho trình đọc màn hình. */
  function ageBadge(asOf, label) {
    const s = sessionsSince(asOf);
    const day = parseDay(asOf);
    const dmy = day ? fmtDateVN(day, false) : "—";
    if (s == null) {
      return `<span class="fm-age fm-age-stale" role="status"
        aria-label="Không rõ thời điểm dữ liệu ${_esc(label || "")}">✕ chưa rõ thời điểm</span>`;
    }
    let cls = "fm-age-fresh", txt = "mới nhất", icon = "●";
    if (s > 3) { cls = "fm-age-stale"; txt = `cũ ${s} phiên`; icon = "▲"; }
    else if (s >= 2) { cls = "fm-age-warn"; txt = `cũ ${s} phiên`; icon = "◆"; }
    else if (s === 1) { txt = "phiên trước"; }
    return `<span class="fm-age ${cls}" role="status"
      aria-label="Dữ liệu ${_esc(label || "")} tính đến ${dmy}, ${txt} so với hôm nay">`
      + `<span class="fm-age-icon" aria-hidden="true">${icon}</span>${txt}`
      + `<span class="fm-age-date">· ${dmy}</span></span>`;
  }

  /* Nút cập nhật: chỉ gọi ĐÚNG endpoint có thật (/api/market/refresh_prices →
     scripts/p6_market_prices.py). Nó làm mới BẢNG GIÁ/price, KHÔNG làm mới chuỗi
     chỉ số market_index (việc của P7 + run_pipeline.py) — nên nhãn nút nói đúng
     phạm vi, và dòng chú thích chỉ rõ phải chạy gì nếu chỉ số vẫn cũ. */
  function refreshBtnHTML(id) {
    return `<button type="button" class="fm-refresh" id="${id}"
      aria-label="Cập nhật dữ liệu giá từ nguồn">⟳ Cập nhật giá</button>`;
  }

  function bindRefreshBtn(id, after) {
    const btn = document.getElementById(id);
    if (!btn || btn.dataset.bound) return;
    btn.dataset.bound = "1";
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      const old = btn.textContent;
      btn.textContent = "⏳ đang cập nhật…";
      try { await fetch("/api/market/refresh_prices", { method: "POST" }); }
      catch (_) { btn.textContent = "⚠ không gọi được — thử lại"; btn.disabled = false; return; }
      const poll = setInterval(async () => {
        let st;
        try { st = await (await fetch("/api/market/refresh_prices/status")).json(); }
        catch (_) { return; }
        if (st.done || !st.running) {
          clearInterval(poll);
          btn.textContent = st.error ? "⚠ lỗi — thử lại" : old;
          btn.disabled = false;
          if (!st.error) { _bp = null; if (after) after(); }
        }
      }, 5000);
    });
  }

  /* ══════════════════════════════════════════════════════════════════════
     §2.1 · DÒNG KẾT LUẬN THỊ TRƯỜNG — chữ lớn nhất đầu trang
     Thuần số học từ bảng giá phiên gần nhất: tỷ lệ độ rộng + so thanh khoản với
     bình quân 20 phiên. MÔ TẢ trạng thái ĐÃ diễn ra (quá khứ/hiện tại), tuyệt
     đối không rating / giá mục tiêu / khuyến nghị.
     ══════════════════════════════════════════════════════════════════════ */
  const LEAN = [
    { max: 0.30, txt: "nghiêng hẳn về giảm", cls: "fm-lean-down2" },
    { max: 0.45, txt: "nghiêng về giảm", cls: "fm-lean-down" },
    { max: 0.55, txt: "giằng co", cls: "fm-lean-flat" },
    { max: 0.70, txt: "nghiêng về tăng", cls: "fm-lean-up" },
    { max: Infinity, txt: "nghiêng hẳn về tăng", cls: "fm-lean-up2" },
  ];

  function breadthOf(rows) {
    let up = 0, down = 0, flat = 0;
    for (const { pct } of rows) {
      if (pct > 0) up++; else if (pct < 0) down++; else flat++;
    }
    return { up, down, flat, n: rows.length };
  }

  /* GTGD phiên = Σ giá khớp × KL khớp toàn phiên (đồng). Bình quân 20 phiên lấy
     `gtgd20` do server tính sẵn từ market.db — cùng một nguồn với cổng thanh khoản,
     nên 2 con số so được với nhau. */
  function turnoverOf(rows) {
    let today = 0, avg20 = 0, nAvg = 0;
    for (const { r } of rows) {
      const px = Number(r.matchPrice), vol = Number(r.totalVol);
      if (isFinite(px) && isFinite(vol)) today += px * vol;
      const g = Number(r.gtgd20);
      if (isFinite(g)) { avg20 += g; nAvg++; }
    }
    return { today, avg20, nAvg };
  }

  function verdictHost() {
    let host = document.getElementById("fm-verdict");
    if (host) return host;
    const hero = document.getElementById("home-hero");
    if (!hero || !hero.parentNode) return null;
    host = document.createElement("section");
    host.id = "fm-verdict";
    host.className = "fm-verdict";
    hero.parentNode.insertBefore(host, hero);
    return host;
  }

  async function renderVerdict() {
    const host = verdictHost();
    if (!host) return;
    const b = await board();
    const rows = validRows(b).map(r => ({ r, pct: rowPct(r) }))
      .filter(x => x.pct != null && isFinite(x.pct));
    if (!rows.length) { host.innerHTML = emptyState("Chưa có dữ liệu bảng giá."); return; }

    const br = breadthOf(rows);
    const denom = br.up + br.down;
    const ratio = denom > 0 ? br.up / denom : 0.5;
    const lean = LEAN.find(l => ratio < l.max) || LEAN[LEAN.length - 1];
    // "cứ 10 mã thì N mã giảm, M mã tăng" — chỉ tính trên số mã CÓ biến động,
    // mã đứng giá kể riêng để tổng không bị hiểu sai.
    const per10Down = denom > 0 ? Math.round(br.down / denom * 10) : 0;
    const per10Up = denom > 0 ? 10 - per10Down : 0;

    const to = turnoverOf(rows);
    let liqTxt = "chưa đủ dữ liệu để so", liqCls = "fm-liq-na", liqDetail = "";
    if (to.avg20 > 0 && to.today > 0) {
      const k = to.today / to.avg20;
      liqTxt = k < 0.7 ? "THẤP hơn bình quân 20 phiên"
        : k > 1.3 ? "CAO hơn bình quân 20 phiên" : "quanh mức bình quân 20 phiên";
      liqCls = k < 0.7 ? "fm-liq-low" : k > 1.3 ? "fm-liq-high" : "fm-liq-mid";
      liqDetail = `${fmtVN(to.today / 1e9, 0)} tỷ đồng so với bình quân `
        + `${fmtVN(to.avg20 / 1e9, 0)} tỷ (tỷ lệ ${fmtVN(k, 2)})`;
    }

    const win = (b.liquidity && b.liquidity.window) || null;
    host.innerHTML = `
      <p class="fm-headline ${lean.cls}">
        Phiên gần nhất, thị trường <b>${lean.txt}</b>: cứ 10 mã thì
        <b>${per10Down} mã giảm</b>, <b>${per10Up} mã tăng</b>.
      </p>
      <p class="fm-subline">
        Giá trị giao dịch <b class="${liqCls}">${liqTxt}</b>${liqDetail ? " — " + liqDetail : ""}.
      </p>
      <p class="fm-verdict-basis">
        Đếm trên <b>${fmtVN(br.n, 0)}</b> mã có khớp lệnh:
        ${fmtVN(br.up, 0)} tăng · ${fmtVN(br.flat, 0)} đứng giá · ${fmtVN(br.down, 0)} giảm.
        ${win ? `Bình quân giá trị giao dịch lấy theo ${win} phiên gần nhất.` : ""}
      </p>
      <div class="fm-chips" id="fm-regime-chip">${regimeChipHTML()}</div>
      <p class="fm-verdict-legal">Đây là MÔ TẢ số liệu phiên đã diễn ra, không phải
        dự báo hay khuyến nghị mua/bán.</p>
      ${boardFoot(b)}`;

    loadRegimeChip();
  }

  /* Nhãn chế độ thị trường mất ~16 giây (đo trên máy thật) → nạp RIÊNG, sau khi
     dòng kết luận đã hiện. Không await trong renderVerdict để không chặn.
     Kết quả được NHỚ (_regimeData) vì mỗi nhịp LivePoll vẽ lại innerHTML của dòng
     kết luận: không nhớ thì chip vừa hiện đã bị xoá và không bao giờ quay lại. */
  let _regimeState = "idle";   // idle | loading | done | error
  let _regimeData = null;

  function regimeChipHTML() {
    if (_regimeState === "loading")
      return `<span class="fm-chip fm-chip-loading">Đang tính nhãn chế độ thị trường…</span>`;
    if (_regimeState === "error")
      return `<span class="fm-chip-note">Chưa lấy được nhãn chế độ thị trường.</span>`;
    const d = _regimeData;
    if (_regimeState !== "done" || !d || d.label == null) return "";
    const score = (d.score != null && d.max_score != null)
      ? ` <span class="fm-chip-score">${d.score}/${d.max_score}</span>` : "";
    return `<span class="fm-chip" aria-label="Nhãn chế độ thị trường: ${_esc(String(d.label))}">`
      + `Chế độ thị trường: <b>${_esc(String(d.label))}</b>${score}</span>`
      + (d.note ? `<span class="fm-chip-note">${_esc(String(d.note))}</span>` : "");
  }

  function paintRegimeChip() {
    const s = document.getElementById("fm-regime-chip");
    if (s) s.innerHTML = regimeChipHTML();
  }

  function loadRegimeChip() {
    if (_regimeState !== "idle") { paintRegimeChip(); return; }
    _regimeState = "loading";
    paintRegimeChip();
    fetch("/api/market/regime").then(r => r.json()).then(d => {
      _regimeData = d;
      _regimeState = (d && d.label != null) ? "done" : "error";
      paintRegimeChip();
    }).catch(() => { _regimeState = "error"; paintRegimeChip(); });
  }

  /* ══════════════════════════════════════════════════════════════════════
     HERO 1 · VNINDEX area chart (LWC) + timeframe pills (market_range.history)
     ══════════════════════════════════════════════════════════════════════ */
  const TF = [
    { k: "1M", days: 22 }, { k: "3M", days: 66 }, { k: "6M", days: 132 },
    { k: "1Y", days: 264 }, { k: "Tất cả", days: Infinity },
  ];
  let _tf = "Tất cả", _rangeData = null, _candles = null, _candleLoad = null;

  /* Ảnh 1 · Nạp OHLC chỉ số 1 lần (P9 → /api/index_history). Không có thì trả
     mảng rỗng để rơi về area từ market_range — KHÔNG dựng nến giả từ close. */
  function loadCandles() {
    if (_candleLoad) return _candleLoad;
    _candleLoad = fetch("/api/index_history?code=VNINDEX")
      .then(r => r.json())
      .then(d => { _candles = (d.candles || []).filter(c => isFinite(c.close)); return _candles; })
      .catch(() => { _candles = []; return _candles; });
    return _candleLoad;
  }

  function drawHeroChart() {
    const box = $("#hero-vnindex");
    if (!box) return;
    const tf = TF.find(t => t.k === _tf) || TF[TF.length - 1];

    // ---- ưu tiên NẾN khi có O/H/L thật và khung đủ ngắn để đọc được ----
    const hasOHLC = _candles && _candles.length > 2
      && _candles.every(c => isFinite(c.open) && isFinite(c.high) && isFinite(c.low));
    if (hasOHLC) {
      let cs = _candles;
      if (isFinite(tf.days) && cs.length > tf.days) cs = cs.slice(cs.length - tf.days);
      const first = cs[0].close, last = cs[cs.length - 1].close;
      // Nến chỉ đọc được khi thưa; khung dài (1Y/Tất cả) vẫn dùng area cho gọn mắt.
      if (cs.length <= 140) {
        M.lwcCandle(box, {
          ohlc: cs.map(c => ({ time: c.time, open: c.open, high: c.high, low: c.low, close: c.close })),
          vol: cs.map(c => ({ time: c.time, value: c.volume || 0,
                              color: (c.close >= c.open ? "rgba(37,183,112,.45)" : "rgba(225,64,64,.45)") })),
        }, { height: 240 });
      } else {
        M.lwcArea(box, cs.map(c => ({ time: c.time, value: c.close })), { height: 240 });
      }
      heroNotes(cs.map(c => c.close), cs.length, hasOHLC);
      return;
    }

    // ---- fallback: chuỗi close từ market_range (như cũ) ----
    if (!_rangeData) return;
    const hist = _rangeData.history || {};
    let series = Object.keys(hist).sort().map(d => ({ time: d, value: Number(hist[d]) }))
      .filter(p => isFinite(p.value));
    if (series.length < 2) { box.innerHTML = emptyState("Chưa có chuỗi VNINDEX."); return; }
    if (isFinite(tf.days) && series.length > tf.days) series = series.slice(series.length - tf.days);
    M.lwcArea(box, series, { height: 240 });
    heroNotes(series.map(p => p.value), series.length, false);
  }

  /* Nhận xét tự động (S2) — thuần dữ kiện của quãng đang xem. */
  function heroNotes(closes, n, fromCandles) {
    const notes = $("#hero-vnindex-notes");
    if (!notes || !closes.length) return;
    const first = closes[0], last = closes[closes.length - 1];
    const chg = first ? (last - first) / first * 100 : 0;
    const hi = Math.max(...closes), lo = Math.min(...closes);
    notes.innerHTML =
      `<li class="${chg >= 0 ? "ok" : "bad"}">Quãng ${_esc(_tf)}: chỉ số ${chg >= 0 ? "tăng" : "giảm"} `
      + `<b>${fmtPctSigned(chg, 2)}</b> (${fmtIndex(first)} → ${fmtIndex(last)} điểm)</li>`
      + `<li class="neu">Cao nhất ${fmtIndex(hi)} · thấp nhất ${fmtIndex(lo)} · ${n} phiên`
      + `<span class="src src-tech"> · ${fromCandles ? "index_ohlc (P9)" : "market_range"}</span></li>`;
  }

  function drawTfPills() {
    const el = $("#hero-vnindex-tf");
    if (!el) return;
    el.innerHTML = TF.map(t =>
      `<span class="tfpill ${t.k === _tf ? "active" : ""}" data-tf="${t.k}">${t.k}</span>`).join("");
    el.querySelectorAll(".tfpill").forEach(p =>
      p.addEventListener("click", () => { _tf = p.dataset.tf; drawTfPills(); drawHeroChart(); }));
  }

  /* ══════════════════════════════════════════════════════════════════════
     HERO 2 · Bảng "Chỉ số & nhóm ngành" (VNINDEX headline + top ngành theo cap)
     ══════════════════════════════════════════════════════════════════════ */
  async function renderIndexTable() {
    const box = $("#hero-index-table");
    if (!box) return;
    let range = _rangeData, heat = null;
    try {
      [range, heat] = await Promise.all([
        range ? Promise.resolve(range) : getData("market_range"),
        fetch("/api/market/heatmap").then(r => r.json()),
      ]);
      _rangeData = range;
    } catch (e) { box.innerHTML = emptyState("Chưa tải được dữ liệu chỉ số/ngành."); return; }

    // headline VNINDEX: base + % thay đổi phiên gần nhất (2 điểm cuối history)
    let headline = "";
    if (range?.available && range.base != null) {
      const hist = range.history || {};
      const ks = Object.keys(hist).sort();
      let dayChg = null;
      if (ks.length >= 2) {
        const prev = Number(hist[ks[ks.length - 2]]), last = Number(hist[ks[ks.length - 1]]);
        if (isFinite(prev) && prev !== 0 && isFinite(last)) dayChg = (last - prev) / prev * 100;
      }
      const chgHtml = dayChg == null ? ""
        : `<span class="idx-chg ${dayChg >= 0 ? "chg-up" : "chg-down"}">`
          + `${dayChg >= 0 ? "▲" : "▼"} ${fmtPctSigned(dayChg, 2)}</span>`;
      // §1.3 · badge tuổi dữ liệu đứng NGAY CẠNH con số, không phải chữ xám
      // dưới chân. Đo 27/07/2026: market_range.as_of = 2026-07-07 → cũ 14 phiên
      // mà giao diện cũ chỉ ghi "tính đến …" nên gần như không ai nhận ra.
      headline = `<div class="idx-headline">
          <span class="idx-name">VN-INDEX</span>
          <span class="idx-val">${fmtVN(range.base, 2)}</span>${chgHtml}
          ${ageBadge(range.as_of, "chỉ số VN-Index")}
        </div>
        <div class="fm-age-row">
          <span class="idx-sub">điểm · tính đến ${_formatTs(range.as_of) || "—"}</span>
          ${refreshBtnHTML("fm-refresh-idx")}
        </div>
        <div class="fm-age-note">Tuổi tính theo phiên (bỏ thứ 7 &amp; chủ nhật; chưa trừ
          ngày nghỉ lễ). Nút trên cập nhật dữ liệu giá; chuỗi điểm chỉ số cần chạy
          thêm P7 + run_pipeline.py.</div>`;
    } else {
      headline = `<div class="idx-headline"><span class="idx-name">VN-INDEX</span>
        <span class="idx-val">—</span>
        <span class="fm-age fm-age-stale" role="status" aria-label="Chưa có dữ liệu chỉ số">✕ chưa có dữ liệu</span>
        </div><div class="idx-sub">chưa có market_range</div>`;
    }

    // nhóm ngành: gom heatmap theo sector, %phiên bình quân tính theo quy mô công ty, top 8 theo cap
    const items = (heat?.items || []).filter(it =>
      it && it.sector && isFinite(Number(it.cap)) && isFinite(Number(it.chg_pct)));
    let groupsHtml = "";
    if (items.length) {
      const by = {};
      for (const it of items) {
        const s = by[it.sector] || (by[it.sector] = { sector: it.sector, sector_vi: it.sector_vi, cap: 0, w: 0, n: 0 });
        const cap = Number(it.cap) || 0;
        s.cap += cap; s.w += cap * Number(it.chg_pct); s.n++;
      }
      const secs = Object.values(by)
        .map(s => ({ sector: s.sector, sector_vi: s.sector_vi, n: s.n, cap: s.cap, avg: s.cap > 0 ? s.w / s.cap : 0 }))
        .sort((a, b) => b.cap - a.cap).slice(0, 8);
      groupsHtml = `<div class="idx-divider"></div>
        <div class="idx-groups-h">Nhóm ngành lớn nhất (%phiên bình quân tính theo quy mô công ty)</div>`
        + secs.map(s => {
          const up = s.avg >= 0;
          return `<div class="grp-row">
            <span class="grp-name">${secVI(s)}<span class="grp-n">${s.n} mã</span></span>
            <span class="grp-val ${up ? "chg-up" : "chg-down"}">${up ? "▲" : "▼"} ${fmtPctSigned(s.avg, 2)}</span>
          </div>`;
        }).join("");
    } else {
      groupsHtml = `<div class="idx-divider"></div>
        <div class="home-foot">Chưa có dữ liệu ngành — chạy P6 bên Crawl Data.</div>`;
    }

    const foot = `<div class="home-foot">${heat?.board_live ? '<span class="dot-live"></span> %phiên LIVE' : '<span class="dot-cache"></span> %phiên phiên gần nhất'}`
      + ` · ${_formatTs(heat?.as_of) || "—"}</div>`;
    box.innerHTML = headline + groupsHtml + foot;
    // Nút cập nhật chỉ tồn tại sau khi innerHTML chạy → bind ở đây.
    bindRefreshBtn("fm-refresh-idx", () => {
      _rangeData = null;
      guardSection("#hero-index-table", renderIndexTable);
      guardSection("#top-gainers", renderMovers);
      guardSection("#fm-verdict", renderVerdict);
    });
  }

  /* ══════════════════════════════════════════════════════════════════════
     3 · Top tăng / giảm giá (bảng C2: logo tròn + % + KLGD)
     ══════════════════════════════════════════════════════════════════════ */
  /* Ảnh 2 · đệm cho đủ n hàng để 2 bảng cạnh nhau không lệch đáy card. */
  function padRows(html, count, want, cols) {
    let out = html;
    for (let i = count; i < want; i++)
      out += `<tr class="row-pad"><td colspan="${cols}">—</td></tr>`;
    return out;
  }

  function moverTable(rows, want = 10) {
    const body = rows.map(({ r, pct }) => {
      const up = pct >= 0;
      return `<tr>
        <td><a class="mv-sym" href="/co-phieu/${encodeURIComponent(r.symbol)}">
          ${M.symLogoHTML(r.symbol)}${_esc(r.symbol)}</a>${thinBadge(r)}</td>
        <td class="mv-num">${fmtPrice(r.matchPrice)}</td>
        <td class="mv-num ${up ? "chg-up" : "chg-down"}">${up ? "▲" : "▼"} ${fmtPctSigned(pct, 2)}</td>
        <td class="mv-num col-klgd">${fmtVN(r.totalVol, 0)}</td>
      </tr>`;
    }).join("");
    return `<table class="mv-table">
      <thead><tr><th>Mã</th><th>Giá</th><th>%phiên</th><th class="col-klgd">KLGD</th></tr></thead>
      <tbody>${padRows(body, rows.length, want, 4)}</tbody></table>`;
  }

  /* ---- Lọc "cổ phiếu chết" — MẶC ĐỊNH BẬT ----
     Sắp thuần theo %phiên thì bảng Top luôn bị mã gần như không giao dịch chiếm
     chỗ: đo 26/07/2026 có 8/10 mã top tăng từ 16/20 phiên không có lệnh nào
     (KHD: 20/20 phiên KL=0) mà vẫn hiện "+14,74%" — người mới tưởng là cơ hội,
     mua vào thì kẹt hàng. Cờ `tradable` do SERVER gắn (modules/market_overview/
     liquidity.py) nên trang chủ và trang Tổng quan dùng chung một tiêu chí.
     `tradable === null` = mã chưa đủ lịch sử giá → GIỮ LẠI, không coi là mã chết. */
  let showThin = false;

  /* §2.3 · Cảnh báo thanh khoản HIỆN THÀNH CHỮ, không phải tooltip.
     Bản cũ chỉ có icon ⚠ + title: trên điện thoại KHÔNG có hover nên cảnh báo
     biến mất đúng lúc cần nhất, và "màu/icon không chữ" thì trình đọc màn hình
     cũng không đọc ra vấn đề gì. Nay in thẳng lý do bằng chữ dưới tên mã.
     `window` lấy từ payload (b.liquidity.window) chứ không hardcode 20, vì
     board KHÔNG trả `sessions` theo từng dòng. */
  let _liqWindow = null;   // set trong renderMovers() từ b.liquidity.window

  function thinWhy(r) {
    if (r.tradable !== false) return null;
    const win = _liqWindow;
    if (r.zero_days >= 3)
      return `thanh khoản rất thấp — ${r.zero_days}${win ? "/" + win : ""} phiên không ai giao dịch`;
    const vol = Number(r.totalVol);
    const volTxt = isFinite(vol) && vol > 0 ? `${fmtVN(vol, 0)} cp/phiên hôm nay · ` : "";
    return `thanh khoản rất thấp — ${volTxt}khớp bình quân ~${fmtVN((r.gtgd20 || 0) / 1e6, 0)} triệu đồng/phiên`;
  }

  function thinBadge(r) {
    const why = thinWhy(r);
    if (!why) return "";
    // role=note + chữ đầy đủ: đọc được bằng mắt, bằng screen-reader, trên mobile.
    return `<div class="fm-thin-warn" role="note">
      <span class="fm-thin-icon" aria-hidden="true">▲</span>${_esc(why)}</div>`;
  }

  /* Dòng minh bạch: đang ẩn bao nhiêu mã, vì sao, và nút xem hết. */
  function thinFoot(hidden, b) {
    const liq = (b && b.liquidity) || {};
    const min = fmtVN((liq.min_gtgd || 5e8) / 1e6, 0);
    const maxZ = liq.max_zero_days != null ? liq.max_zero_days : 2;
    const win = liq.window || null;
    if (showThin) {
      return `<div class="thin-note">Đang hiện <b>tất cả</b> mã, gồm cả mã thanh khoản
        rất thấp (có ghi chú cảnh báo ngay dưới mã).
        <button type="button" class="thin-toggle" data-thin="off">Ẩn mã thanh khoản thấp</button></div>`;
    }
    if (!hidden) return "";
    return `<div class="thin-note">Đã ẩn <b>${fmtVN(hidden, 0)}</b> mã giao dịch quá thưa
      (khớp dưới ${min} triệu đồng/phiên${win ? " bình quân " + win + " phiên" : ""},
      hoặc quá ${maxZ} phiên không ai giao dịch) — dễ mua vào rồi kẹt hàng.
      <button type="button" class="thin-toggle" data-thin="on">Hiện tất cả</button></div>`;
  }

  function bindThinToggle() {
    document.querySelectorAll(".thin-toggle").forEach(btn => {
      btn.onclick = () => { showThin = btn.dataset.thin === "on"; renderMovers(); };
    });
  }

  async function renderMovers() {
    const b = await board();
    _liqWindow = (b && b.liquidity && b.liquidity.window) || null;
    const all = validRows(b).map(r => ({ r, pct: rowPct(r) }))
      .filter(x => x.pct != null && isFinite(x.pct));
    const gBox = $("#top-gainers"), lBox = $("#top-losers");
    if (!all.length) {
      const e = emptyState("Chưa có dữ liệu bảng giá.");
      if (gBox) gBox.innerHTML = e; if (lBox) lBox.innerHTML = e; return;
    }
    const rows = showThin ? all : all.filter(x => x.r.tradable !== false);
    const foot = thinFoot(all.length - rows.length, b) + boardFoot(b);
    const gainers = [...rows].sort((a, b) => b.pct - a.pct).slice(0, 10);
    const losers = [...rows].sort((a, b) => a.pct - b.pct).slice(0, 10);
    if (gBox) gBox.innerHTML = moverTable(gainers) + foot;
    if (lBox) lBox.innerHTML = moverTable(losers) + foot;
    bindThinToggle();
  }

  /* ══════════════════════════════════════════════════════════════════════
     4 · Top khối ngoại mua/bán ròng (foreignBuy − foreignSell, đơn vị cổ phiếu)
     ══════════════════════════════════════════════════════════════════════ */
  function foreignTable(rows, want = 10) {
    const body = rows.map(({ r, net }) => {
      const buy = net >= 0;
      return `<tr>
        <td><a class="mv-sym" href="/co-phieu/${encodeURIComponent(r.symbol)}">
          ${M.symLogoHTML(r.symbol)}${_esc(r.symbol)}</a></td>
        <td class="mv-num">${fmtPrice(r.matchPrice)}</td>
        <td class="mv-num ${buy ? "chg-up" : "chg-down"}">${buy ? "+" : ""}${fmtVN(net, 0)}</td>
      </tr>`;
    }).join("");
    return `<table class="mv-table">
      <thead><tr><th>Mã</th><th>Giá</th><th>NN ròng (CP)</th></tr></thead>
      <tbody>${padRows(body, rows.length, want, 3)}</tbody></table>`;
  }

  async function renderForeign() {
    const b = await board();
    const rows = validRows(b).map(r => {
      const fb = Number(r.foreignBuy), fs = Number(r.foreignSell);
      const net = (isFinite(fb) ? fb : 0) - (isFinite(fs) ? fs : 0);
      return { r, net, has: isFinite(fb) || isFinite(fs) };
    }).filter(x => x.has && x.net !== 0);
    const buyBox = $("#foreign-buy"), sellBox = $("#foreign-sell");
    if (!rows.length) {
      const e = emptyState("Chưa có dữ liệu khối ngoại trên bảng giá.");
      if (buyBox) buyBox.innerHTML = e; if (sellBox) sellBox.innerHTML = e; return;
    }
    const buy = [...rows].filter(x => x.net > 0).sort((a, b) => b.net - a.net).slice(0, 10);
    const sell = [...rows].filter(x => x.net < 0).sort((a, b) => a.net - b.net).slice(0, 10);
    if (buyBox) buyBox.innerHTML = (buy.length ? foreignTable(buy) : emptyState("Không có mã mua ròng.")) + boardFoot(b);
    if (sellBox) sellBox.innerHTML = (sell.length ? foreignTable(sell) : emptyState("Không có mã bán ròng.")) + boardFoot(b);
  }

  /* ---- khởi động: mỗi section độc lập qua guardSection ---- */
  function boot() {
    drawTfPills();
    // §2.1 · dòng kết luận đứng TRƯỚC hero và chỉ cần /api/market/board → hiện
    // gần như tức thì; nhãn chế độ (16s) tự nối vào sau dưới dạng chip.
    // Tạo host TRƯỚC khi gọi guardSection: guardSection giải anchor ngay lúc gọi,
    // nếu #fm-verdict chưa tồn tại thì lỗi sẽ không có chỗ để hiện.
    verdictHost();
    guardSection("#fm-verdict", renderVerdict);
    guardSection("#hero-vnindex", async () => {
      // ảnh 1: nạp nến song song với bảng chỉ số rồi mới vẽ
      await Promise.all([renderIndexTable(), loadCandles()]);
      drawHeroChart();
    });
    guardSection("#top-gainers", renderMovers);
    guardSection("#foreign-buy", renderForeign);
  }
  boot();

  /* R1 · làm mới theo nhịp CHUNG của LivePoll (15s trong phiên, 120s ngoài giờ,
     dừng khi tab ẩn) thay cho setInterval 60s riêng của trang này. Mỗi nhịp chỉ
     xoá cache board rồi vẽ lại — không tự gọi thêm request nào. */
  LivePoll.on(() => {
    _bp = null;
    guardSection("#fm-verdict", renderVerdict);
    guardSection("#top-gainers", renderMovers);
    guardSection("#foreign-buy", renderForeign);
    guardSection("#hero-index-table", renderIndexTable);
  });
})();
