/* Trang Soi Tin — dán tin đồn → nhãn trung tính từng nhận định + dẫn chứng công bố */

const SOITIN_SAMPLES = [
  "Nghe nói HPG sắp chia cổ tức tiền mặt 20% trong tháng tới, anh em gom ngay kẻo lỡ sóng.",
  "VCB chuẩn bị phát hành thêm cổ phiếu để tăng vốn điều lệ cuối năm nay.",
  "Có tin thị trường sắp điều chỉnh mạnh vì áp lực tỷ giá cuối quý.",
];

// Nhãn trung tính → hiển thị (nhãn, class màu). Không có nhãn "thật/giả".
const LABEL_META = {
  co_cong_bo:       { text: "Có dữ liệu công bố liên quan", cls: "lbl-pub" },
  khong_thay:       { text: "Chưa có công bố xác nhận",     cls: "lbl-none" },
  khong_kiem_chung: { text: "Không kiểm chứng được",        cls: "lbl-na" },
  mau_thuan:        { text: "Mâu thuẫn với công bố",         cls: "lbl-conflict" },
};

/* Chip dẫn chứng [E..]/[N..] — tra evidence map do backend trả (như newsMap ở overview). */
function evidenceChips(ids, evMap) {
  return (ids || []).map(raw => {
    const id = String(raw).replace(/[\[\]]/g, "").trim();
    const e = evMap[id];
    if (!e) {
      return `<span class="evidence-chip missing" title="⚠ dẫn chứng không có trong dữ liệu: ${_esc(id)}">${_esc(id)} ⚠</span>`;
    }
    const tip = `(${fmtDateVN(e.date, false)}) ${e.symbol}: ${e.title}`;
    const inner = e.link
      ? `<a href="${_esc(e.link)}" target="_blank" rel="noopener">${_esc(id)}</a>`
      : _esc(id);
    return `<span class="evidence-chip" title="${_esc(tip)}">${inner}</span>`;
  }).join(" ");
}

function renderClaim(c, evMap) {
  const meta = LABEL_META[c.nhan] || LABEL_META.khong_kiem_chung;
  const chips = evidenceChips(c.bang_chung, evMap);
  return `
    <div class="claim-row">
      <div class="claim-head">
        <span class="claim-label ${meta.cls}">${meta.text}</span>
        <span class="claim-text">${_esc(c.text)}</span>
      </div>
      <div class="claim-body">
        <div class="claim-reason">${_esc(c.giai_thich || "")}</div>
        ${c.so_lieu_trich ? `<div class="claim-fig"><b>Số liệu trong công bố:</b> ${_esc(c.so_lieu_trich)}</div>` : ""}
        ${c.diem_lech ? `<div class="claim-gap"><b>Điểm lệch so với tin đồn:</b> ${_esc(c.diem_lech)}</div>` : ""}
        ${c.boi_canh ? `<div class="claim-ctx"><b>Bối cảnh liên quan:</b> ${_esc(c.boi_canh)}</div>` : ""}
        ${chips ? `<div class="claim-evidence">Dẫn chứng công bố: ${chips}</div>` : ""}
      </div>
    </div>`;
}

function renderSoitin(r) {
  if (r.error) {
    $("#soitin-result").innerHTML = `<div class="warn-banner">${_esc(r.error)}</div>`;
    return;
  }
  const a = r.answer;
  const badge = r.mode === "gemini"
    ? `<span class="mode-badge"><span class="dot-live"></span> ${_esc(r.transport)} · ${r.elapsed_s}s</span>`
    : `<span class="mode-badge offline"><span class="dot-cache"></span> chế độ ngoại tuyến (đối chiếu dữ liệu thuần)</span>`;
  const dataSrc = sourceTag("market.db (Crawl Data)", new Date().toISOString());

  const claims = (a.claims || []).map(c => renderClaim(c, r.evidence || {})).join("");

  $("#soitin-result").innerHTML = `
    <div class="copilot-block">
      <div style="margin-bottom:10px">${dataSrc} ${badge}</div>
      <div class="verdict-card">${_esc(a.tong_quan || "")}</div>
      <div class="claims-list">${claims}</div>
      <div class="disclaimer">${_esc(a.disclaimer || "")}</div>
    </div>`;
}

async function soiTin() {
  const text = $("#soitin-input").value.trim();
  if (!text) return;
  const btn = $("#soitin-btn");
  btn.disabled = true;
  $("#soitin-result").innerHTML =
    `<div class="card copilot-block"><span class="spinner"></span>
     Đang tách nhận định và đối chiếu với công bố chính thức trong market.db...</div>`;
  try {
    const r = await fetch("/api/factcheck", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ text }),
    });
    renderSoitin(await r.json());
  } catch (e) {
    $("#soitin-result").innerHTML = `<div class="warn-banner">Lỗi: ${_esc(e.message)}</div>`;
  }
  btn.disabled = false;
}

// Nạp 3 tin mẫu — bấm để điền + soi luôn.
(function initSamples() {
  const box = $("#soitin-samples");
  if (!box) return;
  box.innerHTML = SOITIN_SAMPLES.map((s, i) =>
    `<span class="tfpill hint" data-i="${i}">Tin mẫu ${i + 1}</span>`).join("");
  box.querySelectorAll(".hint").forEach(h =>
    h.addEventListener("click", () => {
      $("#soitin-input").value = SOITIN_SAMPLES[+h.dataset.i];
      soiTin();
    }));
})();

$("#soitin-btn").addEventListener("click", soiTin);
