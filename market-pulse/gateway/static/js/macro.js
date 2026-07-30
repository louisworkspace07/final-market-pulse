/* Trang Vĩ mô — dự báo GDP / CPI */

/* PILLAR-M: đèn chế độ tiền tệ — 3 chỉ báo ±1, ngưỡng công khai, KHÔNG khuyến nghị */
async function renderRegime() {
  const r = await fetch("/api/macro/regime");
  const d = await r.json();
  const el = document.getElementById("regime-body");
  if (!d.available) {
    el.innerHTML = emptyState(d.reason || "Chưa có dữ liệu regime.", "🚦");
    return;
  }
  const color = d.state === "NỚI LỎNG" ? "var(--up)" :
                d.state === "THẮT CHẶT" ? "var(--down)" : "var(--ref)";
  const voteTxt = (v) => v === 1 ? '<span class="is-up">nới ↑</span>'
    : v === -1 ? '<span class="is-down">thắt ↓</span>'
    : v === 0 ? '<span class="is-ref">trung tính</span>' : "—";
  const rows = d.components.map(c => `<tr>
      <td>${_esc(c.label)}</td>
      <td class="num">${c.value != null ? fmtVN(c.value, 2) + (c.unit || "") : "—"}</td>
      <td style="font-size:12px;color:var(--muted)">${_esc(c.threshold)}</td>
      <td>${voteTxt(c.vote)}</td>
      <td style="font-size:12px;color:var(--muted)">${_esc(c.source || "")}</td>
    </tr>`).join("");
  el.innerHTML = `
    <div class="card">
      <div style="display:flex;gap:18px;align-items:center;flex-wrap:wrap;margin-bottom:12px">
        <span class="regime-badge" style="color:${color};font-size:16px">
          <span style="width:10px;height:10px;border-radius:50%;background:${color};display:inline-block"></span>
          ${_esc(d.state)}</span>
        <span style="font-size:13px;color:var(--muted)">
          Điểm tổng: <b>${d.score >= 0 ? "+" : ""}${d.score}</b> / ±3 ·
          Độ tin cậy dữ liệu: <b>${d.confidence_pct}%</b></span>
        <a href="/methodology.html#regime" style="font-size:12px;color:var(--accent)">Ngưỡng &amp; phương pháp →</a>
      </div>
      <div id="regime-onebar"></div>
      <div class="table-wrap" data-advanced><table>
        <thead><tr><th>Chỉ báo</th><th class="num">Giá trị</th><th>Ngưỡng</th><th>Phiếu</th><th>Nguồn</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <div class="disclaimer" style="margin-top:10px">${_esc(d.disclaimer)}</div>
      <div style="margin-top:8px">${sourceTag("macro_plus.json (SBV/GSO seed + VCB live + World Bank)", d.updated_at)}</div>
    </div>`;
  // §12: kim vị trí trên thang Thắt (trái) ↔ Nới (phải); score −3..+3.
  const rob = document.getElementById("regime-onebar");
  if (rob && window.MPChart) {
    const val = Math.max(0, Math.min(100, (d.score + 3) / 6 * 100));
    const chips = (d.components || []).slice(0, 3).map(c => ({
      t: c.label, kind: c.vote === 1 ? "ok" : c.vote === -1 ? "bad" : "neu" }));
    MPChart.mpBar(rob, { value: val, labelLeft: "Thắt chặt", labelRight: "Nới lỏng",
      verdict: `Môi trường tiền tệ: ${d.state}`, reasons: chips });
  }
}

async function renderMacro() {
  const d = await getData("macro_forecast");
  const gdp = d.gdp_growth, cpi = d.cpi;
  const gdpYears = Object.keys(gdp.history).slice(-15);
  const cpiYears = Object.keys(cpi.history).slice(-15);

  const gdpLast = Object.values(gdp.history).at(-1);
  const gdpMean = gdp.forecast.mean[0], cpiMean = cpi.forecast.mean[0];
  // "KTC 80%" là thuật ngữ chết với người thường → đổi cách nói.
  const band80 = (lo, hi) => `8/10 năm rơi trong ${fmtVN(lo, 1)}–${fmtVN(hi, 1)}%`;

  // P6: GDP dự báo là con số anh hùng của trang Vĩ mô.
  $("#macro-kpis").innerHTML =
    kpi(`GDP ${gdp.forecast.years[0]} (dự báo)`, fmtVN(gdpMean, 2) + "%",
        band80(gdp.forecast.lower[0], gdp.forecast.upper[0]), "good hero") +
    kpi(`CPI ${cpi.forecast.years[0]} (dự báo)`, fmtVN(cpiMean, 2) + "%",
        band80(cpi.forecast.lower[0], cpi.forecast.upper[0]), "blue") +
    kpi("GDP năm gần nhất", fmtVN(gdpLast, 2) + "%",
        `Năm ${gdpYears.at(-1)} · World Bank`, "good") +
    kpi("CPI năm gần nhất", fmtVN(Object.values(cpi.history).at(-1), 2) + "%",
        `Năm ${cpiYears.at(-1)} · World Bank`, "blue");

  // P4: "nghĩa là gì với thị trường" — so với trung bình 10 năm, thuần dữ kiện.
  const gdpAvg10 = gdpYears.slice(-10).reduce((s, y) => s + gdp.history[y], 0) / Math.min(10, gdpYears.length);
  const hotter = gdpMean > gdpAvg10;
  $("#macro-interp").innerHTML =
    `GDP dự báo <b>${fmtVN(gdpMean, 2)}%</b> ${hotter ? "cao hơn" : "thấp hơn"} trung bình 10 năm ` +
    `(<b>${fmtVN(gdpAvg10, 1)}%</b>); lạm phát CPI <b>${fmtVN(cpiMean, 2)}%</b> ` +
    `${cpiMean < 4 ? "trong ngưỡng mục tiêu <4% của Chính phủ" : "vượt ngưỡng mục tiêu 4%"}. ` +
    `Đây là bối cảnh vĩ mô — thông tin tham khảo, không phải khuyến nghị đầu tư.`;

  // Source tag: World Bank + thời điểm cập nhật
  const macroSrc = document.getElementById("macro-source");
  if (macroSrc) macroSrc.innerHTML = sourceTag("World Bank API (41 năm dữ liệu)", d.updated_at);

  forecastChart("#gdpChart", gdpYears, gdpYears.map(y => gdp.history[y]), gdp.forecast, "%/năm");
  forecastChart("#cpiChart", cpiYears, cpiYears.map(y => cpi.history[y]), cpi.forecast, "%/năm");

  const bt = gdp.backtest;
  $("#macro-backtest").innerHTML =
    `<b>Backtest minh bạch (walk-forward 5 năm cuối):</b> MAE mô hình GDP = <b>${fmtVN(bt.mae_model, 2)} điểm %</b> ` +
    `(naive = ${fmtVN(bt.mae_naive, 2)}). Giai đoạn ${bt.years[0]}–${bt.years.at(-1)} chứa cú sốc COVID-19 nên sai số ` +
    `còn cao — hệ thống hiển thị cả khoảng tin cậy thay vì chỉ 1 con số điểm. ` +
    `Cập nhật: ${d.updated_at}.`;
}

/* ══════════════════════════════════════════════════════════════════════════
   Chỉ số vĩ mô MỞ RỘNG (macro_plus.json) — hàng KPI mới, mỗi cái sourceTag.
   ══════════════════════════════════════════════════════════════════════════ */
async function renderMacroPlus() {
  let d;
  try { d = await getData("macro_plus"); } catch (_) { return; }
  if (!d || !d.indicators) return;
  const ind = d.indicators, cards = [];

  const fx = d.fx || {};
  if (fx.available)
    cards.push(kpi("Tỷ giá USD/VND (VCB)", fmtVN(fx.usd_sell, 0),
      `mua ${fmtVN(fx.usd_buy, 0)} · ${String(fx.as_of || "").slice(0, 10)}`, "blue"));

  const gold = d.gold || {};
  if (gold.available)
    cards.push(kpi("Vàng SJC", fmtVN(gold.sell, 0), `${gold.unit} · ${gold.source}`, "good"));

  const push = (key, label, cls) => {
    const v = ind[key];
    if (v && v.available)
      cards.push(kpi(label, fmtVN(v.latest, 2) + (v.unit === "%" ? "%" : ""),
        `${v.as_of} · ${v.source}`, cls));
  };
  push("export_growth", "Tăng trưởng XK", "good");
  push("fdi_net", "FDI / GDP", "blue");
  push("unemployment", "Thất nghiệp", "blue");

  const box = $("#macroplus-kpis");
  if (box) box.innerHTML = cards.join("") ||
    `<div class="disclaimer">Chưa có dữ liệu vĩ mô mở rộng — chạy pipeline để tạo macro_plus.json.</div>`;
  const src = $("#macroplus-source");
  if (src) {
    const na = Object.entries(ind).filter(([, v]) => !v.available).map(([, v]) => v.label);
    src.innerHTML = sourceTag("macro_plus (World Bank + VCB + probe)", d.updated_at) +
      (na.length ? ` <span class="src">· chưa có: ${na.join(", ")}</span>` : "");
  }
}

/* ══════════════════════════════════════════════════════════════════════════
   AI "Nhận định bối cảnh vĩ mô" — render dần 2 phần, evidence chips [M..].
   ══════════════════════════════════════════════════════════════════════════ */
let _macroNewsMap = {};

function _mChips(ids) {
  return (ids || []).map(raw => {
    const s = String(raw).replace(/[\[\]]/g, "").trim();
    const id = s.split(":")[0].trim();
    const n = _macroNewsMap[id];
    if (/^M\d+$/.test(id) && n) {
      const tip = `(${fmtDateVN(n.public_date, false)}) ${n.source || ""}: ${n.title || ""}`;
      const inner = n.link
        ? `<a href="${n.link}" target="_blank" rel="noopener">${id}</a>` : id;
      return `<span class="evidence-chip" title="${(tip).replace(/"/g, "&quot;")}">${inner}</span>`;
    }
    if (/^M\d+$/.test(id))
      return `<span class="evidence-chip missing" title="⚠ nguồn không tồn tại">${id} ⚠</span>`;
    // không phải id → mô tả dữ kiện AI nêu
    return `<span class="evidence-chip" style="opacity:.75">${s.length > 60 ? s.slice(0, 60) + "…" : s}</span>`;
  }).join(" ");
}

function _bucTranhBody(bt) {
  if (!bt) return "";
  const pts = (arr, cls) => (arr || []).map(p =>
    `<li><b class="${cls}">${p.y || ""}</b>${p.so_lieu ? ` — ${p.so_lieu}` : ""}
      <div style="margin-top:3px">${_mChips(p.bang_chung)}</div></li>`).join("");
  return `<p>${bt.buc_tranh_chung || ""}</p>
    <div class="grid-2" style="margin-top:12px">
      <div><h4 style="color:var(--accent2)">Điểm sáng</h4><ul>${pts(bt.diem_sang, "good-txt")}</ul></div>
      <div><h4 style="color:var(--warn)">Điểm tối</h4><ul>${pts(bt.diem_toi, "warn-txt")}</ul></div>
    </div>
    ${bt.do_tuoi_du_lieu ? `<p class="src" style="margin-top:10px">🕒 ${bt.do_tuoi_du_lieu}</p>` : ""}`;
}

function _kenhBody(k) {
  if (!k) return "";
  const kenh = (k.kenh_truyen_dan || []).map(x =>
    `<li><b>${x.kenh || ""}</b>: ${x.co_che || ""}
      ${x.trang_thai_hien_tai ? `<div class="src" style="margin-top:3px">Hiện tại: ${x.trang_thai_hien_tai}</div>` : ""}</li>`).join("");
  const risks = (k.rui_ro_vi_mo || []).map(r => `<li>${r}</li>`).join("");
  const watch = (k.theo_doi || []).map(t => `<li>${t}</li>`).join("");
  return `<h4>Kênh truyền dẫn tới TTCK</h4><ul>${kenh}</ul>
    ${risks ? `<h4 style="color:var(--warn)">Rủi ro vĩ mô</h4><ul>${risks}</ul>` : ""}
    ${watch ? `<h4>Chỉ báo theo dõi</h4><ul>${watch}</ul>` : ""}
    ${k.disclaimer ? `<p class="disclaimer" style="margin-top:8px">${k.disclaimer}</p>` : ""}`;
}

function _macroCard(title, status, bodyHtml) {
  if (status === "error")
    return `<div class="card part-error"><h3>${title}</h3><p class="warn-banner">Phần này lỗi.</p></div>`;
  if (status === "running")
    return `<div class="card part-pending"><h3>${title} <span class="spinner"></span></h3>
      ${skel("text", { rows: 3 })}</div>`;
  if (status !== "done") return "";
  return `<div class="card"><h3>${title}</h3>${bodyHtml}</div>`;
}

function renderMacroAI(d) {
  const body = $("#macroai-body");
  if (!body) return;
  if (!d || d.available === false) {
    body.innerHTML = `<div class="disclaimer">Chưa chạy nhận định lần nào — bấm "🤖 Chạy nhận định" để AI tổng hợp bối cảnh vĩ mô từ dữ liệu mới nhất.</div>`;
    return;
  }
  _macroNewsMap = d.news_meta || {};
  body.innerHTML =
    _macroCard("Bức tranh vĩ mô", "done", _bucTranhBody(d.buc_tranh)) +
    _macroCard("Kênh truyền dẫn tới TTCK", "done", _kenhBody(d.kenh_truyen_dan));
  const meta = $("#macroai-meta");
  if (meta) meta.innerHTML = `Tạo lúc ${d.generated_at || "?"} · kênh ${d.transport || "?"}`;
}

async function loadMacroAICache() {
  try { renderMacroAI(await getData("macro_ai")); }
  catch (_) { renderMacroAI(null); }
}

async function runMacroAI() {
  const btn = $("#macroai-run"), body = $("#macroai-body"), meta = $("#macroai-meta");
  btn.disabled = true; btn.textContent = "⏳ Đang phân tích…";
  try { await fetch("/api/macro/analyze", { method: "POST" }); }
  catch (_) { btn.disabled = false; btn.textContent = "🤖 Chạy nhận định"; return; }
  body.innerHTML = _macroCard("Bức tranh vĩ mô", "running", "") +
    _macroCard("Kênh truyền dẫn tới TTCK", "running", "");
  const poll = setInterval(async () => {
    let st;
    try { st = await (await fetch("/api/macro/analyze/status")).json(); }
    catch (_) { return; }
    if (meta && st.steps) meta.textContent = st.steps.map(s => `${s.name}:${s.status}`).join(" · ");
    if (st.status === "done") {
      clearInterval(poll);
      btn.disabled = false; btn.textContent = "🔄 Chạy lại";
      loadMacroAICache();
    } else if (st.status === "error") {
      clearInterval(poll);
      btn.disabled = false; btn.textContent = "🤖 Chạy lại";
      body.innerHTML = `<div class="card part-error"><h3>Lỗi</h3><p class="warn-banner">${st.error || "Không rõ lỗi"}</p></div>`;
    }
  }, 3000);
}

guardSection("#macro-kpis", renderMacro);
guardSection("#regime-body", renderRegime);
guardSection("#macroplus-kpis", renderMacroPlus);
guardSection("#macroai-body", loadMacroAICache);
// script nạp cuối <body> nên phần tử đã tồn tại — gắn trực tiếp.
{
  const _btn = document.getElementById("macroai-run");
  if (_btn) _btn.addEventListener("click", runMacroAI);
}
