/* Tab "Phân tích 360" của /co-phieu/<sym> (plan §5.2b, P1–P20).
   Lazy: chỉ fetch /api/stock/<sym>/analysis khi mở tab. window.renderAnalysis. */
(function () {
  const M = window.MPChart;
  let done = false, data = null, _root = null;

  const NS = "http://www.w3.org/2000/svg";
  const el = (t, a) => { const e = document.createElementNS(NS, t); for (const k in a) e.setAttribute(k, a[k]); return e; };
  const prefersReduced = () =>
    window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* radar 5 trục SVG thuần (0–100). Nâng cấp §10:
     - trục thiếu dữ liệu (score=null) vẽ XÁM + nhãn "thiếu dữ liệu" (không cho 0 giả)
     - overlay trung vị ngành: marker vàng nét đứt trên trục có a.sector != null
     - animation scale từ tâm 400ms + dot stagger (chỉ khi animate=true & không reduced-motion)
     - hover trục → tooltip công thức; click trục → cuộn tới section (a.anchor)
     opts: {animate, showSector, onAxisClick} */
  function radarSVG(axes, size, opts = {}) {
    const c = M._C(), cx = size / 2, cy = size / 2, R = size / 2 - 40, n = axes.length;
    const svg = el("svg", { viewBox: `0 0 ${size} ${size}`, width: "100%",
      style: "max-width:360px", class: "radar-svg" });
    const ang = (i) => i / n * 2 * Math.PI;
    const pt = (a, r) => [cx + r * Math.cos(a - Math.PI / 2), cy + r * Math.sin(a - Math.PI / 2)];

    // lưới 5 vòng
    for (let g = 1; g <= 5; g++) {
      const pts = axes.map((_, i) => pt(ang(i), R * g / 5).join(",")).join(" ");
      svg.appendChild(el("polygon", { points: pts, fill: "none", stroke: c.border, "stroke-width": ".5", opacity: ".6" }));
    }
    // nan trục (score=null) → điểm neo tại tâm để polygon không "phình" giả
    const rOf = (a) => R * (a.score != null ? a.score : 0) / 100;

    // trục + nhãn (nhãn bấm được nếu có anchor)
    axes.forEach((a, i) => {
      const [x, y] = pt(ang(i), R);
      svg.appendChild(el("line", { x1: cx, y1: cy, x2: x, y2: y, stroke: c.border, "stroke-width": ".5" }));
      const [lx, ly] = pt(ang(i), R + 18);
      const missing = a.score == null;
      const g = el("g", { class: "radar-axis-label" + (a.anchor ? " clickable" : ""),
        "data-anchor": a.anchor || "", tabindex: a.anchor ? "0" : null });
      const t = el("text", { x: lx, y: ly, "text-anchor": "middle", "font-size": "11.5",
        fill: missing ? c.muted : c.text, "font-weight": "600" });
      t.textContent = a.axis;
      g.appendChild(t);
      const t2 = el("text", { x: lx, y: ly + 13, "text-anchor": "middle", "font-size": "10.5",
        fill: missing ? c.muted : c.primary, "font-weight": "700" });
      t2.textContent = missing ? "thiếu dữ liệu" : Math.round(a.score);
      g.appendChild(t2);
      // tooltip công thức (hover)
      const tip = el("title"); tip.textContent = (a.formula || a.note || "") + (missing ? " · chưa đủ dữ liệu để tính" : "");
      g.appendChild(tip);
      if (a.anchor && opts.onAxisClick) {
        g.style.cursor = "pointer";
        g.addEventListener("click", () => opts.onAxisClick(a.anchor));
        g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); opts.onAxisClick(a.anchor); } });
      }
      svg.appendChild(g);
    });

    // overlay trung vị ngành (nét đứt vàng) — CHỈ trục có a.sector != null
    if (opts.showSector) {
      const secPts = axes.map((a, i) => (a.sector != null ? pt(ang(i), R * a.sector / 100) : null));
      // vẽ marker + đoạn nối giữa các trục liền kề có dữ liệu ngành
      axes.forEach((a, i) => {
        if (a.sector == null) return;
        const [x, y] = secPts[i];
        svg.appendChild(el("circle", { cx: x, cy: y, r: 3.5, fill: "none",
          stroke: c.ref, "stroke-width": "1.6", class: "radar-sector-dot" }));
      });
    }

    // vùng điểm chính (mã) — animate scale từ tâm
    const poly = axes.map((a, i) => pt(ang(i), rOf(a)).join(",")).join(" ");
    const area = el("polygon", { points: poly, fill: c.primary, "fill-opacity": ".22",
      stroke: c.primary, "stroke-width": "2", class: "radar-area" });
    svg.appendChild(area);
    const dots = axes.map((a, i) => {
      if (a.score == null) return null;
      const [x, y] = pt(ang(i), rOf(a));
      const dot = el("circle", { cx: x, cy: y, r: 3.5, fill: c.primary, class: "radar-dot" });
      svg.appendChild(dot);
      return dot;
    });

    // animation scale từ tâm 400ms + dot stagger
    if (opts.animate && !prefersReduced()) {
      area.style.transform = `scale(0)`;
      area.style.transformOrigin = `${cx}px ${cy}px`;
      area.style.transition = "transform .4s cubic-bezier(.22,1,.36,1)";
      requestAnimationFrame(() => { area.style.transform = "scale(1)"; });
      dots.forEach((d, i) => {
        if (!d) return;
        d.style.opacity = "0";
        d.style.transition = "opacity .25s ease";
        setTimeout(() => { d.style.opacity = "1"; }, 180 + i * 70);
      });
    }
    return svg;
  }

  function yv(series) { return (series || []).map(x => x.value); }
  function yl(series) { return (series || []).map(x => String(x.year != null ? x.year : x.period)); }

  /* B15 · so ngành 2 tầng: Cơ bản = mpBar percentile + 1 câu; Chuyên sâu = strip gốc.
     host: card để append vào; d = {self, median, peers:[{sym,value}], unit};
     opts: {label, higherIsBetter, fmtVal(v)}. percentile tính từ peers (đã đảo chiều
     nếu higherIsBetter=false — thấp hơn = thuận lợi hơn, ví dụ P/E, Nợ/VCSH). */
  function stripWithBar(host, d, opts) {
    opts = opts || {};
    const lab = opts.label || "Chỉ số";
    const hib = opts.higherIsBetter !== false;
    const fv = opts.fmtVal || ((v) => (v != null && isFinite(v) ? String(Math.round(v * 100) / 100) : "—"));
    const peers = (d.peers || []).filter(p => p && p.value != null && isFinite(p.value));
    const self = d.self;
    // Cơ bản: mpBar percentile
    const barBox = document.createElement("div");
    if (self != null && isFinite(self) && peers.length >= 3) {
      // % số mã mà "mã này thuận lợi hơn" theo chiều đã công bố
      const better = peers.filter(p => hib ? self > p.value : self < p.value).length;
      const pct = Math.round(better / peers.length * 100);
      const sentence = `${lab} ${fv(self)} — ${hib ? "cao hơn" : "thấp/rẻ hơn"} ${pct}% mã cùng ngành`;
      const kind = pct >= 60 ? "ok" : pct <= 35 ? "bad" : "neu";
      host.appendChild(barBox);
      M.mpBar(barBox, { value: pct, labelLeft: "kém hơn ngành", labelRight: "thuận lợi hơn ngành",
        verdict: sentence, reasons: [{ t: `trung vị ngành ${fv(d.median)}`, kind: "neu" }] });
    } else {
      // thiếu peer → mpBar xám "chưa đủ dữ liệu" (không bịa)
      host.appendChild(barBox);
      M.mpBar(barBox, { value: null, labelLeft: "kém hơn ngành", labelRight: "thuận lợi hơn ngành",
        verdict: `${lab}: chưa đủ mã ngành để xếp hạng` });
    }
    // Chuyên sâu: strip gốc
    const adv = document.createElement("div"); adv.setAttribute("data-advanced", "");
    host.appendChild(adv);
    M.svgStrip(adv, { self, median: d.median, peers, unit: d.unit },
      { empty: `Chưa đủ dữ liệu ${lab}`, higherIsBetter: hib });
  }

  /* B14 · "đủ chỗ, ghi rõ lý do": render 1 slot XÁM khi thiếu dữ liệu thay vì ẩn im lặng. */
  function slotMissing(host, label, reason) {
    const box = document.createElement("div"); box.className = "slot-missing";
    box.innerHTML = `<span class="sm-label">${_esc(label)}</span>` +
      `<span class="sm-reason">chưa đủ dữ liệu${reason ? " — " + _esc(reason) : ""}</span>`;
    host.appendChild(box);
  }

  /* ======================================================================
     WS-11 · Phụ lục A (A1 · A2 · A3-UI · A5)
     ----------------------------------------------------------------------
     A1 — 3 TRẠNG THÁI AI phải trông khác nhau. Đo trên market.db 2026-07-27:
          1.531 mã, 576 có bản ghi ai_analysis, trong đó 57 mã mode=ai_error
          và 105 mã lưu được 0 khía cạnh; 955 mã CHƯA TỪNG chạy AI. Trước đây
          cả ba đều hiện na ná nhau nên F0 tưởng app hỏng.
     A2 — 2 chế độ đọc, DÙNG LẠI công tắc chung của shell-v3.js
          (body.mode-basic + localStorage "mp_mode" + event "mp:mode"). Không
          tạo khoá localStorage thứ hai: một người bật "đơn giản" ở trang chủ
          thì sang tab này phải vẫn là đơn giản.
     A3 — MỌI con số kèm HẬU TỐ KỲ. Lý do có thật: cùng mã FPT, API trả
          `valuation.pe.value=13,09` (TTM tới 2026-Q1) trong khi
          `peers.self.pe=15,91` (kỳ 2025) — hai P/E lệch 21% trên cùng một tab
          vì chốt ở hai kỳ khác nhau. Số không có kỳ là số vô nghĩa.
     A5 — vốn hóa trần ("107,8 nghìn tỷ") đổi thành hạng trong ngành
          ("#1/27 ngành Công nghệ"), tính từ /api/market/heatmap.
     PHÁP LÝ §6: không rating/target_price/recommendation, không mua-bán-nắm
     giữ, không dự báo giá; chỉ mô tả quá khứ/hiện tại bằng ngôn ngữ phân vị.
     ====================================================================== */

  /* ---- A2 · chế độ đọc: đọc/ghi qua công tắc chung, không tự phát minh ---- */
  function isSimple() { return document.body.classList.contains("mode-basic"); }
  function setSimple(simple) {
    if (typeof window.mpSetMode === "function") { window.mpSetMode(simple ? "basic" : "advanced"); return; }
    // shell-v3.js chưa nạp (trang lẻ) → vẫn giữ đúng khoá chung
    document.body.classList.toggle("mode-basic", simple);
    try { localStorage.setItem("mp_mode", simple ? "basic" : "advanced"); } catch (_) {}
    window.dispatchEvent(new CustomEvent("mp:mode", { detail: simple ? "basic" : "advanced" }));
  }

  /* Thanh chuyển chế độ. aria-pressed để trình đọc màn hình biết nút nào đang
     bật; Tab tới được vì là <button> thật (không phải div bắt click). */
  function readBar() {
    const bar = document.createElement("div");
    bar.className = "f0-readbar";
    bar.innerHTML =
      `<span class="f0-readbar-lab" id="f0-readbar-lab">Cách đọc trang này</span>` +
      `<span class="f0-readsw" role="group" aria-labelledby="f0-readbar-lab">` +
      `<button type="button" data-simple="1" aria-pressed="false">Giải thích đơn giản</button>` +
      `<button type="button" data-simple="0" aria-pressed="false">Bản đầy đủ</button>` +
      `</span>`;
    const sync = () => bar.querySelectorAll("button").forEach(b =>
      b.setAttribute("aria-pressed", String((b.dataset.simple === "1") === isSimple())));
    bar.querySelectorAll("button").forEach(b => b.addEventListener("click", () => {
      setSimple(b.dataset.simple === "1");
      sync(); applyMode();
    }));
    sync();
    window.addEventListener("mp:mode", () => { sync(); applyMode(); });
    return bar;
  }

  /* Khối chỉ hiện ở 1 chế độ. Dùng `hidden` (không phải display:none trong CSS)
     để vẫn đúng khi <link> f0-analysis.css chưa được nhúng vào template. */
  function applyMode() {
    const s = isSimple();
    document.querySelectorAll("#analysis-root [data-only]").forEach(n => {
      n.hidden = (n.dataset.only === "simple") !== s;
    });
  }

  /* ---- A3 · hậu tố kỳ ---------------------------------------------------
     perLabel("2025") → "số liệu năm 2025"
     perLabel("2026-Q1") → "theo báo cáo quý 1/2026"
     perLabel("TTM tới 2026-Q1") → "bốn quý gần nhất, tính tới quý 1/2026"  */
  function perLabel(period) {
    const p = String(period == null ? "" : period).trim();
    if (!p) return "";
    const ttm = p.match(/^TTM\s*tới\s*(\d{4})-Q([1-4])$/i);
    if (ttm) return `bốn quý gần nhất, tính tới quý ${ttm[2]}/${ttm[1]}`;
    const q = p.match(/^(\d{4})-Q([1-4])$/);
    if (q) return `theo báo cáo quý ${q[2]}/${q[1]}`;
    if (/^\d{4}$/.test(p)) return `số liệu năm ${p}`;
    return `kỳ ${p}`;
  }
  /* Hậu tố dạng chữ nhỏ gắn NGAY CẠNH con số. Không dùng title= (mobile
     không tap được title) — đây là chữ hiện sẵn. */
  function per(period) {
    const t = perLabel(period);
    return t ? `<span class="f0-per">${_esc(t)}</span>` : "";
  }
  /* Hộp giải thích khi 2 nguồn cùng tên chỉ số mà khác kỳ (A3, nguyên nhân gốc
     của "P/E lệch 44%"): ghi rõ kỳ ở CẢ HAI chỗ thay vì chọn bừa một số. */
  function periodClashBox(name, a, b) {
    if (!a || !b || !a.period || !b.period || a.period === b.period) return "";
    if (a.value == null || b.value == null) return "";
    return `<div class="f0-perbox">Trang này có hai cách tính ${_esc(name)}, chốt ở hai kỳ khác nhau — ` +
      `nên hai số không bằng nhau và cả hai đều đúng với kỳ của nó: ` +
      `<b>${fmtVN(a.value, 2)}</b> ${_esc(perLabel(a.period))}, và ` +
      `<b>${fmtVN(b.value, 2)}</b> ${_esc(perLabel(b.period))}.</div>`;
  }

  /* ---- A2 · nhãn thuật ngữ: LUÔN qua MPTerm để cả site chỉ có 1 định nghĩa ---- */
  function T(key, label) {
    return window.MPTerm ? window.MPTerm.chip(key, label) : _esc(label != null ? label : key);
  }
  function Tplain(key) { return window.MPTerm ? window.MPTerm.plain(key) : ""; }

  /* ---- A2 · mốc so sánh: số trần thì F0 không biết tốt hay xấu ----------
     pct = percentile ngành ĐÃ chuẩn hóa chiều bởi peers.py (100 = thuận lợi
     nhất theo mô hình), nên diễn đạt bằng vùng cao/giữa/thấp — KHÔNG "rẻ/đắt",
     KHÔNG khuyến nghị. */
  function bandWord(pct) {
    if (pct == null || !isFinite(pct)) return null;
    return pct >= 70 ? "thuộc vùng cao" : pct >= 40 ? "thuộc vùng giữa" : "thuộc vùng thấp";
  }
  function vsMedian(self, median, unit, nSample) {
    if (self == null || !isFinite(self) || median == null || !isFinite(median)) return "";
    const u = unit || "";
    return ` So với mức giữa của ngành là ${fmtVN(median, 2)}${u}` +
      (nSample ? ` (đo trên ${nSample} doanh nghiệp cùng ngành)` : "") + ".";
  }

  window.renderAnalysis = async function () {
    if (done) return; done = true;
    const root = document.getElementById("analysis-root");
    // skeleton đúng hình: 1 card radar + 2 card biểu đồ (không spinner + chữ)
    root.innerHTML =
      `<div class="card stock-sec">${skel("radar", { height: 300 })}</div>`
      + `<div class="card stock-sec">${skel("chart", { height: 200 })}</div>`
      + `<div class="card stock-sec">${skel("table", { rows: 5, cols: 5 })}</div>`;
    try {
      data = await (await fetch(`/api/stock/${window.MP_SYMBOL}/analysis`)).json();
    } catch (e) { root.innerHTML = `<div class="chart-empty">Không tải được dữ liệu phân tích: ${e.message}</div>`; return; }
    if (data.error) { root.innerHTML = `<div class="chart-empty">${data.error}</div>`; return; }
    root.innerHTML = "";
    _root = root;   // B14: cho section()/missingCard() append card xám vào đúng gốc

    /* §12 · ONE BAR tổng "Nền tảng theo mô hình" — Cơ bản THAY radar (radar
       chi tiết ẩn sau [data-advanced]); bấm ⓘ → xem số liệu gốc / bảng trục. */
    const ob = data.onebar && data.onebar.total;
    if (ob) {
      const obCard = document.createElement("div"); obCard.className = "card stock-sec"; obCard.id = "onebar-total";
      obCard.innerHTML = `<h3 class="sec-h">Nền tảng theo mô hình
        <span class="src">${ob.n_scored}/${ob.n_axes} yếu tố · thang 0–100 · <a href="/methodology.html#onebar">cách tính</a></span></h3>`;
      const barBox = document.createElement("div"); obCard.appendChild(barBox);
      M.mpBar(barBox, {
        value: ob.value, labelLeft: ob.label_left, labelRight: ob.label_right,
        verdict: ob.verdict, reasons: ob.reasons,
        detailHtml: "Chi tiết 5 trục &amp; công thức xem trong phần radar bên dưới (chế độ Chuyên sâu) hoặc trang Phương pháp.",
      });
      obCard.insertAdjacentHTML("beforeend", `<div class="disclaimer-box">Thanh mô tả nền tảng định lượng của quá khứ — không phải khuyến nghị đầu tư.</div>`);
      root.appendChild(obCard);
    }

    /* P1 · Radar 360 (chi tiết — Chuyên sâu; Cơ bản dùng One Bar ở trên) */
    const rd = data.radar;
    if (rd && rd.axes && rd.axes.length) {
      const hasSector = rd.axes.some(a => a.sector != null);
      const card = document.createElement("div"); card.className = "card stock-sec"; card.id = "radar360";
      if (ob) card.setAttribute("data-advanced", "");   // Cơ bản ẩn radar, chỉ hiện One Bar
      const secNote = hasSector ? ` · trung vị ngành ${rd.sector_n ? "(" + rd.sector_n + " mã)" : ""}` : "";
      card.innerHTML = `<h3 class="sec-h">Đánh giá 360
        <span class="src">${rd.n_scored}/${rd.n_axes} trục có dữ liệu · thang 0–100 · trọng số &amp; công thức tại <a href="/methodology.html#radar360">Phương pháp</a>${secNote}</span></h3>`;

      // hàng công cụ: toggle "So với ngành" (chỉ khi có dữ liệu ngành)
      if (hasSector) {
        const tools = document.createElement("div"); tools.className = "radar-tools";
        tools.innerHTML = `<label class="radar-sec-toggle"><input type="checkbox" id="radar-sec-cb"> <span>So với ngành</span> <em class="radar-sec-key"></em></label>`;
        card.appendChild(tools);
      }

      const wrap = document.createElement("div"); wrap.className = "radar-wrap";
      const scrollTo = (anchor) => {
        const target = document.getElementById("an-" + anchor) || root.querySelector(`[data-sec="${anchor}"]`);
        if (target) target.scrollIntoView({ behavior: prefersReduced() ? "auto" : "smooth", block: "center" });
      };
      const drawRadar = (showSector) => {
        const old = wrap.querySelector(".radar-svg"); if (old) old.remove();
        const svg = radarSVG(rd.axes, 300, { animate: !old, showSector, onAxisClick: scrollTo });
        wrap.insertBefore(svg, wrap.firstChild);
      };

      // badge tổng lớn (nhãn trung tính)
      const badge = document.createElement("div"); badge.className = "radar-badge";
      const tone = rd.overall == null ? "na" : rd.overall >= 70 ? "hi" : rd.overall >= 50 ? "mid" : rd.overall >= 35 ? "low" : "warn";
      badge.innerHTML = `<div class="rb-score tone-${tone}">${rd.overall != null ? Math.round(rd.overall) : "—"}</div>
        <div class="rb-label">${_esc(rd.label || "")}</div>`;
      wrap.appendChild(badge);
      card.appendChild(wrap);
      drawRadar(false);

      // bảng trục — thêm cột trung vị ngành khi có
      const tbl = document.createElement("table"); tbl.className = "radar-axis-tbl";
      tbl.innerHTML = `<thead><tr><th>Trục</th><th class="num">Điểm</th>${hasSector ? '<th class="num">Ngành</th>' : ""}<th>Ý nghĩa</th></tr></thead><tbody>`
        + rd.axes.map(a => {
          const sc = a.score != null ? Math.round(a.score) : '<span style="color:var(--muted)">thiếu dữ liệu</span>';
          const sec = hasSector ? `<td class="num">${a.sector != null ? Math.round(a.sector) : "—"}</td>` : "";
          const clk = a.anchor ? ` class="ax-row clickable" data-anchor="${_esc(a.anchor)}"` : "";
          return `<tr${clk}><td>${_esc(a.axis)}</td><td class="num ax-score">${sc}</td>${sec}<td style="color:var(--muted)">${_esc(a.note || "")}</td></tr>`;
        }).join("") + `</tbody>`;
      tbl.querySelectorAll(".ax-row.clickable").forEach(tr =>
        tr.addEventListener("click", () => scrollTo(tr.dataset.anchor)));
      card.appendChild(tbl);

      card.insertAdjacentHTML("beforeend", `<div class="disclaimer-box">Điểm tổng hợp mô tả nền tảng theo mô hình định lượng — không phải khuyến nghị đầu tư. <a href="/methodology.html#radar360">Vì sao có hình radar này?</a></div>`);
      root.appendChild(card);

      // toggle overlay ngành
      const cb = card.querySelector("#radar-sec-cb");
      if (cb) {
        const key = card.querySelector(".radar-sec-key");
        cb.addEventListener("change", () => {
          drawRadar(cb.checked);
          if (key) key.textContent = cb.checked ? "▬ nét vàng = trung vị ngành (chỉ trục đủ dữ liệu)" : "";
        });
      }
    }

    /* P2 · Tích cực / Hạn chế (từ f_checks + peers position) */
    const h = data.health, pk = data.peers;
    const pos = [], neg = [];
    (h && h.f_checks || []).forEach(fc => (fc.pass ? pos : neg).push(fc.c));
    if (pk && pk.position) {
      const good = { "cao hơn": 1, "thấp hơn": 0 };
      if (pk.position.roe && pk.position.roe.includes("cao")) pos.push("ROE cao hơn trung vị ngành");
      if (pk.position.net_margin && pk.position.net_margin.includes("cao")) pos.push("Biên ròng cao hơn trung vị ngành");
      if (pk.position.debt_to_equity && pk.position.debt_to_equity.includes("cao")) neg.push("Đòn bẩy cao hơn trung vị ngành");
    }
    const card2 = document.createElement("div"); card2.className = "card stock-sec";
    card2.innerHTML = `<h3 class="sec-h">Tích cực &amp; Hạn chế <span class="src">Từ 9 tiêu chí F-score + so ngành — dữ kiện</span></h3>
      <div class="two-col-bullets">
        <div><b style="color:var(--up)">✓ Tích cực</b><ul class="auto-notes">${pos.length ? pos.map(t => `<li class="ok">${_esc(t)}</li>`).join("") : '<li class="neu">Chưa có điểm nổi bật rõ</li>'}</ul></div>
        <div><b style="color:var(--down)">✗ Hạn chế</b><ul class="auto-notes">${neg.length ? neg.map(t => `<li class="bad">${_esc(t)}</li>`).join("") : '<li class="neu">Chưa ghi nhận hạn chế rõ</li>'}</ul></div>
      </div>`;
    root.appendChild(card2);

    /* P7 · Định giá strips (P/E, P/B vs ngành + peers) */
    const val = data.valuation;
    section(!!val, () => {
      const card7 = document.createElement("div"); card7.className = "card stock-sec"; card7.id = "an-valuation";
      card7.innerHTML = `<h3 class="sec-h">Chỉ số định giá so ngành <span class="src">${_esc(secVI(val.sector) || "")} · ${val.n_peers || 0} mã</span></h3>`;
      root.appendChild(card7);
      const pv = val.peer_values || {};
      // B14: LUÔN render đủ 3 slot định giá (P/E · P/B · EV/EBITDA); thiếu → xám + lý do,
      // người dùng đếm đủ bộ, không "5 yếu tố sao chỉ có 3".
      const slots = [
        ["pe", "P/E", "cần EPS dương từ BCTC"],
        ["pb", "P/B", "cần giá trị sổ sách từ BCTC"],
        ["ev_ebitda", "EV/EBITDA", "chưa tính EV/EBITDA (cần nợ ròng + EBITDA)"],
      ];
      slots.forEach(([k, lab, why]) => {
        const peers = (pv[k] || []);
        const self = val.self ? val.self[k] : null;
        const cnt = peers.length ? ` <span class="src">${peers.length} mã cùng ngành</span>` : "";
        card7.insertAdjacentHTML("beforeend", `<div style="font-size:12px;color:var(--muted);margin:10px 0 2px">${lab}${cnt}</div>`);
        const d2 = document.createElement("div"); card7.appendChild(d2);
        if (self == null || !isFinite(self)) { slotMissing(d2, lab, why); return; }
        // P/E, P/B, EV/EBITDA: THẤP hơn = rẻ/thuận lợi hơn → higherIsBetter=false
        stripWithBar(d2, { self, median: val.benchmark && val.benchmark[k], peers, unit: "lần" },
          { label: lab, higherIsBetter: false, fmtVal: (v) => v != null && isFinite(v) ? fmtVN(v, 1) : "—" });
      });
      if (val.band && val.band.note) card7.insertAdjacentHTML("beforeend", `<div class="disclaimer-box">${_esc(val.band.note)} — dải thống kê lịch sử, KHÔNG phải định giá mục tiêu.</div>`);
    }, "Chỉ số định giá so ngành", "cần P/E, P/B từ BCTC và ≥3 mã cùng ngành", "valuation");

    /* P12 · DT–LN + biên ròng (combo) */
    const cb = data.combo;
    section(cb && cb.years && cb.years.length, () => {
      const card12 = card("Doanh thu &amp; Lợi nhuận", `CAGR DT ${fmtPct(cb.revenue_cagr)} · CAGR LN ${fmtPct(cb.profit_cagr)} · nguồn financials`, "combo");
      root.appendChild(card12.card);
      const notes = [];
      if (cb.revenue_cagr != null) notes.push({ t: `Doanh thu ${cb.revenue_cagr >= 0 ? "tăng" : "giảm"} bình quân ${fmtPct(cb.revenue_cagr)}/năm (4 năm)`, kind: cb.revenue_cagr >= 0 ? "ok" : "bad" });
      if (cb.profit_cagr != null) notes.push({ t: `Lợi nhuận ${cb.profit_cagr >= 0 ? "tăng" : "giảm"} bình quân ${fmtPct(cb.profit_cagr)}/năm`, kind: cb.profit_cagr >= 0 ? "ok" : "bad" });
      M.mpTrend(card12.body, cb.profit.map(p => ({ label: String(p.year), value: p.value })),
        { title: "LNST theo năm", metric: "LNST", unit: " tỷ", higherIsBetter: true, notes });
    }, "Doanh thu &amp; Lợi nhuận", "cần ≥2 năm doanh thu/LNST từ BCTC", "combo");

    /* P13 · Biên ròng/gộp so ngành */
    const mg = data.margins;
    section(mg && mg.net_latest != null, () => {
      const c13 = card("Biên lợi nhuận so ngành", "Biên ròng & gộp — WS-A theo ngành");
      root.appendChild(c13.card);
      const mgPeers = ((data.valuation || {}).peer_values || {}).net_margin || [];
      // Biên ròng: CAO hơn = thuận lợi hơn
      stripWithBar(c13.body, { self: mg.net_latest, median: mg.sector_net, peers: mgPeers, unit: "%" },
        { label: "Biên ròng", higherIsBetter: true, fmtVal: (v) => fmtPct(v) });
    }, "Biên lợi nhuận so ngành", "cần biên lợi nhuận từ BCTC");

    /* P15 · ROE/ROA lịch sử */
    const rr = data.roe_roa;
    section(rr && rr.roe && rr.roe.length, () => {
      const c15 = card("ROE / ROA lịch sử", "BCTC chuẩn hóa theo năm", "roe_roa");
      root.appendChild(c15.card);
      M.mpTrend(c15.body, rr.roe.map(x => ({ label: String(x.year), value: x.value })),
        { title: "ROE theo năm", metric: "ROE", unit: "%", higherIsBetter: true,
          notes: [{ t: `ROE gần nhất ${fmtPct(rr.roe_latest)}${rr.sector_roe != null ? ` · trung vị ngành ${fmtPct(rr.sector_roe)}` : ""}`, kind: rr.roe_latest >= 15 ? "ok" : "neu" }] });
    }, "ROE / ROA lịch sử", "cần ROE/ROA nhiều năm từ BCTC", "roe_roa");

    /* P16 · DuPont */
    const dp = data.dupont;
    section(dp && dp.length, () => {
      const c16 = card("Phân tích DuPont", "ROE ≈ biên ròng × vòng quay TS × hệ số nhân vốn");
      root.appendChild(c16.card);
      // Cột đòn bẩy giờ là HỆ SỐ NHÂN VỐN (Tổng TS/VCSH) — đúng đại lượng của
      // đẳng thức DuPont. Ghi rõ "≈" và lý do lệch: tử số là số cả năm, mẫu số
      // là số cuối kỳ, năm nào vốn chủ biến động mạnh thì tích lệch ROE thật.
      c16.body.innerHTML = `<table><thead><tr><th>Năm</th><th class="num">Biên ròng</th><th class="num">Vòng quay TS</th>
        <th class="num" title="Tổng tài sản / Vốn chủ sở hữu — càng cao càng dùng nhiều nợ">Hệ số nhân vốn</th>
        <th class="num">ROE</th></tr></thead>
        <tbody>${dp.map(r => `<tr><td>${r.year}</td><td class="num">${fmtPct(r.net_margin)}</td><td class="num">${r.asset_turnover != null ? fmtVN(r.asset_turnover, 2) : "—"}</td><td class="num" title="${r.debt_to_equity_pct != null ? "Nợ/VCSH " + fmtVN(r.debt_to_equity_pct, 1) + "%" : ""}">${r.leverage != null ? fmtVN(r.leverage, 2) + " lần" : "—"}</td><td class="num">${fmtPct(r.roe)}</td></tr>`).join("")}</tbody></table>
        <div class="disclaimer" style="margin-top:8px">Dấu ≈ vì lợi nhuận là số cả năm còn tài sản/vốn chủ là số cuối kỳ — năm nào vốn chủ biến động mạnh thì tích ba cột lệch so với ROE.</div>`;
    }, "Phân tích DuPont", "cần đủ biên ròng + vòng quay tài sản + đòn bẩy nhiều năm");

    /* P17 · Nợ/VCSH so ngành */
    const lv = data.leverage;
    section(lv && lv.d2e_latest != null, () => {
      const c17 = card("Đòn bẩy tài chính", "Nợ / Vốn chủ so ngành");
      root.appendChild(c17.card);
      const lvPeers = ((data.valuation || {}).peer_values || {}).debt_to_equity || [];
      // Nợ/VCSH: THẤP hơn = thuận lợi hơn
      stripWithBar(c17.body, { self: lv.d2e_latest, median: lv.sector_d2e, peers: lvPeers, unit: "lần" },
        { label: "Nợ/VCSH", higherIsBetter: false, fmtVal: (v) => fmtVN(v, 2) });
    }, "Đòn bẩy tài chính", "cần Nợ/Vốn chủ từ BCTC");

    /* P18 · Lưu chuyển tiền tệ — B17: Cơ bản = 3 dòng kể chuyện ✓/✗ + câu chốt;
       Chuyên sâu = waterfall nhãn tiếng Việt (Kinh doanh/Đầu tư/Vay-trả). */
    const cf = data.cashflow;
    section(cf && cf.cfo != null, () => {
      const c18 = card("Lưu chuyển tiền tệ", `Năm ${cf.year || ""} · dòng tiền vào/ra`);
      root.appendChild(c18.card);
      const u = " tỷ", fU = (v) => M._fmtUnit(v, u);
      const story = [
        { icon: cf.cfo >= 0 ? "✓" : "✗", kind: cf.cfo >= 0 ? "ok" : "bad",
          t: `Kinh doanh ${cf.cfo >= 0 ? "tạo ra" : "hao hụt"} ${fU(cf.cfo)}` },
        { icon: cf.cfi >= 0 ? "＋" : "－", kind: "neu",
          t: `${cf.cfi >= 0 ? "Thu về từ" : "Chi cho"} đầu tư ${fU(cf.cfi)}` },
        { icon: cf.cff >= 0 ? "＋" : "－", kind: "neu",
          t: `${cf.cff >= 0 ? "Vay ròng thêm" : "Trả bớt nợ/chia"} ${fU(cf.cff)}` },
      ];
      const storyBox = document.createElement("div"); storyBox.className = "cf-story";
      storyBox.innerHTML = story.map(s =>
        `<div class="cf-line ${s.kind}"><span class="cf-icon">${s.icon}</span> ${_esc(s.t)}</div>`).join("")
        + `<div class="cf-close">Tiền cuối kỳ <b>${fU(cf.end || 0)}</b>${cf.begin != null ? ` (${(cf.end || 0) >= (cf.begin || 0) ? "tăng" : "giảm"} so đầu kỳ ${fU(cf.begin)})` : ""}.</div>`;
      c18.body.appendChild(storyBox);
      // Chuyên sâu: waterfall nhãn tiếng Việt
      const adv = document.createElement("div"); adv.setAttribute("data-advanced", "");
      c18.body.appendChild(adv);
      M.svgWaterfall(adv, [
        { label: "Đầu kỳ", value: cf.begin || 0, kind: "start" },
        { label: "Kinh doanh", value: cf.cfo || 0, kind: "flow" },
        { label: "Đầu tư", value: cf.cfi || 0, kind: "flow" },
        { label: "Vay-trả", value: cf.cff || 0, kind: "flow" },
        { label: "Cuối kỳ", value: cf.end || 0, kind: "end" },
      ], { title: "Dòng tiền chi tiết (tỷ đồng)", unit: u });
    }, "Lưu chuyển tiền tệ", "cần báo cáo lưu chuyển tiền tệ (CFO/CFI/CFF)");

    /* P19 · Cổ tức */
    const dv = data.dividends;
    section(dv && (dv.payout || []).length, () => {
      const c19 = card("Cổ tức", `Tỷ suất ${fmtPct(dv.dividend_yield)} · payout/LN`, "dividends");
      root.appendChild(c19.card);
      M.mpTrend(c19.body, dv.payout.map(p => ({ label: String(p.year), value: p.value })),
        { title: "Payout ratio theo năm", metric: "Payout", unit: "%", higherIsBetter: true });
    }, "Cổ tức", "chưa có lịch sử chi trả cổ tức trong dữ liệu", "dividends");

    // áp lại tooltip thuật ngữ cho nội dung mới
    if (window.MPTerm) window.MPTerm.scan(root);
  };

  function card(title, src, anchorId) {
    const c = document.createElement("div"); c.className = "card stock-sec";
    if (anchorId) c.id = "an-" + anchorId;   // đích cuộn khi click trục radar
    c.innerHTML = `<h3 class="sec-h">${title}${src ? ` <span class="src">${src}</span>` : ""}</h3>`;
    const body = document.createElement("div"); c.appendChild(body);
    return { card: c, body };
  }

  /* B14 · "đủ chỗ, ghi rõ lý do" cấp CARD: section thiếu dữ liệu vẫn HIỆN
     (card xám + lý do) thay vì biến mất im lặng → người dùng đếm đủ bộ. */
  function missingCard(title, reason, anchorId) {
    const c = document.createElement("div");
    c.className = "card stock-sec missing-card";
    if (anchorId) c.id = "an-" + anchorId;
    c.innerHTML = `<h3 class="sec-h">${title}</h3>
      <div class="mc-body"><span class="mc-ic" aria-hidden="true">▤</span>
        <span>Chưa đủ dữ liệu để hiển thị${reason ? " — " + _esc(reason) : ""}.</span></div>`;
    return c;
  }
  /* render section: có dữ liệu → drawFn(); không → card xám nêu lý do. */
  function section(cond, drawFn, title, reason, anchorId) {
    if (cond) { try { drawFn(); return; } catch (e) { /* rơi xuống card xám */ } }
    if (_root) _root.appendChild(missingCard(title, reason, anchorId));
  }
  function fmtPct(v) { return v == null || !isFinite(v) ? "—" : (v >= 0 ? "" : "") + fmtVN(v, 1) + "%"; }
})();
