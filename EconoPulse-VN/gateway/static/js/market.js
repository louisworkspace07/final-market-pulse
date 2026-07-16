/* Trang Thị trường — dải thống kê 30 phiên (KHÔNG phải dự báo) + sức khỏe DN */

/* CSS riêng WS-6 (f0-market.css) — nạp bằng JS vì template không thuộc phạm vi
   sửa của workstream này. Idempotent. */
(function ensureF0MarketCss() {
  const href = "/static/css/f0-market.css";
  if (document.querySelector(`link[href="${href}"]`)) return;
  const l = document.createElement("link");
  l.rel = "stylesheet"; l.href = href;
  document.head.appendChild(l);
})();

/* §1.3 · tuổi dữ liệu tính theo PHIÊN GIAO DỊCH (bỏ T7/CN), không phải ngày lịch:
   đếm ngày lịch thì mở trang vào cuối tuần luôn bị báo "cũ 2–3 ngày" dù dữ liệu
   vẫn đúng là phiên gần nhất. Chưa trừ nghỉ lễ → số phiên có thể HƠI cao. */
function mktSessionsSince(asOf, now) {
  if (!asOf) return null;
  const a = new Date(String(asOf).slice(0, 10) + "T00:00:00");
  if (isNaN(a.getTime())) return null;
  const b = new Date((now || new Date()).toISOString().slice(0, 10) + "T00:00:00");
  if (b <= a) return 0;
  let n = 0;
  const cur = new Date(a.getTime());
  while (cur < b) {
    cur.setDate(cur.getDate() + 1);
    const wd = cur.getDay();
    if (wd !== 0 && wd !== 6) n++;
  }
  return n;
}

/* Badge 3 màu ĐẶT CẠNH con số. Màu không bao giờ là tín hiệu duy nhất: luôn kèm
   chữ trong badge + aria-label đầy đủ cho trình đọc màn hình. */
/* `withDate=false` → badge chỉ nói "cũ N phiên", không kèm ngày. Dùng khi ngày
   đã được ghi ngay cạnh, để một tấm thẻ không hiện cùng một ngày hai lần bằng
   hai định dạng khác nhau (trước đây: badge "07/07/2026" + dòng dưới
   "Tính đến 2026-07-07"). */
function mktAgeBadge(asOf, label, withDate = true) {
  const s = mktSessionsSince(asOf);
  if (s == null) {
    return `<span class="fm-age fm-age-stale" role="status"
      aria-label="Không rõ thời điểm dữ liệu ${_esc(label || "")}">✕ chưa rõ thời điểm</span>`;
  }
  const dmy = fmtDateVN(new Date(String(asOf).slice(0, 10) + "T00:00:00"), false);
  let cls = "fm-age-fresh", txt = "mới nhất", icon = "●";
  if (s > 3) { cls = "fm-age-stale"; txt = `cũ ${s} phiên`; icon = "▲"; }
  else if (s >= 2) { cls = "fm-age-warn"; txt = `cũ ${s} phiên`; icon = "◆"; }
  else if (s === 1) { txt = "phiên trước"; }
  return `<span class="fm-age ${cls}" role="status"
    aria-label="Dữ liệu ${_esc(label || "")} tính đến ${dmy}, ${txt} so với hôm nay">`
    + `<span class="fm-age-icon" aria-hidden="true">${icon}</span>${txt}`
    + (withDate ? `<span class="fm-age-date">· ${dmy}</span>` : "") + `</span>`;
}

/* Ngày hiển thị kiểu Việt Nam từ chuỗi ISO; chuỗi hỏng thì trả nguyên bản. */
function mktDateVN(iso) {
  const d = new Date(String(iso).slice(0, 10) + "T00:00:00");
  return isNaN(d) ? String(iso) : fmtDateVN(d, false);
}

/* Nút cập nhật giá — gọi ĐÚNG endpoint có thật (/api/market/refresh_prices →
   scripts/p6_market_prices.py). Nó làm mới bảng `price`, KHÔNG làm mới chuỗi
   điểm chỉ số `market_index` (việc của P7 + run_pipeline.py) nên nhãn nói đúng
   phạm vi và chú thích chỉ rõ phải chạy gì nếu chỉ số vẫn cũ. */
function mktRefreshBtn(id) {
  return `<button type="button" class="fm-refresh" id="${id}"
    aria-label="Cập nhật dữ liệu giá từ nguồn">⟳ Cập nhật giá</button>`;
}

function mktBindRefresh(id, after) {
  const btn = document.getElementById(id);
  if (!btn || btn.dataset.bound) return;
  btn.dataset.bound = "1";
  btn.addEventListener("click", async () => {
    const old = btn.textContent;
    btn.disabled = true;
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
        if (!st.error && after) after();
      }
    }, 5000);
  });
}

async function renderMarket() {
  const d = await getData("market_range");
  if (!d.available) {
    $("#market-kpis").innerHTML = `<div class="warn-banner">Chưa đủ dữ liệu VNINDEX: ${d.reason || "?"}</div>`;
    return;
  }
  const histDates = Object.keys(d.history);
  const histVals = Object.values(d.history);
  const base = d.base;
  const rp = d.return_pct, band = d.band;

  // P6 hierarchy: VNINDEX là "con số anh hùng" của trang.
  // §1.3 · badge tuổi dữ liệu đứng NGAY CẠNH con số thay vì chỉ dòng chữ xám
  // "Tính đến …": đo 27/07/2026 market_range.as_of = 2026-07-07, tức đã cũ
  // 14 phiên mà giao diện cũ không hề nhấn mạnh.
  $("#market-kpis").innerHTML =
    // Badge PHẢI nằm ngoài `.value`: `.kpi.hero .value` là 40px — badge lọt vào
    // trong đó sẽ thừa hưởng cỡ chữ đó nếu f0-market.css chưa nạp (cache cũ,
    // mất mạng), biến "cũ 14 phiên · 07/07/2026" thành chữ khổng lồ đè cả con số.
    // Đặt ở `.sub` thì hỏng CSS cũng chỉ là chữ nhỏ xám.
    kpi("VN-Index hiện tại", fmtVN(base, 2),
        `<span class="fm-age-row">${mktAgeBadge(d.as_of, "chỉ số VN-Index", false)}`
        + `<span>Tính đến ${mktDateVN(d.as_of)}</span></span>`, "blue hero") +
    kpi("Trung vị 30 phiên (lịch sử)", fmtVN(band.p50, 0),
        `${fmtPctSigned(rp.p50)} — mức giữa phân phối`, rp.p50 >= 0 ? "good" : "warn") +
    kpi("Dải giữa (P25–P75)", `${fmtVN(band.p25, 0)}–${fmtVN(band.p75, 0)}`,
        `${fmtPctSigned(rp.p25)} … ${fmtPctSigned(rp.p75)} trong 50% số lần`, "blue") +
    kpi("Số mẫu lịch sử", fmtVN(d.n_samples, 0), "Đoạn 30 phiên (rolling)", "blue");

  // P4: dòng "nghĩa là gì" — diễn giải dải bằng ngôn ngữ đời thường, thuần dữ kiện.
  const width = band.p75 - band.p25, widthPct = (width / base * 100);
  const spread = widthPct > 8 ? "RỘNG (biến động lịch sử lớn)" : widthPct > 4 ? "vừa phải" : "HẸP (thị trường ít biến động)";
  $("#market-interp").innerHTML =
    `Trong lịch sử, sau 30 phiên VN-Index thường dao động quanh <b>${fmtVN(band.p25,0)}–${fmtVN(band.p75,0)} điểm</b> ` +
    `(50% số lần), biên độ ${spread}. Đây là <b>phân phối thống kê của quá khứ</b>, không phải dự đoán tương lai — ` +
    `dùng để hình dung mức biến động BÌNH THƯỜNG, không phải mục tiêu giá.`;

  const mktSrc = document.getElementById("market-source");
  if (mktSrc) mktSrc.innerHTML = sourceTag(d.source || "VNINDEX (VNDirect)", d.updated_at);

  // §12: thanh vị trí VNINDEX trong dải giá 30 phiên lịch sử (mô tả, KHÔNG dự báo).
  const mBar = $("#market-onebar");
  if (mBar && window.MPChart) {
    const win = histVals.slice(-30);
    if (win.length >= 10) {
      const lo = Math.min(...win), hi = Math.max(...win);
      const posPct = hi > lo ? (base - lo) / (hi - lo) * 100 : 50;
      const pctile = win.filter(v => v <= base).length / win.length * 100;
      MPChart.mpBar(mBar, {
        value: Math.max(0, Math.min(100, posPct)),
        labelLeft: `đáy 30 phiên (${fmtVN(lo, 0)})`, labelRight: `đỉnh 30 phiên (${fmtVN(hi, 0)})`,
        verdict: `VN-Index đang ở ~P${fmtVN(pctile, 0)} vùng giá 30 phiên gần nhất`,
        reasons: [{ t: "mô tả vị trí lịch sử, không phải dự báo", kind: "neu" }],
      });
    }
  }

  distributionChart("#marketChart", histDates, histVals, d);
}

/* Fan chart phân phối: lịch sử VNINDEX + dải percentile 30 phiên tới (thống kê
   mô tả — KHÔNG phải dự báo). Các dải chiếu ngang từ phiên cuối tới +30 phiên. */
function distributionChart(canvasId, histDates, histVals, d) {
  const H = 30;
  const future = Array.from({ length: H }, (_, i) => `+${i + 1}`);
  const labels = [...histDates.slice(-120), ...future];
  const hv = histVals.slice(-120);
  const n = hv.length;
  const pad = (arr) => [...Array(n - 1).fill(null), hv[n - 1], ...arr];
  // mỗi percentile: đường thẳng từ base tới band.pXX
  const ramp = (target) => Array.from({ length: H }, (_, i) => hv[n - 1] + (target - hv[n - 1]) * (i + 1) / H);
  const b = d.band;
  // Palette phẳng v3 — đọc từ CSS token, không dùng rainbow.
  const cc = chartColors();
  const primary = cc.accent || "#006CEC", up = cc.up || "#25B770", down = cc.down || "#E14040";
  new Chart($(canvasId), {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "VNINDEX (lịch sử)", data: [...hv, ...Array(H).fill(null)],
          borderColor: primary, backgroundColor: primary, pointRadius: 0, borderWidth: 2, tension: .2 },
        { label: "P50 (trung vị lịch sử)", data: pad(ramp(b.p50)),
          borderColor: up, borderDash: [6, 4], pointRadius: 0, borderWidth: 2 },
        { label: "P95", data: pad(ramp(b.p95)), borderColor: "transparent",
          backgroundColor: "rgba(37,183,112,.08)", fill: "+1", pointRadius: 0 },
        { label: "P75", data: pad(ramp(b.p75)), borderColor: "transparent",
          backgroundColor: "rgba(37,183,112,.14)", fill: "+1", pointRadius: 0 },
        { label: "P25", data: pad(ramp(b.p25)), borderColor: "transparent",
          backgroundColor: "rgba(37,183,112,.14)", fill: "+1", pointRadius: 0 },
        { label: "P5", data: pad(ramp(b.p5)), borderColor: "transparent",
          backgroundColor: "rgba(225,64,64,.06)", fill: "+1", pointRadius: 0 },
      ],
    },
    options: {
      plugins: {
        legend: { labels: { filter: (i) => !["P95", "P75", "P25", "P5"].includes(i.text) } },
        title: { display: true, text: "Dải thống kê 30 phiên (phân phối lịch sử — KHÔNG phải dự báo)" },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmtVN(c.parsed.y, 1)}` } },
      },
      scales: {
        // Trục ngày dày đặc chồng chữ → chỉ hiện tối đa ~9 mốc, không nghiêng.
        x: { ticks: { autoSkip: true, maxTicksLimit: 9, maxRotation: 0, minRotation: 0 } },
        y: { title: { display: true, text: "điểm VN-Index" },
             ticks: { callback: (v) => fmtVN(v, 0) } },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

/* ---------------- sức khỏe doanh nghiệp ---------------- */
let healthRows = [];
let scoreRange = null;   // B5: [lo,hi] khi click bin histogram, null = tất cả

function drawHealthTable() {
  const q = $("#health-search").value.toLowerCase();
  const g = $("#health-filter").value;
  const zone = ($("#health-zone") || {}).value || "";
  const flagOnly = ($("#health-flag-only") || {}).checked || false;
  const rows = healthRows.filter(r =>
    (!g || r.group === g) &&
    (!zone || r.z_zone === zone) &&
    (!flagOnly || (r.watch_flags || []).includes("weak_combo")) &&
    (!scoreRange || (r.health_score != null && r.health_score >= scoreRange[0] && r.health_score <= scoreRange[1])) &&
    (!q || r.symbol.toLowerCase().includes(q) || (r.name || "").toLowerCase().includes(q)));

  // B6: chip trạng thái lọc + đếm kết quả + nút xóa lọc
  const act = $("#health-active");
  if (act) {
    const chips = [];
    if (scoreRange) chips.push(`Điểm ${scoreRange[0]}–${scoreRange[1]}`);
    if (g) chips.push(g === "DN" ? "Doanh nghiệp phi tài chính" : "Ngân hàng / tài chính");
    if (zone) chips.push("Vùng " + zone);
    if (flagOnly) chips.push("Có cờ theo dõi");
    if (q) chips.push(`“${q}”`);
    if (chips.length) {
      act.style.display = "flex";
      act.innerHTML = `<span class="fa-label">Đang lọc:</span>` +
        chips.map(c => `<span class="fa-chip">${_esc(c)}</span>`).join("") +
        `<span class="fa-count">${fmtVN(rows.length, 0)} mã</span>` +
        `<button class="fa-clear" onclick="clearHealthFilter()">Xóa lọc ✕</button>`;
    } else {
      act.style.display = "none"; act.innerHTML = "";
    }
  }

  // Drill-down: click vào tên mã → hiện chi tiết chỉ số
  $("#health-table tbody").innerHTML = rows.slice(0, 200).map(r => {
    const zoneCls = r.z_zone === "An toàn" ? "zone-safe" : r.z_zone === "Xám" ? "zone-grey"
      : r.z_zone === "Nguy hiểm" ? "zone-danger" : "";
    const hs = r.health_score;
    const drillId = `health-drill-${r.symbol}`;
    const drillContent = `
      <table><tr><th>Chỉ tiêu</th><th>Giá trị</th><th>Ý nghĩa</th></tr>
        <tr><td>Altman Z''</td><td>${fmtVN(r.z_score, 2)}</td><td class="${zoneCls}">${r.z_zone}</td></tr>
        <tr><td>Piotroski F</td><td>${r.f_score}/${r.f_max}</td><td>Sức khỏe tài chính (tối đa 9)</td></tr>
        <tr><td>ROA</td><td>${r.roa != null ? fmtVN(r.roa, 2) + "%" : "—"}</td><td>Tỷ suất sinh lời tổng tài sản</td></tr>
        <tr><td>ROE</td><td>${r.roe != null ? fmtVN(r.roe, 2) + "%" : "—"}</td><td>Tỷ suất sinh lời vốn chủ</td></tr>
        <tr><td>Tỷ lệ nợ</td><td>${fmtVN(r.debt_ratio, 2)}</td><td>Tỷ lệ nợ / Tổng tài sản</td></tr>
        <tr><td>Cường độ GD</td><td>${fmtVN(r.flow_score, 0)}</td><td>Volume 5/20 phiên + biến động (0–100, mô tả)</td></tr>
        <tr><td>Cờ theo dõi</td><td colspan="2">${(r.watch_flags || []).length
          ? r.watch_flags.map(f => ({z_danger:"Z'' vùng nguy hiểm", f_low:"F-score ≤ 3",
              f_drop:"F-score giảm ≥2 so kỳ trước", weak_combo:"Z'' nguy hiểm + F thấp"}[f] || f)).join(" · ")
          : "không có"}</td></tr>
      </table>
      <div style="margin-top:8px">${sourceTag("BCTC market.db", r.data_as_of)}</div>`;
    const isWeak = (r.watch_flags || []).includes("weak_combo");
    return `<tr>
      <td><a href="/co-phieu/${r.symbol}" style="display:inline-flex;align-items:center;gap:7px;color:var(--accent);font-weight:700;text-decoration:none">${window.MPChart ? MPChart.symLogoHTML(r.symbol) : ""}${r.symbol}</a>
        ${isWeak ? `<span class="mini-tag danger" title="Z-score vùng nguy hiểm + F-score thấp — trạng thái dữ liệu, không phải khuyến nghị">⚠ theo dõi</span>` : ""}
        <b class="drill-toggle" style="cursor:pointer;color:var(--muted)" onclick="toggleDrill('${drillId}')">▸</b></td>
      <td title="${r.name || ""}">${(r.name || "").slice(0, 38)}</td>
      <td>${r.exchange || ""}</td>
      <td><span class="badge">${r.group}</span></td>
      <td class="num">${hs != null ? `<span class="score-bar"><i style="width:${hs}%"></i></span>${fmtVN(hs, 0)}` : "—"}</td>
      <td class="num">${fmtVN(r.z_score, 2)}</td>
      <td class="${zoneCls}">${r.z_zone}</td>
      <td class="num">${r.f_score}/${r.f_max}</td>
      <td class="num">${fmtVN(r.roa, 2)}</td>
      <td class="num">${fmtVN(r.roe, 2)}</td>
      <td class="num">${fmtVN(r.debt_ratio, 2)}</td>
    </tr>
    <tr><td colspan="11" style="padding:0">
      <div class="drill-panel" id="${drillId}">${drillContent}</div>
    </td></tr>`;
  }).join("");
}

async function renderHealth() {
  const d = await getData("health_scores");
  healthRows = d.companies;
  const dn = healthRows.filter(r => r.group === "DN" && r.z_score != null);
  const safe = dn.filter(r => r.z_zone === "An toàn").length;
  const danger = dn.filter(r => r.z_zone === "Nguy hiểm").length;

  $("#health-kpis").innerHTML =
    kpi("Công ty được chấm", fmtVN(healthRows.length, 0), "Từ BCTC crawl thật (market.db)", "blue") +
    kpi("Vùng an toàn (Z'' > 2.6)", fmtVN(safe, 0), `trên ${fmtVN(dn.length,0)} DN phi tài chính`, "good") +
    kpi("Vùng nguy hiểm (Z'' < 1.1)", fmtVN(danger, 0), "Cảnh báo rủi ro phá sản", danger > 0 ? "warn" : "good") +
    kpi("Điểm SK trung bình", fmtVN(healthRows.reduce((s, r) => s + (r.health_score || 0), 0) / healthRows.length, 1),
        "Thang 0–100 (Z'' + F + ROA)", "blue");

  // Dòng diễn giải thuần dữ kiện (nếu bỏ trống, .interp-line:empty sẽ tự ẩn).
  const weakN = healthRows.filter(r => (r.watch_flags || []).includes("weak_combo")).length;
  const scoredN = healthRows.filter(r => r.health_score != null).length;
  $("#health-interp").innerHTML =
    `Đã chấm <b>${fmtVN(healthRows.length, 0)}</b> doanh nghiệp từ BCTC thật: ` +
    `<b>${fmtVN(safe, 0)}</b> mã vùng an toàn, <b>${fmtVN(danger, 0)}</b> mã vùng nguy hiểm. ` +
    (weakN ? `<b>${fmtVN(weakN, 0)}</b> mã có cờ "theo dõi" (Z-score nguy hiểm + F-score thấp). ` : "") +
    `Đây là mô tả trạng thái tài chính theo mô hình học thuật — không phải khuyến nghị.`;

  // P4: thay 4 con số tổng bằng PHÂN BỐ điểm (histogram) + bảng mã đáng ngại.
  drawHealthDist();

  // Source tag cho bảng sức khỏe
  const healthSrc = document.getElementById("health-source");
  if (healthSrc) healthSrc.innerHTML = sourceTag("BCTC market.db (Crawl Data)", d.generated_at);

  drawHealthTable();
  $("#health-search").addEventListener("input", drawHealthTable);
  $("#health-filter").addEventListener("change", drawHealthTable);
  const z = $("#health-zone"); if (z) z.addEventListener("change", drawHealthTable);
  const f = $("#health-flag-only"); if (f) f.addEventListener("change", drawHealthTable);
}

/* P4: histogram phân bố điểm sức khỏe 0–100 (10 bin) + danh sách mã đáng ngại.
   Người dùng cần THẤY bức tranh phân hóa, không phải 1 con số trung bình. */
function drawHealthDist() {
  const scored = healthRows.filter(r => r.health_score != null);
  const bins = Array(10).fill(0);
  scored.forEach(r => { bins[Math.min(9, Math.floor(r.health_score / 10))]++; });
  const mx = Math.max(...bins, 1);
  const barCol = i => i < 3 ? "var(--down,#E14040)" : i < 6 ? "var(--ref,#FFC701)" : "var(--up,#25B770)";
  // B5: mỗi bin bấm được → lọc bảng theo khoảng điểm; bin đang chọn viền sáng.
  const bars = bins.map((c, i) => {
    const lo = i * 10, hi = i * 10 + 9;
    const sel = scoreRange && scoreRange[0] === lo && scoreRange[1] === hi;
    return `<div class="bar${sel ? " sel" : ""}" role="button" tabindex="0"
        onclick="toggleScoreBin(${lo},${hi})" onkeydown="if(event.key==='Enter')toggleScoreBin(${lo},${hi})"
        style="height:${c / mx * 100}%;background:${barCol(i)}"
        title="${lo}–${hi} điểm: ${fmtVN(c, 0)} mã — bấm để lọc"><span>${c || ""}</span></div>`;
  }).join("");
  const xs = bins.map((_, i) => `<div>${i * 10}</div>`).join("");
  // B4: top mã yếu nhất → link NỘI BỘ /co-phieu (bỏ :5000/app cũ + _blank)
  const weak = [...scored].sort((a, b) => (a.health_score) - (b.health_score)).slice(0, 10);
  const weakRows = weak.map(r => `
    <a href="/co-phieu/${encodeURIComponent(r.symbol)}" class="weak-chip" title="${_esc(r.name || "")}">
      <b>${_esc(r.symbol)}</b> <span class="num-mono">${fmtVN(r.health_score, 0)}</span>
      ${r.z_zone === "Nguy hiểm" ? '<span class="mini-tag danger">Z nguy hiểm</span>' : ""}</a>`).join("");
  $("#health-dist").innerHTML = `
    <div style="display:grid;grid-template-columns:1.3fr 1fr;gap:20px;align-items:end">
      <div>
        <div style="font-size:12.5px;color:var(--muted);margin-bottom:22px">Phân bố điểm sức khỏe ${fmtVN(scored.length,0)} DN (0–100) — bấm cột để lọc bảng</div>
        <div class="hist">${bars}</div>
        <div class="hist-x">${xs}</div>
      </div>
      <div>
        <div style="font-size:12.5px;color:var(--muted);margin-bottom:8px">⚠️ 10 mã điểm thấp nhất — bấm xem chi tiết</div>
        <div class="weak-list">${weakRows}</div>
      </div>
    </div>`;
}

/* B5: bấm cột histogram → bật/tắt lọc theo khoảng điểm, đồng bộ bảng + chip. */
function toggleScoreBin(lo, hi) {
  if (scoreRange && scoreRange[0] === lo && scoreRange[1] === hi) scoreRange = null;
  else scoreRange = [lo, hi];
  drawHealthDist();
  drawHealthTable();
}

/* B6: xóa toàn bộ lọc (kể cả khoảng điểm từ histogram). */
function clearHealthFilter() {
  scoreRange = null;
  $("#health-search").value = "";
  $("#health-filter").value = "";
  const z = $("#health-zone"); if (z) z.value = "";
  const f = $("#health-flag-only"); if (f) f.checked = false;
  drawHealthDist();
  drawHealthTable();
}

guardSection("#market-kpis", renderMarket);
guardSection("#health-kpis", renderHealth);
