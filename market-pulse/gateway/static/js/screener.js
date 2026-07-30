/* Bộ lọc dữ liệu (A5) — screener % khớp.
   Đọc health_scores.json (BCTC market.db). Mỗi mã tính % khớp = số tiêu chí
   ĐANG BẬT mà mã thỏa / tổng số tiêu chí đang bật × 100. Chưa bật tiêu chí
   nào → hiện toàn bộ danh sách, cột % khớp = "—". Đây là bộ lọc DỮ LIỆU tài
   chính (BCTC), KHÔNG phải tín hiệu mua/bán — tuân thủ legal.py toàn hệ thống. */

const FILTERS = [
  { id: "z_safe", label: "Z'' vùng an toàn (>2,6)", risk: false, test: (c) => c.z_zone === "An toàn" },
  { id: "f_high", label: "F-score ≥ 7", risk: false, test: (c) => c.f_score != null && c.f_score >= 7 },
  { id: "health_high", label: "Điểm sức khỏe ≥ 70", risk: false, test: (c) => c.health_score != null && c.health_score >= 70 },
  { id: "roe_high", label: "ROE ≥ 15%", risk: false, test: (c) => c.roe != null && c.roe >= 15 },
  { id: "roa_high", label: "ROA ≥ 8%", risk: false, test: (c) => c.roa != null && c.roa >= 8 },
  { id: "debt_low", label: "Nợ/TS ≤ 50%", risk: false, test: (c) => c.debt_ratio != null && c.debt_ratio <= 50 },
  { id: "z_danger", label: "Z'' vùng nguy hiểm (<1,1)", risk: true, test: (c) => c.z_zone === "Nguy hiểm" },
  { id: "f_low", label: "F-score ≤ 3", risk: true, test: (c) => c.f_score != null && c.f_score <= 3 },
];

const activeIds = new Set();
let ALL = [];

function _groupLabel(g) {
  if (g === "DN") return "Doanh nghiệp";
  if (g === "TCTC") return "Tổ chức TC";
  return g || "—";
}

/* Chip filter — bấm để bật/tắt. Trạng thái BẬT tô màu accent (hoặc đỏ cho
   nhóm "soi rủi ro") bằng style inline vì style.css không được sửa ở đây. */
function _chipHtml(f) {
  const on = activeIds.has(f.id);
  // Pill phẳng v3 (.tfpill). Nhóm rủi ro khi BẬT tô đỏ token để phân biệt.
  const riskStyle = on && f.risk ? ' style="border-color:var(--down);background:rgba(225,64,64,.12);color:var(--down)"' : "";
  return `<span class="tfpill${on ? " active" : ""}" data-fid="${f.id}"${riskStyle}>${on ? "✓ " : ""}${_esc(f.label)}</span>`;
}

function drawFilters() {
  const main = FILTERS.filter((f) => !f.risk).map(_chipHtml).join("");
  const risk = FILTERS.filter((f) => f.risk).map(_chipHtml).join("");
  $("#scr-filters").innerHTML = `
    <div style="font-size:12.5px;color:var(--muted);margin-bottom:8px">Bật/tắt tiêu chí để lọc — có thể chọn nhiều tiêu chí cùng lúc</div>
    <div class="tfpills">${main}</div>
    <div class="tfpills" style="margin-top:10px">
      <span class="src" style="margin-right:2px">Soi rủi ro:</span>${risk}
    </div>`;
  $("#scr-filters").querySelectorAll("[data-fid]").forEach((el) => {
    el.onclick = () => {
      const id = el.dataset.fid;
      if (activeIds.has(id)) activeIds.delete(id); else activeIds.add(id);
      drawFilters();
      drawTable();
    };
  });
}

/* % khớp cho 1 mã dựa trên các tiêu chí ĐANG BẬT. null nếu chưa bật gì. */
function _matchInfo(c) {
  if (!activeIds.size) return null;
  const matched = FILTERS.filter((f) => activeIds.has(f.id) && f.test(c));
  return { pct: Math.round((matched.length / activeIds.size) * 100), matched };
}

/* §12: micro-bar TĨNH cho bảng (không animation/ResizeObserver — nhẹ cho ~150
   hàng). Dùng health_score batch có sẵn; thiếu dữ liệu → thanh xám. */
function _scoreMicro(v) {
  if (v == null || !isFinite(v)) return `<span class="mpbar-micro missing" title="chưa chấm điểm"></span>`;
  const p = Math.max(0, Math.min(100, v));
  return `<span class="mpbar-micro" title="Điểm sức khỏe ${fmtVN(v,0)}/100 — phải = khỏe hơn theo mô hình"><i style="left:${p}%"></i></span>`;
}

function drawTable() {
  const q = ($("#scr-search").value || "").trim().toLowerCase();
  let rows = ALL.filter((c) =>
    !q || c.symbol.toLowerCase().includes(q) || (c.name || "").toLowerCase().includes(q));

  rows = rows.map((c) => ({ c, m: _matchInfo(c) }));

  if (activeIds.size) {
    rows.sort((a, b) => (b.m.pct - a.m.pct) || ((b.c.health_score ?? -1) - (a.c.health_score ?? -1)));
  } else {
    rows.sort((a, b) => (b.c.health_score ?? -1) - (a.c.health_score ?? -1));
  }

  const total = rows.length;
  rows = rows.slice(0, 150);

  const trs = rows.map(({ c, m }) => {
    const chips = m && m.matched.length
      ? m.matched.map((f) =>
          `<span class="mini-tag" style="display:inline-block;margin:1px 3px 1px 0;
             background:${f.risk ? "rgba(225,64,64,.12)" : "rgba(0,108,236,.12)"};
             color:${f.risk ? "var(--down)" : "var(--primary)"}">${_esc(f.label)}</span>`)
          .join("")
      : "—";
    return `<tr>
      <td>${wlStar(c.symbol)} <a href="/co-phieu/${c.symbol}" style="display:inline-flex;align-items:center;gap:7px;color:var(--accent);font-weight:700;text-decoration:none">${window.MPChart ? MPChart.symLogoHTML(c.symbol) : ""}${_esc(c.symbol)}</a></td>
      <td title="${_esc(c.name || "")}">${_esc((c.name || "—").slice(0, 34))}</td>
      <td>${_esc(_groupLabel(c.group))}</td>
      <td class="num">${m ? fmtVN(m.pct, 1) + "%" : "—"}</td>
      <td>${chips}</td>
      <td>${_scoreMicro(c.health_score)}</td>
      <td class="num">${c.health_score != null ? fmtVN(c.health_score, 0) : "—"}</td>
      <td class="num">${c.z_score != null ? fmtVN(c.z_score, 2) : "—"}</td>
      <td class="num">${c.f_score != null ? `${c.f_score}/${c.f_max}` : "—"}</td>
      <td class="num">${c.roe != null ? fmtVN(c.roe, 1) : "—"}</td>
    </tr>`;
  }).join("");

  $("#scr-table-body").innerHTML = trs ||
    `<tr><td colspan="10" style="text-align:center;color:var(--muted);padding:20px">Không tìm thấy mã phù hợp.</td></tr>`;

  $("#scr-count").textContent = activeIds.size
    ? `${total} mã · sắp theo % khớp ${activeIds.size} tiêu chí đã bật (hiện tối đa 150 mã đầu)`
    : `${total} mã · sắp theo Điểm sức khỏe (hiện tối đa 150 mã đầu)`;
}

async function renderScreener() {
  const body = $("#scr-body");
  body.innerHTML = skel("table", { rows: 10, cols: 6 });

  const data = await getData("health_scores");
  ALL = data.companies || [];

  if (!ALL.length) {
    body.innerHTML = emptyState("Chưa có dữ liệu sức khỏe doanh nghiệp để lọc.", "🧮");
    return;
  }

  body.innerHTML = `
    <div class="interp-line">Bộ lọc mô tả <b>DỮ LIỆU</b> tài chính — không phải tín hiệu mua/bán.
      Bật các tiêu chí bên dưới để xem % khớp từng mã; tắt hết để xem toàn bộ danh sách.
      ${sourceTag("health_scores.json (BCTC market.db)", data.updated_at)}</div>
    <div class="card" id="scr-filters" style="margin-bottom:14px"></div>
    <div class="card">
      <div class="table-tools">
        <input id="scr-search" placeholder="Tìm mã / tên công ty...">
      </div>
      <div class="src" id="scr-count" style="margin-bottom:8px"></div>
      <div class="table-wrap">
        <table><thead><tr>
          <th>Mã</th><th>Công ty</th><th>Nhóm</th><th class="num">% khớp</th>
          <th>Điều kiện khớp</th><th>Tổng</th><th class="num">Điểm SK</th><th class="num">Z''</th>
          <th class="num">F</th><th class="num">ROE %</th>
        </tr></thead><tbody id="scr-table-body"></tbody></table>
      </div>
      <div class="disclaimer">Dữ liệu tổng hợp từ BCTC (Altman Z''-score, Piotroski F-score, điểm sức khỏe) — không cấu thành khuyến nghị đầu tư.</div>
    </div>`;

  drawFilters();
  drawTable();
  $("#scr-search").addEventListener("input", drawTable);
}

guardSection("#scr-body", renderScreener);
