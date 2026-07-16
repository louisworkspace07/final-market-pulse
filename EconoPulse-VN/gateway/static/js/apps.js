/* Trang Hệ sinh thái — quản trị 4 dự án thành phần: vai trò + đèn trạng thái +
   PID / Restart / Log cho 3 app con do cổng :9999 tự spawn. */

// App con nào cổng :9999 quản lý được (spawn/restart/log) + trang nhúng nội bộ.
const CHILD_IDS = ["crawl", "banggia", "econolens"];
const EMBED_PAGE = {
  crawl: "/data.html",
  banggia: "/banggia.html",
  econolens: "/copilot.html",
};

// Khối điều khiển pipeline SỐNG — chỉ thẻ Crawl Data mới có. Trạng thái
// bắt đầu/dừng/tiến độ nằm trong bộ nhớ tiến trình :5000, market.db không có,
// nên khối này BẮT BUỘC gọi HTTP (qua proxy /api/crawl/*) chứ không đọc thẳng
// đĩa như phần "Độ phủ nguồn" ở tab Dữ liệu gốc của trang cổ phiếu.
function crawlControlHTML() {
  return `
    <div class="crawl-ctl" id="crawl-ctl">
      <div class="crawl-cov" id="crawl-cov">Đang tải tiến độ…</div>
      <div class="crawl-form">
        <select id="crawl-group" title="Nhóm mã">
          <option value="VN30">VN30</option>
          <option value="VN100">VN100</option>
          <option value="HOSE">HOSE</option>
          <option value="HNX">HNX</option>
          <option value="UPCOM">UPCOM</option>
          <option value="ALL">Toàn bộ thị trường</option>
        </select>
        <select id="crawl-backend" title="Kênh AI">
          <option value="local_api">Local API</option>
          <option value="gemini">Gemini (CDP)</option>
          <option value="claude">Claude API</option>
        </select>
        <button class="open" id="crawl-start" style="cursor:pointer;border:0">▶ Bắt đầu</button>
        <button class="open" id="crawl-stop" style="cursor:pointer;border:0" disabled>■ Dừng</button>
        <button class="open" id="crawl-gcheck" style="cursor:pointer;border:0">⚙ Kiểm tra AI</button>
      </div>
      <div class="crawl-badge" id="crawl-gstate"></div>
      <div class="crawl-progress" id="crawl-progress" hidden>
        <div class="crawl-bar"><div class="crawl-bar-fill" id="crawl-bar-fill"></div></div>
        <div class="crawl-stat" id="crawl-stat"></div>
        <pre class="crawl-log" id="crawl-log"></pre>
      </div>
    </div>`;
}

async function renderServices() {
  const services = await (await fetch("/api/services")).json();
  $("#services").innerHTML = services.map(s => {
    const isChild = CHILD_IDS.includes(s.id);
    const page = EMBED_PAGE[s.id];
    const openLink = page
      ? `<a class="open" href="${page}">Mở trong cổng →</a>`
      : (s.url
          ? `<a class="open" href="${s.url}" target="_blank">Mở ↗</a>`
          : `<a class="open off">Desktop app</a>`);
    const adminRow = isChild ? `
        <div class="reb-tags" style="margin-top:10px;align-items:center">
          <span class="tag" id="pid-${s.id}" style="background:rgba(126,148,199,.12)">PID —</span>
          <button class="open" data-restart="${s.id}" style="cursor:pointer;border:0">⟳ Restart</button>
          <button class="open" data-log="${s.id}" style="cursor:pointer;border:0">📄 Log</button>
        </div>
        <pre id="log-${s.id}" style="display:none;margin-top:10px;max-height:240px;overflow:auto;
          font-size:12px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;
          padding:12px;white-space:pre-wrap"></pre>` : "";
    return `
    <div class="card service" id="svc-${s.id}">
      <div class="info">
        <h3>${s.name} <span class="svc-dot" title="trạng thái">●</span></h3>
        <p>${s.role}</p>
        <p style="margin-top:6px">Thư mục: <code>${s.dir}</code> · Chạy: <code>${s.cmd}</code></p>
        <div class="reb-tags" style="margin-top:8px">
          ${(s.provides || []).map(p => `<span class="tag keep">${p}</span>`).join("")}
        </div>
        ${adminRow}
        ${s.id === "crawl" ? crawlControlHTML() : ""}
      </div>
      ${openLink}
    </div>`;
  }).join("");

  // Nút Restart / Log cho từng app con.
  document.querySelectorAll("[data-restart]").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.dataset.restart;
      btn.textContent = "⏳ Đang khởi động…";
      btn.disabled = true;
      try {
        const r = await (await fetch(`/api/children/restart/${id}`, { method: "POST" })).json();
        btn.textContent = r.ok ? `✓ PID ${r.pid}` : `✗ ${r.error || "lỗi"}`;
      } catch (_) {
        btn.textContent = "✗ lỗi";
      }
      setTimeout(() => { btn.textContent = "⟳ Restart"; btn.disabled = false; }, 2500);
      refreshChildStatus();
    };
  });
  document.querySelectorAll("[data-log]").forEach(btn => {
    btn.onclick = async () => {
      const id = btn.dataset.log;
      const pre = document.getElementById(`log-${id}`);
      if (pre.style.display !== "none") { pre.style.display = "none"; return; }
      pre.style.display = "block";
      pre.textContent = "Đang tải log…";
      try {
        const r = await (await fetch(`/api/children/log/${id}`)).json();
        pre.textContent = (r.lines || []).join("\n") || "(log trống)";
        pre.scrollTop = pre.scrollHeight;
      } catch (_) {
        pre.textContent = "(không đọc được log)";
      }
    };
  });

  refreshServiceStatus();
  refreshChildStatus();
  initCrawlControl();
}

/* ---------------------------------------------------------------------
   Điều khiển pipeline Crawl Data (proxy /api/crawl/* → cổng 5000)
   ------------------------------------------------------------------- */
let _crawlPollTimer = null;
let _crawlSince = 0;

async function loadCrawlCoverage() {
  const el = document.getElementById("crawl-cov");
  if (!el) return;
  const group = document.getElementById("crawl-group")?.value || "";
  try {
    const c = await (await fetch(`/api/crawl/coverage?group=${encodeURIComponent(group)}`)).json();
    const vn = n => (n || 0).toLocaleString("vi-VN");
    el.textContent = `${vn(c.analyzed)}/${vn(c.total)} mã đã phân tích AI (nhóm ${c.group}) · `
      + `${vn(c.crawled_company)} đã crawl xong tin/sự kiện`;
  } catch (_) {
    el.textContent = "Không tính được tiến độ (market.db chưa sẵn sàng).";
  }
}

async function checkGeminiState() {
  const el = document.getElementById("crawl-gstate");
  const btn = document.getElementById("crawl-gcheck");
  if (!el || !btn) return;
  btn.disabled = true;
  const old = btn.textContent;
  btn.textContent = "⏳ Đang kiểm tra…";
  try {
    const backend = document.getElementById("crawl-backend")?.value || "local_api";
    const r = await (await fetch("/api/crawl/gemini_check", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ backend }),
    })).json();
    el.textContent = r.msg || (r.ok ? "Sẵn sàng" : "Chưa sẵn sàng");
    el.className = "crawl-badge " + (r.ok ? "ok" : "bad");
  } catch (_) {
    el.textContent = "Không kiểm tra được — dịch vụ Crawl Data (5000) có thể chưa chạy.";
    el.className = "crawl-badge bad";
  } finally {
    btn.disabled = false;
    btn.textContent = old;
  }
}

async function startCrawl() {
  const startBtn = document.getElementById("crawl-start");
  const group = document.getElementById("crawl-group").value;
  const backend = document.getElementById("crawl-backend").value;
  startBtn.disabled = true;
  try {
    const r = await (await fetch("/api/crawl/start", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group, backend }),
    })).json();
    if (!r.ok) {
      alert(r.msg || "Không bắt đầu được — có thể đang chạy tác vụ khác.");
      startBtn.disabled = false;
      return;
    }
    _crawlSince = 0;
    document.getElementById("crawl-log").textContent = "";
    document.getElementById("crawl-progress").hidden = false;
    pollCrawl();
  } catch (e) {
    alert("Lỗi: " + e.message);
    startBtn.disabled = false;
  }
}

async function stopCrawl() {
  const stopBtn = document.getElementById("crawl-stop");
  stopBtn.disabled = true;
  try {
    const r = await (await fetch("/api/crawl/stop", { method: "POST" })).json();
    if (!r.ok) alert(r.msg || "Không dừng được.");
  } catch (e) {
    alert("Lỗi: " + e.message);
  }
}

async function pollCrawl() {
  clearTimeout(_crawlPollTimer);
  try {
    const j = await (await fetch(`/api/crawl/poll?since=${_crawlSince}`)).json();
    _crawlSince = j.total ?? _crawlSince;
    const pr = j.progress || {};
    const done = (pr.done || 0) + (pr.errors || 0);
    const total = pr.total || 0;
    const pct = total ? Math.min(100, Math.round((done / total) * 100)) : 0;

    const fill = document.getElementById("crawl-bar-fill");
    const stat = document.getElementById("crawl-stat");
    const log = document.getElementById("crawl-log");
    const startBtn = document.getElementById("crawl-start");
    const stopBtn = document.getElementById("crawl-stop");
    const panel = document.getElementById("crawl-progress");
    // Trang vừa mở mà lượt crawl ĐÃ chạy từ trước (không phải do bấm Bắt đầu
    // ở đây) — vẫn phải hiện thanh tiến độ, không chỉ khi tự bấm.
    if (panel && j.running) panel.hidden = false;
    if (fill) fill.style.width = pct + "%";
    if (stat) {
      stat.textContent = `${j.task || "—"} · ${done.toLocaleString("vi-VN")}/${total.toLocaleString("vi-VN")}`
        + ` (${pr.errors || 0} lỗi)`
        + (j.eta ? ` · còn ~${Math.round(j.eta / 60)} phút` : "")
        + (!j.running ? " · ĐÃ DỪNG" : "");
    }
    if (log && j.lines && j.lines.length) {
      log.textContent += j.lines.join("\n") + "\n";
      log.scrollTop = log.scrollHeight;
    }
    if (startBtn) startBtn.disabled = !!j.running;
    if (stopBtn) stopBtn.disabled = !j.running;

    if (j.running) {
      _crawlPollTimer = setTimeout(pollCrawl, 2000);
    } else if (total > 0) {
      loadCrawlCoverage();   // lượt vừa xong → cập nhật lại tiến độ tổng
    }
  } catch (_) {
    _crawlPollTimer = setTimeout(pollCrawl, 5000);
  }
}

function initCrawlControl() {
  if (!document.getElementById("crawl-ctl")) return;   // thẻ crawl chưa render (hiếm)
  loadCrawlCoverage();
  document.getElementById("crawl-group").addEventListener("change", loadCrawlCoverage);
  document.getElementById("crawl-start").addEventListener("click", startCrawl);
  document.getElementById("crawl-stop").addEventListener("click", stopCrawl);
  document.getElementById("crawl-gcheck").addEventListener("click", checkGeminiState);
  // Trang vừa mở NHƯNG lượt crawl có thể đã chạy từ trước (mở lại trình
  // duyệt) — poll 1 lần để phát hiện, không chỉ chờ người dùng bấm Bắt đầu.
  pollCrawl();
}

async function refreshServiceStatus() {
  try {
    const st = await (await fetch("/api/services/status")).json();
    for (const [id, ok] of Object.entries(st)) {
      const dot = document.querySelector(`#svc-${id} .svc-dot`);
      if (!dot) continue;
      dot.style.color = ok === true ? "var(--accent2)" : ok === false ? "var(--danger)" : "var(--muted)";
      dot.title = ok === true ? "đang chạy" : ok === false ? "chưa bật" : "không kiểm tra được";
    }
  } catch (_) { }
}

async function refreshChildStatus() {
  try {
    const st = await (await fetch("/api/children/status")).json();
    for (const [id, info] of Object.entries(st)) {
      const el = document.getElementById(`pid-${id}`);
      if (!el) continue;
      el.textContent = info.pid
        ? `PID ${info.pid}`
        : (info.running ? "PID — (chạy sẵn)" : "PID — (tắt)");
    }
  } catch (_) { }
}

renderServices().catch(e => console.error(e));
setInterval(refreshServiceStatus, 20000);
setInterval(refreshChildStatus, 20000);
