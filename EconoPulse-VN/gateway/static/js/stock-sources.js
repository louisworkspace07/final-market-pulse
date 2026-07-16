/* ============================================================================
   Tab "Dữ liệu gốc" — phơi TOÀN BỘ tệp Crawl Data đã cào cho mã đang xem.

   Trước đây các nguồn này chỉ xem được ở cổng 5000 (bảng điều khiển crawl), nên
   người dùng cổng 9999 không biết hệ thống đang giữ những gì. Ở đây đọc qua:
     GET /api/stock/<mã>/sources          → có những nguồn nào
     GET /api/stock/<mã>/source/<khóa>    → nội dung, đã lọc khoá khuyến nghị

   Bảng dựng generic từ khóa của bản ghi đầu — thêm nguồn mới ở backend là tự
   hiện, không phải sửa file này.
   ========================================================================== */
(function (global) {
  "use strict";

  const MAX_COLS = 8;          // nhiều cột hơn thì bảng không đọc nổi trên 1 màn
  const esc = (s) => String(s == null ? "" : s)
    .replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const NICE = {
    officer_name: "Họ tên", officer_position: "Chức vụ",
    officer_own_percent: "Tỷ lệ sở hữu", officer_own_quantity: "Số cổ phiếu",
    share_holder: "Cổ đông", share_own_percent: "Tỷ lệ", quantity: "Số lượng",
    sub_company_name: "Công ty con", company_name: "Công ty",
    ownership_percent: "Tỷ lệ sở hữu", charter_capital: "Vốn điều lệ",
    title: "Tiêu đề", public_date: "Ngày", news_title: "Tiêu đề",
    date: "Ngày", price: "Giá", volume: "Khối lượng", period: "Kỳ",
    item: "Chỉ tiêu", value: "Giá trị", item_id: "Mã chỉ tiêu",
    // nguồn "ai_debug" (analysis/debug/index.json)
    key: "Khía cạnh", ok: "Thành công", error: "Lỗi", attempts: "Số lần thử",
    retried: "Đã thử lại", secs: "Thời gian (giây)",
    prompt_chars: "Độ dài prompt", raw_chars: "Độ dài trả lời",
    // nguồn "manifest" (manifest.json)
    n_sources: "Tổng số nguồn", n_present: "Số nguồn có dữ liệu",
    completeness_pct: "Độ phủ (%)", generated_at: "Sinh lúc",
  };

  function cell(v) {
    if (v == null || v === "") return "—";
    if (typeof v === "number") {
      // Tỷ lệ vnstock lưu dạng 0.0689 = 6,89% — đổi sang % cho dễ đọc.
      return Math.abs(v) < 1 && v !== 0
        ? (v * 100).toLocaleString("vi-VN", { maximumFractionDigits: 2 }) + "%"
        : v.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
    }
    const s = String(v);
    return esc(s.length > 140 ? s.slice(0, 140) + "…" : s);
  }

  function tableHTML(rows) {
    if (!rows.length) return `<p class="src-empty">Nguồn này rỗng.</p>`;
    // Ưu tiên cột có tên đẹp, bỏ cột mà mọi dòng đều trống.
    const keys = Object.keys(rows[0])
      .filter((k) => k !== "symbol" && rows.some((r) => r[k] != null && r[k] !== ""))
      .sort((a, b) => (NICE[b] ? 1 : 0) - (NICE[a] ? 1 : 0))
      .slice(0, MAX_COLS);
    const head = keys.map((k) => `<th>${esc(NICE[k] || k)}</th>`).join("");
    const body = rows.map((r) =>
      `<tr>${keys.map((k) => `<td>${cell(r[k])}</td>`).join("")}</tr>`).join("");
    return `<div class="src-tablewrap"><table class="src-table">
      <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
  }

  function objHTML(obj) {
    const rows = Object.entries(obj || {})
      .filter(([, v]) => v != null && v !== "" && typeof v !== "object")
      .map(([k, v]) => `<tr><th>${esc(NICE[k] || k)}</th><td>${cell(v)}</td></tr>`)
      .join("");
    return rows ? `<div class="src-tablewrap"><table class="src-table src-kv">
      <tbody>${rows}</tbody></table></div>` : `<p class="src-empty">Không có trường nào.</p>`;
  }

  async function openSource(sym, key, host, hint) {
    host.innerHTML = `<p class="src-empty">Đang tải…</p>`;
    try {
      const r = await fetch(`/api/stock/${encodeURIComponent(sym)}/source/${encodeURIComponent(key)}`);
      if (!r.ok) throw new Error("HTTP " + r.status);
      const d = await r.json();
      const note = d.truncated
        ? `<p class="src-note">Hiện ${d.rows.length} trên tổng ${d.total.toLocaleString("vi-VN")} bản ghi.</p>`
        : "";
      // Nguồn rỗng phải NÓI RÕ vì sao rỗng. "Nguồn này rỗng." khiến người đọc
      // kết luận doanh nghiệp không có dữ liệu loại đó, trong khi thực tế là
      // nguồn cụ thể ấy không trả — và dữ liệu thật nằm ở nguồn khác.
      const body = (d.kind === "table" && !(d.rows || []).length && hint)
        ? `<p class="src-empty">${esc(hint)}</p>`
        : (d.kind === "table" ? tableHTML(d.rows || []) : objHTML(d.data));
      host.innerHTML = body + note + `<p class="src-path">Nguồn: ${esc(d.source || "")}</p>`;
    } catch (e) {
      host.innerHTML = `<p class="src-empty">Không tải được (${esc(e.message)}).</p>`;
    }
  }

  /* 18 nguồn trải thành MỘT hàng pill phẳng thì "Cổ đông lớn" đứng cạnh "Lưu
     chuyển tiền tệ" mà không có gì cho biết chúng khác loại — mắt phải đọc hết
     18 nhãn mới tìm ra cái cần. Xếp theo nhóm mà server trả về, mỗi nhóm một
     hàng có tiêu đề. Nguồn rỗng dồn xuống cuối nhóm và làm mờ: vẫn thấy được là
     "đã hỏi, nguồn không có", nhưng không tranh chỗ với nguồn có dữ liệu. */
  function pillHTML(s, on) {
    const cnt = s.kind === "object"
      ? ""                                     // nguồn dạng hồ sơ không đếm bản ghi
      : `<span class="src-count">${(s.total || 0).toLocaleString("vi-VN")}</span>`;
    return `<button type="button" class="src-pill${on ? " on" : ""}${s.empty ? " is-empty" : ""}"
      data-key="${esc(s.key)}"${s.hint ? ` title="${esc(s.hint)}"` : ""}>${esc(s.label)}${cnt}</button>`;
  }

  async function load(hostId, sym) {
    const host = typeof hostId === "string" ? document.getElementById(hostId) : hostId;
    if (!host) return false;
    host.innerHTML = `<p class="src-empty">Đang tìm dữ liệu đã cào…</p>`;
    let list = [], groups = [];
    try {
      const j = await (await fetch(`/api/stock/${encodeURIComponent(sym)}/sources`)).json();
      list = j.sources || [];
      groups = j.groups || [];
    } catch (_) { /* để rơi xuống nhánh rỗng */ }
    if (!list.length) {
      host.innerHTML = `<p class="src-empty">Chưa cào được dữ liệu nào cho mã này.</p>`;
      return false;
    }

    // Gateway cũ (chưa có khoá `groups`) → dồn tất cả vào một nhóm không tên,
    // giao diện vẫn chạy y như trước thay vì trắng trang.
    if (!groups.length) groups = [{ key: "", label: "" }];
    const first = list.find((s) => !s.empty) || list[0];
    const blocks = groups.map((g) => {
      const items = list.filter((s) => (s.group || "") === g.key)
        .sort((a, b) => (a.empty ? 1 : 0) - (b.empty ? 1 : 0));
      if (!items.length) return "";
      return `<div class="src-group">
        ${g.label ? `<div class="src-group-h">${esc(g.label)}</div>` : ""}
        <div class="src-pills">${items.map((s) => pillHTML(s, s === first)).join("")}</div>
      </div>`;
    }).join("");

    const nEmpty = list.filter((s) => s.empty).length;
    host.innerHTML = `
      <p class="src-intro">Đây là dữ liệu thô hệ thống đã cào cho ${esc(sym)} —
        cùng nguồn mà mọi con số và biểu đồ trên trang lấy ra.
        <b>${list.length} nguồn</b>, tổng
        <b>${list.reduce((s, x) => s + (x.total || 0), 0).toLocaleString("vi-VN")}</b> bản ghi${
          nEmpty ? `; ${nEmpty} nguồn được làm mờ là nguồn đã hỏi nhưng không trả dữ liệu` : ""}.</p>
      ${blocks}
      <div id="src-body"></div>`;

    const body = host.querySelector("#src-body");
    const hintOf = {};
    list.forEach((s) => { if (s.hint) hintOf[s.key] = s.hint; });
    host.querySelectorAll(".src-pill").forEach((b) => {
      b.addEventListener("click", () => {
        host.querySelectorAll(".src-pill").forEach((x) => x.classList.remove("on"));
        b.classList.add("on");
        openSource(sym, b.dataset.key, body, hintOf[b.dataset.key]);
      });
    });
    openSource(sym, first.key, body, hintOf[first.key]);
    return true;
  }

  global.MPSources = { load };
})(window);
