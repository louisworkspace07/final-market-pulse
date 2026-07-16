/* Trang Copilot — hỏi đáp AI có phản biện + audit trail */
function renderCopilotAnswer(r) {
  const a = r.answer;
  // mode: "local_api" (server AI local, mặc định) | "api" (Gemini API key) |
  // "gemini" (tên cũ, giữ để tương thích) | "offline" (rule-based khi AI lỗi).
  const liveModes = ["local_api", "api", "gemini"];
  const badge = liveModes.includes(r.mode)
    ? `<span class="mode-badge"><span class="dot-live"></span> ${r.model} · ${r.elapsed_s}s</span>`
    : `<span class="mode-badge offline"><span class="dot-cache"></span> chế độ ngoại tuyến (rule-based)</span>`;

  // Explainability: nguồn dữ liệu + thời điểm phân tích
  const dataSrc = sourceTag("market.db (Crawl Data)", r.generated_at || new Date().toISOString());
  const aiSrc   = sourceTag(r.model || "AI phân tích", r.generated_at || new Date().toISOString());

  const factRows = (r.facts || []).map(f => `
    <div class="fact-row" id="fact-${f.id}">
      <span class="fid">${f.id}</span>
      <span class="flabel">${f.label}</span>
      <span class="fval">${f.value}<br><i>${f.source} · cập nhật ${f.updated_at || "?"}</i></span>
      <span class="conf ${confClass(f.confidence)}">${f.confidence}</span>
    </div>`).join("");

  $("#copilot-result").innerHTML = `
    <div class="copilot-block">
      <div style="margin-bottom:10px">${dataSrc} ${aiSrc}</div>
      <div class="verdict-card">${linkFacts(a.tom_tat_du_kien || a.verdict || "")} ${badge}</div>
      <div class="pillar-grid">
        <div class="pillar p-arg"><h4>Luận điểm chính</h4>
          <ul>${a.luan_diem.map(x => `<li>${linkFacts(x)}</li>`).join("")}</ul></div>
        <div class="pillar p-assume"><h4>Giả định đang dùng</h4>
          <ul>${a.gia_dinh.map(x => `<li>${linkFacts(x)}</li>`).join("")}</ul></div>
        <div class="pillar p-risk"><h4>Điều gì khiến nhận định SAI</h4>
          <ul>${a.rui_ro.map(x => `<li>${linkFacts(x)}</li>`).join("")}</ul></div>
      </div>
      <details class="facts-panel card" open>
        <summary>Audit trail — ${r.facts.length} sự kiện định lượng đã cấp cho AI (nguồn · thời điểm · độ tin cậy)</summary>
        ${factRows}
      </details>
      <div class="disclaimer">${a.disclaimer || "Thông tin giáo dục, không phải khuyến nghị đầu tư."}</div>
    </div>`;

  document.querySelectorAll(".fact-ref").forEach(el =>
    el.addEventListener("click", () => {
      const row = document.getElementById("fact-" + el.dataset.fid);
      if (row) {
        row.scrollIntoView({ behavior: "smooth", block: "center" });
        row.style.background = "rgba(37,183,112,.15)";
        setTimeout(() => row.style.background = "", 1600);
      }
    }));
}

async function askCopilot() {
  const q = $("#copilot-q").value.trim();
  if (!q) return;
  const btn = $("#copilot-btn");
  btn.disabled = true;
  $("#copilot-result").innerHTML =
    `<div class="card copilot-block"><span class="spinner"></span>
     Đang thu thập dữ liệu định lượng và phân tích có phản biện... (~20 giây)</div>`;
  try {
    const r = await fetch("/api/copilot/ask", {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    renderCopilotAnswer(await r.json());
  } catch (e) {
    $("#copilot-result").innerHTML = `<div class="warn-banner">Lỗi: ${e.message}</div>`;
  }
  btn.disabled = false;
}

$("#copilot-btn").addEventListener("click", askCopilot);
$("#copilot-q").addEventListener("keydown", e => { if (e.key === "Enter") askCopilot(); });
document.querySelectorAll(".hint").forEach(h =>
  h.addEventListener("click", () => { $("#copilot-q").value = h.dataset.q; askCopilot(); }));

// Trang khác chuyển sang với câu hỏi dựng sẵn: /copilot.html?q=... (nút "Hỏi Copilot" ở /co-phieu/<sym>)
{
  const preQ = new URLSearchParams(location.search).get("q");
  if (preQ) { $("#copilot-q").value = preQ; askCopilot(); }
}
