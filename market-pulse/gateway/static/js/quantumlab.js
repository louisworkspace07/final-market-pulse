/* Quantum Lab — wizard 3 bước: universe → quiz khẩu vị (λ) → QUBO 3 solver.
   Quiz map (PDF triage 44): bảo thủ λ=4 · cân bằng λ=2 · tăng trưởng λ=1. */

let UNI = [];               // universe từ API
const picked = new Set();   // mã đã chọn

/* ---------- điều hướng bước ---------- */
function gotoStep(n) {
  for (const s of [1, 2, 3]) {
    document.getElementById(`qstep-${s}`).style.display = s === n ? "" : "none";
  }
  document.querySelectorAll("#qlab-stepbar .tabpill").forEach(p =>
    p.classList.toggle("active", +p.dataset.step === n));
}
document.querySelectorAll("#qlab-stepbar .tabpill").forEach(p =>
  p.addEventListener("click", () => gotoStep(+p.dataset.step)));

/* ---------- BƯỚC 1: universe ---------- */
function drawChips() {
  const q = document.getElementById("uni-search").value.trim().toLowerCase();
  const rows = UNI.filter(u => !q || u.symbol.toLowerCase().includes(q) ||
    u.name.toLowerCase().includes(q)).slice(0, 80);
  document.getElementById("uni-chips").innerHTML = rows.map(u => `
    <span class="tfpill hint${picked.has(u.symbol) ? " active" : ""}" data-sym="${u.symbol}"
      title="${_esc(u.name)} · ${u.n_days} phiên">
      ${u.symbol}</span>`).join("");
  document.getElementById("uni-count").textContent = picked.size;
  document.querySelectorAll("#uni-chips .hint").forEach(ch =>
    ch.addEventListener("click", () => {
      const s = ch.dataset.sym;
      picked.has(s) ? picked.delete(s) : picked.size < 14 && picked.add(s);
      drawChips();
    }));
}

async function initUniverse() {
  const r = await fetch("/api/quantum/universe");
  const d = await r.json();
  UNI = d.symbols || [];
  document.getElementById("uni-src").textContent =
    `${UNI.length} mã có ≥60 phiên giá trong market.db`;
  // prefill từ watchlist: /quantum-lab?syms=FPT,VCB,...
  const pre = new URLSearchParams(location.search).get("syms");
  if (pre) {
    const valid = new Set(UNI.map(u => u.symbol));
    pre.split(",").map(s => s.trim().toUpperCase())
      .filter(s => valid.has(s)).slice(0, 14).forEach(s => picked.add(s));
  }
  drawChips();
}

document.getElementById("uni-search").addEventListener("input", drawChips);
document.getElementById("pick-default").addEventListener("click", () => {
  picked.clear();
  UNI.slice(0, 12).forEach(u => picked.add(u.symbol));
  drawChips();
});
document.getElementById("to-step2").addEventListener("click", () => {
  if (picked.size < 4) { alert("Chọn ít nhất 4 mã (khuyến nghị 6–14)."); return; }
  gotoStep(2);
});

/* ---------- BƯỚC 2: quiz khẩu vị ---------- */
const QUIZ = [
  {
    q: "Danh mục mô phỏng giảm 15% trong 1 tháng — phản ứng gần với bạn nhất?",
    opts: [["Rất khó chịu, muốn giảm biến động ngay", 3],
           ["Chấp nhận được nếu nằm trong kịch bản", 2],
           ["Bình thường — biến động là một phần của thị trường", 1]],
  },
  {
    q: "Khoảng thời gian bạn dự kiến giữ một cấu hình danh mục?",
    opts: [["Dưới 6 tháng", 3], ["6 tháng – 2 năm", 2], ["Trên 2 năm", 1]],
  },
  {
    q: "Giữa hai cấu hình cùng điểm mô hình, bạn nghiêng về…",
    opts: [["Biến động thấp hơn dù lợi suất kỳ vọng thấp hơn", 3],
           ["Cân bằng giữa hai yếu tố", 2],
           ["Lợi suất kỳ vọng cao hơn dù biến động cao hơn", 1]],
  },
];
const PROFILE = { high: ["Bảo thủ", 4], mid: ["Cân bằng", 2], low: ["Tăng trưởng", 1] };

/* Q3 — regime-aware: đèn chế độ tiền tệ CHỈ đổi λ mặc định + hiện lý do.
   User luôn thấy con số cuối và có thể đổi câu trả lời quiz. Không khuyến nghị. */
let REGIME = null;
async function loadRegime() {
  try {
    const r = await fetch("/api/macro/regime");
    const d = await r.json();
    if (d.available) REGIME = d;
  } catch { /* thiếu regime vẫn chạy bình thường */ }
}
function regimeAdjust(lam) {
  if (!REGIME) return { lam, note: "" };
  if (REGIME.state === "THẮT CHẶT")
    return { lam: Math.min(lam + 1, 8),
      note: ` · môi trường tiền tệ ${REGIME.state} (điểm ${REGIME.score}) — biến động lịch sử trong pha này thường cao hơn, λ mặc định +1` };
  if (REGIME.state === "NỚI LỎNG")
    return { lam: Math.max(lam - 0.5, 0.5),
      note: ` · môi trường tiền tệ ${REGIME.state} (điểm ${REGIME.score}) — λ mặc định −0,5` };
  return { lam, note: ` · môi trường tiền tệ ${REGIME.state} — λ giữ nguyên` };
}

function drawQuiz() {
  document.getElementById("quiz-body").innerHTML = QUIZ.map((it, i) => `
    <div style="margin:12px 0">
      <div style="font-weight:600;font-size:13.5px;margin-bottom:7px">${i + 1}. ${it.q}</div>
      <div class="tfpills" style="flex-wrap:wrap">${it.opts.map(([t, v], j) =>
        `<span class="tfpill quiz-opt" data-q="${i}" data-v="${v}" data-j="${j}">${t}</span>`).join("")}
      </div></div>`).join("");
  document.querySelectorAll(".quiz-opt").forEach(o =>
    o.addEventListener("click", () => {
      document.querySelectorAll(`.quiz-opt[data-q="${o.dataset.q}"]`).forEach(x =>
        { x.classList.remove("active", "chosen"); });
      o.classList.add("active", "chosen");
      updateProfile();
    }));
}

function currentLambda() {
  const chosen = [...document.querySelectorAll(".quiz-opt.chosen")];
  if (chosen.length < QUIZ.length) return null;
  const avg = chosen.reduce((s, o) => s + (+o.dataset.v), 0) / chosen.length;
  return avg >= 2.5 ? PROFILE.high : avg >= 1.7 ? PROFILE.mid : PROFILE.low;
}

function updateProfile() {
  const p = currentLambda();
  if (!p) {
    document.getElementById("quiz-result").textContent = "Trả lời đủ 3 câu để xác định hồ sơ.";
    return;
  }
  const adj = regimeAdjust(p[1]);
  document.getElementById("quiz-result").textContent =
    `Hồ sơ: ${p[0]} → λ = ${adj.lam} (phạt rủi ro trong hàm mục tiêu)${adj.note}`;
}

/* ---------- BƯỚC 3: chạy + kết quả ---------- */
document.getElementById("run-lab").addEventListener("click", async () => {
  const p = currentLambda();
  if (!p) { alert("Trả lời đủ 3 câu trước khi chạy."); return; }
  const lam = regimeAdjust(p[1]).lam;   // Q3: λ mặc định điều chỉnh theo regime
  const k = +document.getElementById("qlab-k").value;
  gotoStep(3);
  document.getElementById("qlab-result").innerHTML = "";
  document.getElementById("qlab-steps").innerHTML = skeleton(2);

  const r = await fetch("/api/quantum/run", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbols: [...picked], k, risk_aversion: lam }),
  });
  const { job_id, error } = await r.json();
  if (error) {
    document.getElementById("qlab-steps").innerHTML = errorBox(error);
    return;
  }
  poll(job_id, p);
});

function stepIcon(s) {
  return s === "done" ? "✅" : s === "running" ? "⏳" : s === "error" ? "❌" : "⤼";
}

async function poll(jobId, profile) {
  const r = await fetch(`/api/quantum/status/${jobId}`);
  const st = await r.json();
  document.getElementById("qlab-steps").innerHTML = (st.steps || []).map(s => `
    <div class="step ${s.status}">
      <span>${stepIcon(s.status)}</span> <b>${_esc(s.name)}</b>
      <span style="color:var(--muted);font-size:12px">${_esc(s.detail || "")}</span>
    </div>`).join("");
  if (st.status === "running") { setTimeout(() => poll(jobId, profile), 1500); return; }
  if (st.status === "error") {
    document.getElementById("qlab-result").innerHTML = errorBox(st.error || "lỗi không rõ");
    return;
  }
  drawResult(st.result, profile);
}

function drawResult(d, profile) {
  const m = d.methods;
  const order = ["brute_force", "qaoa", "simulated_annealing"].filter(k => m[k]);
  const best = m.brute_force || m.simulated_annealing;

  const rows = order.map(k => {
    const x = m[k];
    return `<tr>
      <td><b>${_esc(x.label)}</b></td>
      <td class="num">${fmtVN(x.energy, 2)}</td>
      <td class="num">${x.optimality_gap_pct != null ? fmtVN(x.optimality_gap_pct, 2) + "%" : "—"}</td>
      <td class="num">${fmtVN(x.time_s, 2)}s</td>
      <td>${x.symbols.join(", ")}</td>
      <td class="num">${fmtVN(x.exp_return, 1)}%</td>
      <td class="num">${fmtVN(x.volatility, 1)}%</td>
      <td class="num">${x.sharpe != null ? fmtVN(x.sharpe, 2) : "—"}</td>
    </tr>`;
  }).join("");

  document.getElementById("qlab-result").innerHTML = `
    <div class="kpi-row">
      ${kpi("Hồ sơ khẩu vị", profile[0], `λ = ${d.risk_aversion} · K = ${d.k}`, "blue hero")}
      ${kpi("Lợi suất kỳ vọng*", fmtVN(best.exp_return, 1) + "%", "annualized, equal-weight, quá khứ", "blue")}
      ${kpi("Biến động*", fmtVN(best.volatility, 1) + "%", "độ lệch chuẩn năm hóa", "blue")}
      ${kpi("Sharpe*", best.sharpe != null ? fmtVN(best.sharpe, 2) : "—", "lợi suất / biến động (rf=0)", "blue")}
    </div>
    <div class="card" id="qlab-sharpe-bar" style="margin-bottom:12px"></div>
    <div class="card" data-advanced>
      <h3>Đối chứng 3 phương pháp trên cùng ma trận QUBO</h3>
      <div class="table-wrap"><table>
        <thead><tr><th>Phương pháp</th><th class="num">Năng lượng</th>
          <th class="num">Gap vs đúng</th><th class="num">Thời gian</th>
          <th>Danh mục chọn</th><th class="num">LS kỳ vọng*</th>
          <th class="num">Biến động*</th><th class="num">Sharpe*</th></tr></thead>
        <tbody>${rows}</tbody></table></div>
      <div style="margin-top:10px;font-size:12.5px;color:var(--muted)">
        * Thống kê LỊCH SỬ (${fmtVN(d.n_sessions, 0)} phiên, ×252) — quá khứ không bảo đảm tương lai.
        Năng lượng thấp hơn = nghiệm tốt hơn theo hàm mục tiêu <i>λ·rủi ro − lợi suất</i>.
      </div>
      <div style="margin-top:8px">${sourceTag(d.source)}</div>
    </div>
    <div class="card" style="margin-top:12px">
      <div class="grid-2">
        <div><canvas id="allocChart" height="180"></canvas></div>
        <div data-advanced>
          <h3>Đọc kết quả thế nào?</h3>
          <ol style="font-size:13px;line-height:1.7;padding-left:18px">
            <li><b>Brute-force</b> duyệt đủ 2^N tổ hợp — là nghiệm ĐÚNG để đối chứng.</li>
            <li><b>QAOA</b> chạy trên mô phỏng lượng tử PennyLane; <b>gap</b> cho biết
              nghiệm lượng tử kém nghiệm đúng bao nhiêu %.</li>
            <li><b>SA</b> là baseline quantum-inspired cổ điển.</li>
          </ol>
          <div class="disclaimer" style="margin-top:8px">${_esc(d.disclaimer)}</div>
        </div>
      </div>
    </div>`;

  // §12: thanh Sharpe chuẩn hóa clamp(−0.5..2) → 0–100 (phải = hiệu quả rủi ro tốt hơn)
  const sbBox = document.getElementById("qlab-sharpe-bar");
  if (sbBox && window.MPChart) {
    if (best.sharpe == null || !isFinite(best.sharpe)) {
      MPChart.mpBar(sbBox, { value: null, labelLeft: "kém hiệu quả", labelRight: "hiệu quả hơn" });
    } else {
      const sv = Math.max(0, Math.min(100, (best.sharpe + 0.5) / 2.5 * 100));
      MPChart.mpBar(sbBox, { value: sv, labelLeft: "Sharpe thấp (−0,5)", labelRight: "Sharpe cao (2,0+)",
        verdict: `Sharpe* danh mục ≈ ${fmtVN(best.sharpe, 2)} (lịch sử)`,
        reasons: [{ t: `LS kỳ vọng ${fmtVN(best.exp_return, 1)}%`, kind: "neu" },
                  { t: `biến động ${fmtVN(best.volatility, 1)}%`, kind: "neu" }],
        detailHtml: "Sharpe = lợi suất kỳ vọng / độ lệch chuẩn (rf=0), tính từ lịch sử — quá khứ không bảo đảm tương lai." });
    }
  }

  const c = chartColors();
  const picked_ = best.symbols;
  // Palette phẳng v3: dải xanh primary → xanh lá, không rainbow.
  const flatPal = ["#006CEC", "#3B8FF0", "#25B770", "#5AC98D", "#7FB2F5", "#1E9E5C", "#A7ADB2"];
  new Chart(document.getElementById("allocChart"), {
    type: "doughnut",
    data: { labels: picked_,
      datasets: [{ data: picked_.map(() => 1),
        borderWidth: 0,
        backgroundColor: picked_.map((_, i) => flatPal[i % flatPal.length]) }] },
    options: { plugins: { legend: { position: "right" },
      title: { display: true, text: `Danh mục ${best.symbols.length} mã (equal-weight)` } } },
  });
}

/* ---------- init ---------- */
drawQuiz();
updateProfile();
guardSection("#uni-chips", initUniverse);
loadRegime().then(updateProfile);
