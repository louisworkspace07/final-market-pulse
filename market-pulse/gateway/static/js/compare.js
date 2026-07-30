/* Trang So sánh 2 cổ phiếu (A3) — /so-sanh
   Dữ liệu: /api/stock/<sym> (gọi song song 2 lần). Chỉ trình bày dữ kiện —
   KHÔNG xếp hạng "tốt hơn/nên chọn" (ràng buộc pháp lý). */

let cmpChart = null;

/* ---- đọc / ghi mã trên URL (?a=..&b=..) không reload trang ---- */
function _params() {
  return new URLSearchParams(location.search);
}
function _setUrl(a, b) {
  const p = _params();
  p.set("a", a);
  p.set("b", b);
  history.replaceState(null, "", `${location.pathname}?${p.toString()}`);
}

async function fetchSide(sym) {
  const r = await fetch(`/api/stock/${sym}`);
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `Không tìm thấy mã ${sym}`);
  return d;
}

/* ---- chuẩn hoá % hiệu suất giá từ phiên chung đầu tiên ----
   Cả 2 có giá: giao ngày chung, quy đổi mỗi đường về % so với giá đóng cửa
   tại ngày chung sớm nhất. Chỉ 1 mã có giá: vẽ riêng đường đó, chuẩn hoá từ
   phiên đầu của chính nó, kèm ghi chú mã còn lại thiếu dữ liệu. */
function buildNormalized(symA, symB, dA, dB) {
  const pxA = dA.price, pxB = dB.price;
  if (!pxA && !pxB) return { ok: false, note: "Cả 2 mã đều chưa có dữ liệu giá (chưa nằm trong nhóm crawl P6)." };

  if (pxA && pxB) {
    const mapA = new Map(pxA.series), mapB = new Map(pxB.series);
    const common = pxA.series.map(p => p[0]).filter(d => mapB.has(d));
    if (common.length) {
      const base = common[0];
      const baseA = mapA.get(base), baseB = mapB.get(base);
      return {
        ok: true, labels: common,
        seriesA: common.map(d => (mapA.get(d) / baseA - 1) * 100),
        seriesB: common.map(d => (mapB.get(d) / baseB - 1) * 100),
        note: `Chuẩn hoá % từ phiên chung đầu tiên: ${base}.`,
      };
    }
    // không có ngày trùng — hiếm (lệch hoàn toàn lịch giao dịch); chỉ vẽ đường A,
    // ghi chú để người dùng biết B bị bỏ qua khỏi biểu đồ (vẫn có trong bảng chỉ số)
    return {
      ok: true,
      only: "A",
      labels: pxA.series.map(p => p[0]),
      values: pxA.series.map(p => (p[1] / pxA.series[0][1] - 1) * 100),
      note: `Không có phiên giao dịch trùng ngày giữa ${symA} và ${symB} — chỉ hiển thị ${symA} trên biểu đồ.`,
    };
  }

  // chỉ 1 mã có giá
  const only = pxA ? "A" : "B", px = pxA || pxB, missingSym = pxA ? symB : symA;
  return {
    ok: true, only, labels: px.series.map(p => p[0]),
    values: px.series.map(p => (p[1] / px.series[0][1] - 1) * 100),
    note: `Mã ${missingSym} chưa có dữ liệu giá — chỉ hiển thị đường còn lại.`,
  };
}

function drawChart(canvas, symA, symB, norm) {
  if (cmpChart) { cmpChart.destroy(); cmpChart = null; }
  const c = chartColors();
  const datasets = [];

  // Palette phẳng v3: A = primary xanh, B = up xanh lá (2 màu token tương phản).
  if (norm.only === "A") {
    datasets.push({ label: `${symA} (%)`, data: norm.values, borderColor: c.accent,
      backgroundColor: c.accent + "22", fill: false, pointRadius: 0, borderWidth: 2, tension: .25 });
  } else if (norm.only === "B") {
    datasets.push({ label: `${symB} (%)`, data: norm.values, borderColor: c.up,
      backgroundColor: c.up + "22", fill: false, pointRadius: 0, borderWidth: 2, tension: .25 });
  } else {
    datasets.push({ label: `${symA} (%)`, data: norm.seriesA, borderColor: c.accent,
      backgroundColor: c.accent + "22", fill: false, pointRadius: 0, borderWidth: 2, tension: .25 });
    datasets.push({ label: `${symB} (%)`, data: norm.seriesB, borderColor: c.up,
      backgroundColor: c.up + "22", fill: false, pointRadius: 0, borderWidth: 2, tension: .25 });
  }

  cmpChart = new Chart(canvas, {
    type: "line",
    data: { labels: norm.labels, datasets },
    options: {
      plugins: { legend: { position: "top" },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${fmtPctSigned(ctx.parsed.y)}` } } },
      scales: {
        x: { ticks: { autoSkip: true, maxTicksLimit: 8, maxRotation: 0 } },
        y: { ticks: { callback: v => fmtPctSigned(v, 0) } },
      },
      interaction: { mode: "index", intersect: false },
    },
  });
}

function headBlock(sym, d) {
  const i = d.info;
  return `
    <div style="flex:1;min-width:200px">
      <div style="font-size:19px;font-weight:800;display:flex;align-items:center;gap:8px">
        ${window.MPChart ? MPChart.symLogoHTML(sym) : ""}
        <a href="/co-phieu/${sym}" style="color:var(--accent);text-decoration:none">${_esc(sym)}</a> ${wlStar(sym)}
      </div>
      <div style="color:var(--muted);font-size:12.5px">${_esc(i.name || "—")} ·
        ${_esc(i.exchange || "—")} · ${_esc(i.sector || "—")}</div>
    </div>`;
}

/* Ảnh 17 · "Thông tin cơ bản" 2 cột — trước đây trang So sánh nhảy thẳng vào
   chỉ số mà không cho biết 2 doanh nghiệp này LÀ AI. Toàn bộ lấy từ dữ liệu đã
   có (bảng companies + profile.json), không thêm request nặng. */
function _basicRows(symA, symB, dA, dB) {
  const g = (d, path, fb) => {
    const o = d.info || {};
    const ov = (d.profile && d.profile.overview) || {};
    for (const k of path) { if (o[k] != null && o[k] !== "") return o[k]; if (ov[k] != null && ov[k] !== "") return ov[k]; }
    return fb;
  };
  const pct = (v) => (v == null || !isFinite(Number(v))) ? "—" : fmtPctSigned(Number(v) * 100, 1).replace("+", "");
  const rows = [
    ["Ngành", d => secVI(g(d, ["sector"], "")) || "—"],
    ["Sàn niêm yết", d => _esc(g(d, ["exchange"], "—"))],
    ["Vốn hóa", d => fmtMoney(g(d, ["market_cap"], null))],
    ["Số CP lưu hành", d => fmtVN(g(d, ["issue_share"], null), 0)],
    ["Sở hữu nước ngoài", d => pct(g(d, ["foreigner_percentage"], null))],
    ["Room ngoại tối đa", d => pct(g(d, ["maximum_foreign_percentage"], null))],
    ["Sở hữu nhà nước", d => pct(g(d, ["state_percentage"], null))],
    ["GTGD bình quân 1 tháng", d => fmtMoney(g(d, ["average_match_value1_month"], null))],
  ];
  return rows.map(([label, fn]) =>
    `<tr><td>${label}</td><td class="num">${fn(dA)}</td><td class="num">${fn(dB)}</td></tr>`).join("");
}

function zRow(h) {
  if (!h) return "—";
  if (h.group === "TCTC") return "Tổ chức tài chính";
  if (h.z_score == null) return "—";
  return `${fmtVN(h.z_score, 2)}${h.z_zone ? " · " + _esc(h.z_zone) : ""}`;
}

function metricRows(dA, dB) {
  const fA = dA.fund || {}, fB = dB.fund || {};
  const hA = dA.health, hB = dB.health;
  const priceA = dA.price ? dA.price.last : dA.info.current_price;
  const priceB = dB.price ? dB.price.last : dB.info.current_price;

  const rows = [
    ["Giá hiện tại", priceA != null ? fmtVN(priceA, 2) : "—", priceB != null ? fmtVN(priceB, 2) : "—"],
    ["Vốn hoá", fmtMoney(dA.info.market_cap), fmtMoney(dB.info.market_cap)],
    ["P/E", fA.pe != null ? fmtVN(fA.pe, 1) : "—", fB.pe != null ? fmtVN(fB.pe, 1) : "—"],
    ["P/B", fA.pb != null ? fmtVN(fA.pb, 1) : "—", fB.pb != null ? fmtVN(fB.pb, 1) : "—"],
    ["ROE %", fA.roe_pct != null ? fmtVN(fA.roe_pct, 1) : "—", fB.roe_pct != null ? fmtVN(fB.roe_pct, 1) : "—"],
    ["ROA %", fA.roa_pct != null ? fmtVN(fA.roa_pct, 1) : "—", fB.roa_pct != null ? fmtVN(fB.roa_pct, 1) : "—"],
    ["Biên ròng %", fA.net_margin_pct != null ? fmtVN(fA.net_margin_pct, 1) : "—",
      fB.net_margin_pct != null ? fmtVN(fB.net_margin_pct, 1) : "—"],
    ["Nợ/VCSH", fA.debt_to_equity != null ? fmtVN(fA.debt_to_equity, 1) : "—",
      fB.debt_to_equity != null ? fmtVN(fB.debt_to_equity, 1) : "—"],
    ["Điểm SK /100", hA && hA.health_score != null ? fmtVN(hA.health_score, 0) + "/100" : "—",
      hB && hB.health_score != null ? fmtVN(hB.health_score, 0) + "/100" : "—"],
    ["Z''-score / vùng", zRow(hA), zRow(hB)],
    ["F-score", hA && hA.f_score != null ? `${hA.f_score}/${hA.f_max}` : "—",
      hB && hB.f_score != null ? `${hB.f_score}/${hB.f_max}` : "—"],
  ];

  return rows.map(([label, a, b]) =>
    `<tr><td>${_esc(label)}</td><td class="num">${a}</td><td class="num">${b}</td></tr>`).join("");
}

/* §12: đếm số tiêu chí mỗi mã "thuận lợi hơn" theo CHIỀU đã công bố (legal-safe:
   chỉ đếm dữ kiện, KHÔNG kết luận "nên chọn"). Trả {aWin,bWin,tie,total}. */
function _tugCount(dA, dB) {
  const fA = dA.fund || {}, fB = dB.fund || {}, hA = dA.health || {}, hB = dB.health || {};
  // [giá trị A, giá trị B, higherIsBetter]
  const crit = [
    [fA.pe, fB.pe, false], [fA.pb, fB.pb, false],
    [fA.roe_pct, fB.roe_pct, true], [fA.roa_pct, fB.roa_pct, true],
    [fA.net_margin_pct, fB.net_margin_pct, true],
    [fA.debt_to_equity, fB.debt_to_equity, false],
    [hA.health_score, hB.health_score, true],
    [hA.z_score, hB.z_score, true], [hA.f_score, hB.f_score, true],
  ];
  let aWin = 0, bWin = 0, tie = 0, total = 0;
  crit.forEach(([a, b, hib]) => {
    if (a == null || b == null || !isFinite(a) || !isFinite(b)) return;
    total++;
    if (a === b) { tie++; return; }
    const aBetter = hib ? a > b : a < b;
    if (aBetter) aWin++; else bWin++;
  });
  return { aWin, bWin, tie, total };
}

async function doCompare(symA, symB) {
  const node = $("#compare-result");
  const [dA, dB] = await Promise.all([fetchSide(symA), fetchSide(symB)]);

  node.innerHTML = `
    <div class="card">
      <div style="display:flex;gap:24px;flex-wrap:wrap;margin-bottom:12px">
        ${headBlock(symA, dA)}
        ${headBlock(symB, dB)}
      </div>
      <div id="cmp-tug"></div>
      <h3>Hiệu suất giá chuẩn hoá (%) <span class="src" id="cmp-chart-note"></span></h3>
      <div id="cmp-chart-wrap"><canvas id="cmpChart" height="100"></canvas></div>
    </div>

    <div class="card" style="margin-top:14px">
      <h3>Thông tin cơ bản</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Chỉ tiêu</th><th class="num">${_esc(symA)}</th><th class="num">${_esc(symB)}</th></tr></thead>
          <tbody>${_basicRows(symA, symB, dA, dB)}</tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:14px">
      <h3>Chỉ số song song</h3>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Chỉ tiêu</th><th class="num">${_esc(symA)}</th><th class="num">${_esc(symB)}</th></tr></thead>
          <tbody>${metricRows(dA, dB)}</tbody>
        </table>
      </div>
    </div>

    <div class="card" style="margin-top:14px" id="cmp-ai-card">
      <h3>AI so sánh
        <span class="src">AI đọc số liệu 2 mã và chỉ ra khác biệt theo từng mặt — chỉ dữ kiện, KHÔNG khuyến nghị chọn mã</span>
      </h3>
      <div class="ask-row">
        <button id="cmp-ai-btn">▶ Chạy AI so sánh ${_esc(symA)} · ${_esc(symB)}</button>
      </div>
      <div id="cmp-ai-body"></div>
    </div>`;

  // Ảnh 17: AI chạy KHI BẤM (tốn 1 lượt AI), có cache theo cặp mã trong 1 giờ.
  const aiBtn = $("#cmp-ai-btn");
  if (aiBtn) aiBtn.addEventListener("click", () => runCompareAI(symA, symB));
  const cached = _aiCacheGet(symA, symB);
  if (cached) renderCompareAI(cached, true);

  // §12: tug tổng "A nhỉnh X/N tiêu chí" (đếm dữ kiện — không kết luận nên chọn)
  const tug = _tugCount(dA, dB);
  const tugBox = $("#cmp-tug");
  if (tugBox && window.MPChart && tug.total > 0) {
    const verdict = tug.aWin === tug.bWin
      ? `${_esc(symA)} và ${_esc(symB)} ngang nhau (${tug.aWin}–${tug.bWin} trên ${tug.total} tiêu chí)`
      : `${_esc(tug.aWin > tug.bWin ? symA : symB)} nhỉnh hơn ở ${Math.max(tug.aWin, tug.bWin)}/${tug.total} tiêu chí định lượng`;
    MPChart.mpBar(tugBox, { variant: "tug", verdict,
      tug: { aLabel: symA, bLabel: symB, aValue: tug.aWin, bValue: tug.bWin } });
    tugBox.insertAdjacentHTML("beforeend",
      `<div class="disclaimer" style="font-size:11.5px">Chỉ đếm số tiêu chí thuận lợi theo mô hình — KHÔNG phải khuyến nghị chọn mã.</div>`);
  }

  const norm = buildNormalized(symA, symB, dA, dB);
  const noteEl = $("#cmp-chart-note");
  if (!norm.ok) {
    $("#cmp-chart-wrap").innerHTML = emptyState(norm.note, "📈");
  } else {
    if (noteEl) noteEl.textContent = norm.note || "";
    drawChart($("#cmpChart"), symA, symB, norm);
  }

  $("#compare-source").innerHTML = sourceTag("market.db + health_scores.json", dA.price?.as_of || dB.price?.as_of || null);
}

/* ---------------- Ảnh 17 · AI so sánh (cache 1h theo cặp mã) ---------------- */
const _AI_TTL_MS = 3600000;
function _aiKey(a, b) { return `mp_cmp_ai_${a}_${b}`; }
function _aiCacheGet(a, b) {
  try {
    const raw = localStorage.getItem(_aiKey(a, b));
    if (!raw) return null;
    const o = JSON.parse(raw);
    if (Date.now() - o.ts > _AI_TTL_MS) return null;
    return o.data;
  } catch (_) { return null; }
}
function _aiCacheSet(a, b, data) {
  try { localStorage.setItem(_aiKey(a, b), JSON.stringify({ ts: Date.now(), data })); } catch (_) {}
}

async function runCompareAI(a, b) {
  const btn = $("#cmp-ai-btn"), box = $("#cmp-ai-body");
  if (!box) return;
  if (btn) { btn.disabled = true; btn.textContent = "Đang phân tích…"; }
  box.innerHTML = skel("text", { rows: 4 });
  try {
    const r = await fetch("/api/compare_ai", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ a, b }),
    });
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    _aiCacheSet(a, b, d);
    renderCompareAI(d, false);
  } catch (e) {
    box.innerHTML = `<div class="warn-banner">Chưa chạy được AI so sánh: ${_esc(e.message)}</div>`;
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = `▶ Chạy lại AI so sánh`; }
  }
}

function renderCompareAI(d, fromCache) {
  const box = $("#cmp-ai-body");
  if (!box) return;
  const ans = d.answer || {};
  const li = (arr) => (arr || []).map(x => `<li class="neu">${_esc(x)}</li>`).join("") || "<li>—</li>";
  const diff = (ans.diff || []).map(x => `
    <tr><td>${_esc(x.aspect || "")}</td>
        <td>${_esc(x.a || "—")}</td>
        <td>${_esc(x.b || "—")}</td>
        <td>${_esc(x.gap || "—")}</td></tr>`).join("");
  box.innerHTML = `
    ${fromCache ? `<div class="disclaimer">Kết quả đã lưu trong 1 giờ — bấm nút để chạy lại.</div>` : ""}
    <h4>Điểm giống</h4><ul class="auto-notes">${li(ans.same)}</ul>
    <h4>Khác biệt theo từng mặt</h4>
    <div class="table-wrap"><table>
      <thead><tr><th>Khía cạnh</th><th>${_esc(d.a || "A")}</th><th>${_esc(d.b || "B")}</th><th>Chênh lệch</th></tr></thead>
      <tbody>${diff || `<tr><td colspan="4">—</td></tr>`}</tbody></table></div>
    <div class="grid-2" style="margin-top:12px">
      <div><h4>Rủi ro riêng ${_esc(d.a || "A")}</h4><ul class="auto-notes">${li(ans.risks?.a)}</ul></div>
      <div><h4>Rủi ro riêng ${_esc(d.b || "B")}</h4><ul class="auto-notes">${li(ans.risks?.b)}</ul></div>
    </div>
    ${ans.note ? `<div class="interp-line">${_esc(ans.note)}</div>` : ""}
    <div class="disclaimer">${_esc(ans.disclaimer || "Thông tin giáo dục, không phải khuyến nghị đầu tư.")}</div>`;
}

function run() {
  const a = ($("#sym-a").value || "").trim().toUpperCase();
  const b = ($("#sym-b").value || "").trim().toUpperCase();
  if (!a || !b) return;
  $("#sym-a").value = a;
  $("#sym-b").value = b;
  _setUrl(a, b);
  $("#compare-result").innerHTML = skel("table", { rows: 8, cols: 3 });
  guardSection("#compare-result", () => doCompare(a, b));
}

function initCompare() {
  const p = _params();
  const a = (p.get("a") || "FPT").toUpperCase();
  const b = (p.get("b") || "VNM").toUpperCase();
  $("#sym-a").value = a;
  $("#sym-b").value = b;

  $("#sym-a").addEventListener("input", (e) => { e.target.value = e.target.value.toUpperCase(); });
  $("#sym-b").addEventListener("input", (e) => { e.target.value = e.target.value.toUpperCase(); });
  [$("#sym-a"), $("#sym-b")].forEach(el => el.addEventListener("keydown", (e) => {
    if (e.key === "Enter") run();
  }));
  $("#btn-compare").addEventListener("click", run);

  $("#compare-hints").querySelectorAll(".hint").forEach(h => {
    h.addEventListener("click", () => {
      $("#sym-a").value = h.dataset.a;
      $("#sym-b").value = h.dataset.b;
      run();
    });
  });

  run();
}

initCompare();
