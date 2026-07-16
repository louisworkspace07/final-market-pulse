/* Trang Danh mục — phân tích danh mục người dùng + tối ưu lượng tử */

/* ---------------- danh mục người dùng ---------------- */
function holdingRow(sym = "", qty = "") {
  const div = document.createElement("div");
  div.className = "holding-row";
  div.innerHTML = `
    <input class="h-sym" placeholder="Mã (VD: FPT)" value="${sym}">
    <input class="h-qty" placeholder="Khối lượng" type="number" min="0" value="${qty}">
    <button class="h-del" title="Xoá">✕</button>`;
  div.querySelector(".h-del").addEventListener("click", () => div.remove());
  return div;
}

function getHoldings() {
  return [...document.querySelectorAll(".holding-row")].map(r => ({
    symbol: r.querySelector(".h-sym").value.trim().toUpperCase(),
    qty: parseFloat(r.querySelector(".h-qty").value) || 0,
  })).filter(h => h.symbol && h.qty > 0);
}

function corrColor(v) {
  if (v >= 0.7) return "rgba(240,97,109,.35)";
  if (v >= 0.4) return "rgba(244,185,66,.25)";
  if (v <= -0.2) return "rgba(79,140,255,.25)";
  return "transparent";
}

let pfCharts = [];
function renderPortfolio(d) {
  pfCharts.forEach(c => c.destroy());
  pfCharts = [];
  const posRows = d.positions.map(p => `<tr>
    <td><b>${p.symbol}</b></td><td>${(p.name || "").slice(0, 30)}</td>
    <td>${p.sector}</td><td class="num num-mono">${fmtVN(p.qty, 0)}</td>
    <td class="num">${p.weight_pct}%</td>
    <td class="num">${p.health_score ?? "—"}</td></tr>`).join("");

  let corrHtml = "<p class='disclaimer'>Cần ≥ 2 mã có dữ liệu giá để tính tương quan.</p>";
  if (d.correlation) {
    const s = d.correlation.symbols;
    corrHtml = `<table class="corr-table"><tr><th></th>${s.map(x => `<th>${x}</th>`).join("")}</tr>` +
      d.correlation.matrix.map((row, i) =>
        `<tr><th>${s[i]}</th>${row.map(v =>
          `<td style="background:${corrColor(v)}">${fmtVN(v, 2)}</td>`).join("")}</tr>`
      ).join("") + "</table>";
  }

  const riskHtml = d.risk ? `
    <h3>Độ biến động danh mục: ${fmtVN(d.risk.portfolio_vol_pct, 2)}%/năm</h3>
    <canvas id="riskChart" height="${40 + d.risk.risk_contribution.length * 26}"></canvas>`
    : "<p class='disclaimer'>Không đủ dữ liệu giá để tính rủi ro.</p>";

  const reb = d.rebalance || {};
  const rebHtml = reb.error ? `<p class="disclaimer">${reb.error}</p>` : `
    <p style="font-size:13px;color:var(--muted)">${reb.method} — nghiệm tối ưu của
    MÔ HÌNH để tham khảo, không phải khuyến nghị giao dịch.</p>
    <div class="reb-tags">
      ${(reb.keep || []).map(s => `<span class="tag keep">${s} · trùng danh mục</span>`).join("")}
      ${(reb.add || []).map(s => `<span class="tag add">${s} · mô hình chọn</span>`).join("")}
      ${(reb.drop || []).map(s => `<span class="tag drop">${s} · ngoài nghiệm</span>`).join("")}
    </div>
    <p style="font-size:13px">Lợi suất kỳ vọng của cơ cấu mô hình: <b>${fmtVN(reb.exp_return_pct, 2)}%/năm</b>
    (kết quả mô hình — không phải cam kết)</p>`;

  const srcHtml = (d.sources || []).map(s =>
    `<div class="fact-row"><span class="flabel">${s.label}</span>
     <span class="fval">${s.source}${s.updated_at ? " · cập nhật " + s.updated_at : ""}</span>
     <span class="conf ${confClass(s.confidence)}">${s.confidence}</span></div>`).join("");

  $("#portfolio-result").innerHTML = `
    <div class="copilot-block">
      ${d.concentration_warning ? `<div class="warn-banner">⚠️ ${d.concentration_warning}</div>` : ""}
      ${(d.high_corr_pairs || []).length ? `<div class="warn-banner">🔗 Cặp mã "tưởng đa dạng mà cùng nhịp":
        ${d.high_corr_pairs.map(p => `${p.pair.join("–")} (ρ=${p.corr})`).join(", ")}</div>` : ""}
      ${(d.not_found || []).length ? `<div class="warn-banner">Không nhận diện được mã: ${d.not_found.join(", ")}</div>` : ""}
      <div class="pf-grid">
        <div class="card"><h3>Cơ cấu ngành (HHI = ${d.hhi})</h3><canvas id="sectorChart"></canvas></div>
        <div class="card"><h3>Ma trận tương quan (${d.risk ? d.risk.n_days + " phiên" : ""})</h3>
          <div class="table-wrap">${corrHtml}</div></div>
        <div class="card">${riskHtml}</div>
        <div class="card"><h3>Cơ cấu tối ưu theo mô hình (QUBO)</h3>${rebHtml}</div>
      </div>
      <div class="card" style="margin-top:14px"><h3>Chi tiết vị thế — tổng ${fmtMoney(d.total_value)}</h3>
        <div class="table-wrap"><table>
          <thead><tr><th>Mã</th><th>Công ty</th><th>Ngành</th><th class="num">KL</th>
          <th class="num">Tỷ trọng</th><th class="num">Điểm SK</th></tr></thead>
          <tbody>${posRows}</tbody></table></div></div>
      <details class="facts-panel card"><summary>Nguồn dữ liệu của phân tích này</summary>${srcHtml}</details>
    </div>`;

  pfCharts.push(new Chart($("#sectorChart"), {
    type: "doughnut",
    data: {
      labels: d.sectors.map(s => s.sector),
      datasets: [{ data: d.sectors.map(s => s.weight_pct),
        backgroundColor: ["#4f8cff", "#22d3a5", "#f4b942", "#f0616d", "#9b7bff", "#38bdf8", "#fb923c"] }],
    },
    options: { plugins: { legend: { position: "right" } } },
  }));

  if (d.risk) {
    pfCharts.push(new Chart($("#riskChart"), {
      type: "bar",
      data: {
        labels: d.risk.risk_contribution.map(r => r.symbol),
        datasets: [
          { label: "Tỷ trọng vốn %", data: d.risk.risk_contribution.map(r => r.weight_pct), backgroundColor: "#4f8cff" },
          { label: "Đóng góp rủi ro %", data: d.risk.risk_contribution.map(r => r.risk_pct), backgroundColor: "#f0616d" },
        ],
      },
      options: { indexAxis: "y", plugins: { legend: { position: "bottom" } } },
    }));
  }
}

async function analyzePortfolio() {
  const holdings = getHoldings();
  if (!holdings.length) {
    $("#portfolio-result").innerHTML =
      `<div class="warn-banner">Nhập ít nhất 1 mã kèm khối lượng > 0.</div>`;
    return;
  }
  const btn = $("#portfolio-btn");
  btn.disabled = true;
  $("#portfolio-result").innerHTML =
    `<div class="card copilot-block"><span class="spinner"></span>Đang phân tích danh mục...</div>`;
  try {
    const r = await fetch("/api/portfolio/analyze", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ holdings }),
    });
    const d = await r.json();
    if (d.error) $("#portfolio-result").innerHTML = `<div class="warn-banner">${d.error}</div>`;
    else renderPortfolio(d);
  } catch (e) {
    $("#portfolio-result").innerHTML = `<div class="warn-banner">Lỗi: ${e.message}</div>`;
  }
  btn.disabled = false;
}

const holdingsBox = $("#holdings-rows");
// prefill từ watchlist (/portfolio.html?syms=FPT,ACB) — mặc định demo 3 mã
{
  const pre = new URLSearchParams(location.search).get("syms");
  const seed = pre
    ? pre.split(",").map(s => [s.trim().toUpperCase(), 100]).filter(([s]) => s).slice(0, 12)
    : [["FPT", 100], ["VCB", 200], ["HPG", 500]];
  seed.forEach(([s, q]) => holdingsBox.appendChild(holdingRow(s, q)));
}
$("#add-holding").addEventListener("click", () => holdingsBox.appendChild(holdingRow()));
$("#portfolio-btn").addEventListener("click", analyzePortfolio);

/* ---------------- tối ưu lượng tử (QAOA demo) ---------------- */
async function renderQuantum() {
  const d = await getData("quantum_portfolio");
  const target = $("#quantum-result");
  let html = `<h3>Chọn ${d.k} / ${d.universe.length} mã · λ (ngại rủi ro) = ${d.risk_aversion}</h3>`;
  for (const [key, m] of Object.entries(d.methods)) {
    html += `<div class="method">
      <h4>${m.label}</h4>
      <div class="syms">${m.symbols.map(s => `<span class="sym">${s}</span>`).join("")}</div>
      <div class="stats">
        Lợi suất kỳ vọng: <b>${fmtVN(m.exp_return, 2)}%/năm</b> · Độ biến động: <b>${fmtVN(m.volatility, 2)}%</b>
        ${m.optimality_gap_pct != null ? `<span data-advanced> · Optimality gap vs brute-force: <b>${fmtVN(m.optimality_gap_pct, 2)}%</b></span>` : ""}
      </div>
    </div>`;
  }
  html += `<div class="stats" style="margin-top:6px">
    PennyLane: <b>${d.pennylane_available ? "sẵn sàng (QAOA mô phỏng lượng tử)" : "chưa cài — đang dùng quantum-inspired SA"}</b>
    · Universe: ${d.universe.join(", ")}</div>`;
  target.innerHTML = html;
}
guardSection("#quantum-result", renderQuantum);
