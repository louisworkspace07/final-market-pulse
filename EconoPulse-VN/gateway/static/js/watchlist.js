/* Danh sách theo dõi (A6) — đọc localStorage, ghép điểm SK từ health_scores. */

async function renderWatchlist() {
  const syms = wlGet();
  const body = document.getElementById("wl-body");
  if (!syms.length) {
    body.innerHTML = emptyState(
      "Chưa có mã nào. Bấm ☆ cạnh tên mã ở trang cổ phiếu (/co-phieu/<mã>) hoặc tìm bằng Ctrl+K.", "⭐");
    return;
  }
  let hmap = {};
  try {
    const d = await getData("health_scores");
    (d.companies || []).forEach(c => { hmap[c.symbol] = c; });
  } catch { /* health thiếu vẫn hiện danh sách */ }

  const logo = s => window.MPChart ? MPChart.symLogoHTML(s) : "";
  // §12: micro-bar tĩnh dùng health_score batch (phải = khỏe hơn); thiếu → xám.
  const _wlScoreMicro = (v) => (v == null || !isFinite(v))
    ? `<span class="mpbar-micro missing" title="chưa chấm điểm"></span>`
    : `<span class="mpbar-micro" title="Điểm sức khỏe ${fmtVN(v,0)}/100 — phải = khỏe hơn theo mô hình"><i style="left:${Math.max(0,Math.min(100,v))}%"></i></span>`;
  const rows = syms.map(s => {
    const h = hmap[s] || {};
    return `<tr>
      <td>${wlStar(s)} <a href="/co-phieu/${s}" style="display:inline-flex;align-items:center;gap:7px;color:var(--accent);font-weight:700;text-decoration:none">${logo(s)}${s}</a></td>
      <td title="${_esc(h.name || "")}">${_esc((h.name || "—").slice(0, 40))}</td>
      <td><span class="wl-spark" id="wl-sp-${s}" style="display:inline-block;width:60px;height:24px"></span></td>
      <td>${_wlScoreMicro(h.health_score)}</td>
      <td class="num">${h.health_score != null ? fmtVN(h.health_score, 0) : "—"}</td>
      <td class="num">${h.z_score != null ? fmtVN(h.z_score, 2) : "—"}</td>
      <td>${_esc(h.z_zone || "—")}</td>
      <td class="num">${h.f_score != null ? `${h.f_score}/${h.f_max}` : "—"}</td>
      <td class="num">${h.roe != null ? fmtVN(h.roe, 1) : "—"}</td>
    </tr>`;
  }).join("");

  body.innerHTML = `<div class="card"><div class="table-wrap">
    <table><thead><tr>
      <th>Mã</th><th>Công ty</th><th>Giá 30 phiên</th><th>Tổng</th><th class="num">Điểm SK</th><th class="num">Z''</th>
      <th>Vùng</th><th class="num">F</th><th class="num">ROE %</th>
    </tr></thead><tbody>${rows}</tbody></table></div>
    <div style="margin-top:8px">${sourceTag("localStorage + health_scores.json + market.db (giá)")}</div></div>`;

  // Sparkline giá — nạp riêng từng mã (danh sách nhỏ, do người dùng chọn).
  if (window.MPChart) syms.forEach(async s => {
    try {
      const d = await (await fetch(`/api/stock/${s}`)).json();
      const series = d.price && d.price.series;
      if (series && series.length > 1)
        MPChart.svgSparkline(`#wl-sp-${s}`, series.slice(-30).map(p => p[1]), {});
    } catch { /* mã chưa có giá → để trống */ }
  });
}

document.getElementById("wl-analyze").onclick = () => {
  // trang Danh mục đọc ?syms= để prefill holdings
  location.href = "/portfolio.html?syms=" + wlGet().join(",");
};
document.getElementById("wl-qlab").onclick = () => {
  location.href = "/quantum-lab?syms=" + wlGet().join(",");
};

guardSection("#wl-body", renderWatchlist);
