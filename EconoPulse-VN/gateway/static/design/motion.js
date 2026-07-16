/* ==========================================================================
   Market Pulse — Motion Engine  ·  "NHỊP ĐẬP THỊ TRƯỜNG"
   --------------------------------------------------------------------------
   9 primitive tái dùng, thuần JS, 0-CDN. Kỷ luật 60fps:
     · chỉ animate transform/opacity/background (không layout thrash)
     · IntersectionObserver — ngoài viewport không chạy
     · prefers-reduced-motion / pin yếu → tắt Tier nặng
     · mọi hiệu ứng skip được, không bao giờ chặn thao tác
   Chỉ dùng easing/duration trong tokens.css: --spring / --glide, 150/300/600/1200.
   Expose qua window.MP. Tự init khi DOMContentLoaded, an toàn nếu gọi lại.
   ========================================================================== */
(function () {
  "use strict";

  const REDUCED = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Ngân sách hiệu ứng nặng: pin yếu / ít nhân CPU → tắt aurora + particle.
  const LOW_POWER = (navigator.hardwareConcurrency || 4) <= 2 ||
    (navigator.deviceMemory || 4) <= 2;
  const HEAVY_OK = !REDUCED && !LOW_POWER;

  const EASE_SPRING = (t) => {           // xấp xỉ cubic-bezier(.34,1.56,.64,1)
    const c = 1.70158 * 1.2;
    return 1 + (c + 1) * Math.pow(t - 1, 3) + c * Math.pow(t - 1, 2);
  };
  const EASE_GLIDE = (t) => 1 - Math.pow(1 - t, 3);   // ~cubic-bezier(.22,1,.36,1)

  // rAF-based timer honoring reduced-motion (kết thúc tức thì nếu tắt motion).
  function animate(dur, ease, onFrame, onDone) {
    if (REDUCED) { onFrame(1); onDone && onDone(); return; }
    const start = performance.now();
    function frame(now) {
      const t = Math.min(1, (now - start) / dur);
      onFrame(ease ? ease(t) : t);
      if (t < 1) requestAnimationFrame(frame);
      else onDone && onDone();
    }
    requestAnimationFrame(frame);
  }

  /* ---------------------------------------------------------------------- *
   * 1. countUp — mọi KPI đếm cuộn tới giá trị, 900ms, easing giảm dần.
   *    Đọc số đích từ textContent (giữ định dạng: dấu %, +, phẩy, đơn vị).
   * ---------------------------------------------------------------------- */
  function parseNum(s) {
    const m = String(s).replace(/ /g, " ")
      .match(/-?[\d.,]+/);
    if (!m) return null;
    // Chuẩn hóa: bỏ phân tách nghìn kiểu VN (dấu chấm) khi có phẩy thập phân.
    let raw = m[0];
    const hasComma = raw.includes(","), hasDot = raw.includes(".");
    if (hasComma && hasDot) raw = raw.replace(/\./g, "").replace(",", ".");
    else if (hasComma) raw = raw.replace(",", ".");
    const v = parseFloat(raw);
    return isNaN(v) ? null : { value: v, match: m[0], index: m.index };
  }

  function countUp(el, opts) {
    if (!el || el.__mpCounted) return;
    const target = parseNum(el.textContent);
    if (!target) return;
    el.__mpCounted = true;
    const o = opts || {};
    const dur = o.duration || 900;
    const decimals = (target.match.split(/[.,]/)[1] || "").length;
    const prefix = el.textContent.slice(0, target.index);
    const suffix = el.textContent.slice(target.index + target.match.length);
    const from = 0, to = target.value;
    const fmt = (v) => {
      const s = decimals > 0 ? v.toFixed(decimals) : Math.round(v).toLocaleString("vi-VN");
      return prefix + (decimals > 0 ? s.replace(".", ",") : s) + suffix;
    };
    animate(dur, EASE_GLIDE,
      (t) => { el.textContent = fmt(from + (to - from) * t); },
      () => { el.textContent = fmt(to); el.classList.add("mp-count-pop");
              setTimeout(() => el.classList.remove("mp-count-pop"), 600); });
  }

  /* ---------------------------------------------------------------------- *
   * 2. flashDelta — giá đổi → nền cell lóe xanh/đỏ rồi phai 600ms (Bloomberg).
   * ---------------------------------------------------------------------- */
  function flashDelta(el, dir) {
    if (!el || REDUCED) return;
    const cls = dir >= 0 ? "mp-flash-up" : "mp-flash-down";
    el.classList.remove("mp-flash-up", "mp-flash-down");
    void el.offsetWidth;               // reflow để restart animation
    el.classList.add(cls);
    setTimeout(() => el.classList.remove(cls), 600);
  }

  /* ---------------------------------------------------------------------- *
   * 3. cascade — card vào bằng blur-rise, stagger 45ms theo thứ tự đọc.
   *    Dùng IntersectionObserver: chỉ phát khi phần tử vào viewport.
   * ---------------------------------------------------------------------- */
  const _io = ("IntersectionObserver" in window) ? new IntersectionObserver((entries) => {
    entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add("mp-in"); _io.unobserve(e.target); }
    });
  }, { threshold: 0.08 }) : null;

  function cascade(container, sel) {
    const root = container || document;
    const items = root.querySelectorAll(sel || ".card, .kpi");
    items.forEach((el, i) => {
      if (el.__mpCascaded) return;
      el.__mpCascaded = true;
      el.classList.add("mp-cascade");
      el.style.setProperty("--mp-delay", Math.min(i * 45, 400) + "ms");
      if (_io && !REDUCED) _io.observe(el);
      else el.classList.add("mp-in");
    });
  }

  /* ---------------------------------------------------------------------- *
   * 4. ecgLine — đường điện tâm đồ chạy ngang topbar; bpm gắn trạng thái phiên.
   *    beat() bắn 1 nhịp giật mạnh (khi có cảnh báo radar mới).
   * ---------------------------------------------------------------------- */
  function ecgLine(canvas, opts) {
    if (!canvas || REDUCED) return { setBpm() {}, beat() {} };
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let W, H;
    function resize() {
      W = canvas.clientWidth; H = canvas.clientHeight;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize();
    window.addEventListener("resize", resize);

    let bpm = (opts && opts.bpm) || 60;
    let x = 0, spike = 0, running = true;
    const speed = 1.6;                 // px/frame
    const mid = () => H * 0.5;
    const buf = [];                    // lưu vệt để vẽ đuôi mờ

    // Sinh y cho vị trí x theo hình sóng PQRST đơn giản, chu kỳ theo bpm.
    function ecgY(phase) {
      // phase 0..1 trong 1 nhịp
      const p = phase;
      if (p < 0.10) return -Math.sin(p / 0.10 * Math.PI) * 2;      // P
      if (p < 0.16) return 0;
      if (p < 0.19) return 6;                                       // Q
      if (p < 0.23) return -22 - spike * 16;                        // R (đỉnh)
      if (p < 0.27) return 10;                                      // S
      if (p < 0.42) return -Math.sin((p - 0.27) / 0.15 * Math.PI) * 6; // T
      return 0;
    }

    let phase = 0;
    function loop() {
      if (!running) return;
      const cyclesPerSec = bpm / 60;
      phase += cyclesPerSec / 60;
      if (phase >= 1) { phase -= 1; if (spike > 0) spike = Math.max(0, spike - 0.5); }

      x += speed;
      if (x > W) { x = 0; buf.length = 0; }
      buf.push({ x, y: mid() + ecgY(phase) });
      if (buf.length > W / speed + 4) buf.shift();

      ctx.clearRect(0, 0, W, H);
      ctx.lineWidth = 1.8;
      ctx.lineJoin = "round";
      const grad = ctx.createLinearGradient(0, 0, W, 0);
      grad.addColorStop(0, "rgba(34,227,156,0)");
      grad.addColorStop(0.5, "rgba(34,227,156,.6)");
      grad.addColorStop(1, "rgba(79,140,255,.9)");
      ctx.strokeStyle = grad;
      ctx.shadowColor = "rgba(34,227,156,.6)"; ctx.shadowBlur = 6;
      ctx.beginPath();
      buf.forEach((pt, i) => i ? ctx.lineTo(pt.x, pt.y) : ctx.moveTo(pt.x, pt.y));
      ctx.stroke();
      // chấm sáng đầu sóng
      const head = buf[buf.length - 1];
      if (head) {
        ctx.shadowBlur = 12; ctx.fillStyle = "#22E39C";
        ctx.beginPath(); ctx.arc(head.x, head.y, 2.4, 0, Math.PI * 2); ctx.fill();
      }
      ctx.shadowBlur = 0;
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);

    return {
      setBpm(v) { bpm = Math.max(20, Math.min(180, v)); },
      beat() { spike = 1; },           // 1 nhịp giật mạnh
      stop() { running = false; },
    };
  }

  /* ---------------------------------------------------------------------- *
   * 5. typewriter — text AI gõ dần, con trỏ nhấp nháy, ~2 ký tự/frame.
   *    Bỏ qua (hiện full) khi user cuộn hoặc reduced-motion.
   * ---------------------------------------------------------------------- */
  function typewriter(el, text, opts) {
    if (!el) return Promise.resolve();
    const full = (text != null) ? String(text) : el.textContent;
    if (REDUCED) { el.textContent = full; return Promise.resolve(); }
    const o = opts || {};
    const cps = o.charsPerFrame || 2;
    el.textContent = "";
    el.classList.add("mp-caret");
    let i = 0, skipped = false;
    const skip = () => { skipped = true; };
    window.addEventListener("scroll", skip, { once: true, passive: true });
    return new Promise((resolve) => {
      function frame() {
        if (skipped) { el.textContent = full; done(); return; }
        i += cps;
        el.textContent = full.slice(0, i);
        if (i < full.length) requestAnimationFrame(frame);
        else done();
      }
      function done() {
        window.removeEventListener("scroll", skip);
        setTimeout(() => el.classList.remove("mp-caret"), 600);
        resolve();
      }
      requestAnimationFrame(frame);
    });
  }

  /* ---------------------------------------------------------------------- *
   * 6. flipZoom — FLIP: phóng 1 phần tử thành trang đích (morph transform).
   *    Nếu trình duyệt hỗ trợ View Transitions, dùng nó; nếu không, tự morph.
   * ---------------------------------------------------------------------- */
  function flipZoom(fromEl, navigate) {
    if (REDUCED || !fromEl) { navigate && navigate(); return; }
    const r = fromEl.getBoundingClientRect();
    const ghost = fromEl.cloneNode(true);
    Object.assign(ghost.style, {
      position: "fixed", left: r.left + "px", top: r.top + "px",
      width: r.width + "px", height: r.height + "px", margin: 0, zIndex: 9999,
      transition: "transform var(--dur-3) var(--glide), opacity var(--dur-3) var(--glide)",
      transformOrigin: "center center", pointerEvents: "none",
    });
    document.body.appendChild(ghost);
    const sx = window.innerWidth / r.width, sy = window.innerHeight / r.height;
    const scale = Math.max(sx, sy) * 1.05;
    requestAnimationFrame(() => {
      ghost.style.transform =
        `translate(${window.innerWidth / 2 - (r.left + r.width / 2)}px,` +
        `${window.innerHeight / 2 - (r.top + r.height / 2)}px) scale(${scale})`;
      ghost.style.opacity = "0";
    });
    setTimeout(() => { ghost.remove(); navigate && navigate(); }, 560);
  }

  /* ---------------------------------------------------------------------- *
   * 7. radarSweep — kim quét tròn + vòng sóng lan cho card Radar.
   * ---------------------------------------------------------------------- */
  function radarSweep(el) {
    if (!el || REDUCED || el.__mpSweep) return;
    el.__mpSweep = true;
    if (getComputedStyle(el).position === "static") el.style.position = "relative";
    const sweep = document.createElement("div");
    sweep.className = "mp-radar-sweep";
    el.appendChild(sweep);
  }

  /* ---------------------------------------------------------------------- *
   * 8. aurora — nền ambient: 3 blob gradient cực mờ trôi chậm + hạt sao,
   *    parallax theo chuột 4px. Tắt khi reduced-motion / pin yếu.
   * ---------------------------------------------------------------------- */
  function aurora() {
    if (!HEAVY_OK || document.getElementById("mp-aurora")) return;
    const canvas = document.createElement("canvas");
    canvas.id = "mp-aurora";
    document.body.appendChild(canvas);
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    let W, H;
    function resize() {
      W = window.innerWidth; H = window.innerHeight;
      canvas.width = W * dpr; canvas.height = H * dpr;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
    resize(); window.addEventListener("resize", resize);

    const blobs = [
      { hue: "34,227,156", r: 420 }, { hue: "79,140,255", r: 480 },
      { hue: "155,123,255", r: 400 },
    ].map((b, i) => ({ ...b, ph: i * 2.1 }));
    // Ngân sách hạt cứng: 60 sao.
    const stars = Array.from({ length: 60 }, (_, i) => ({
      x: (i * 97 % 100) / 100, y: (i * 53 % 100) / 100,
      r: 0.6 + (i % 3) * 0.5, tw: (i % 7) / 7,
    }));
    let mx = 0, my = 0, t = 0;
    window.addEventListener("mousemove", (e) => {
      mx = (e.clientX / W - 0.5); my = (e.clientY / H - 0.5);
    }, { passive: true });

    let raf;
    function loop() {
      t += 1 / 60;
      ctx.clearRect(0, 0, W, H);
      // blob trôi 40s/vòng
      blobs.forEach((b) => {
        const a = (t / 40) * Math.PI * 2 + b.ph;
        const cx = W * (0.5 + 0.32 * Math.cos(a)) + mx * 4;
        const cy = H * (0.5 + 0.30 * Math.sin(a * 0.8)) + my * 4;
        const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, b.r);
        g.addColorStop(0, `rgba(${b.hue},.05)`);
        g.addColorStop(1, `rgba(${b.hue},0)`);
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      });
      // sao nhấp nháy
      stars.forEach((s) => {
        const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * 0.8 + s.tw * 6.28));
        ctx.fillStyle = `rgba(180,200,255,${0.25 * tw})`;
        ctx.beginPath();
        ctx.arc(s.x * W + mx * 4, s.y * H + my * 4, s.r, 0, Math.PI * 2);
        ctx.fill();
      });
      raf = requestAnimationFrame(loop);
    }
    loop();
    // Tạm dừng khi tab ẩn để tiết kiệm pin.
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) cancelAnimationFrame(raf);
      else loop();
    });
  }

  /* ---------------------------------------------------------------------- *
   * 9. stampLabel — nhãn kiểm chứng đóng dấu (rơi + rung + vệt mực).
   * ---------------------------------------------------------------------- */
  function stampLabel(el) {
    if (!el || REDUCED || el.__mpStamped) return;
    el.__mpStamped = true;
    el.classList.add("mp-stamp");
    setTimeout(() => el.classList.remove("mp-stamp"), 600);
  }

  /* ---------------------------------------------------------------------- *
   * Auto-init — quét DOM sẵn có, không cần sửa markup từng trang.
   * ---------------------------------------------------------------------- */
  let ecg = null;

  function mountEcg() {
    const topbar = document.querySelector(".topbar");
    if (!topbar || topbar.querySelector(".mp-ecg-wrap")) return;
    const wrap = document.createElement("div");
    wrap.className = "mp-ecg-wrap";
    const c = document.createElement("canvas");
    c.className = "mp-ecg";
    wrap.appendChild(c);
    topbar.appendChild(wrap);
    // bpm theo trạng thái phiên: mở = 78, ngoài giờ = 46.
    const open = document.querySelector("#tb-mkt.open");
    ecg = ecgLine(c, { bpm: open ? 78 : 46 });
    // Theo dõi đổi trạng thái phiên (common.js đổi class mỗi giây).
    const mkt = document.querySelector("#tb-mkt");
    if (mkt && ecg) {
      new MutationObserver(() => {
        ecg.setBpm(mkt.classList.contains("open") ? 78 : 46);
      }).observe(mkt, { attributes: true, attributeFilter: ["class"] });
    }
  }

  function autoCount() {
    // KPI value + mọi phần tử gắn data-countup.
    document.querySelectorAll(".kpi .value, [data-countup]").forEach((el) => {
      if (!_io) { countUp(el); return; }
      const once = new IntersectionObserver((es, ob) => {
        es.forEach((e) => { if (e.isIntersecting) { countUp(el); ob.disconnect(); } });
      }, { threshold: 0.3 });
      once.observe(el);
    });
  }

  /* ---------------------------------------------------------------------- *
   * autoEnhance — theo dõi các container render động (kết quả AI, claims,
   * heatmap, radar, KPI) và áp hiệu ứng đúng lúc nội dung xuất hiện.
   * Không sửa JS từng trang — mọi thứ tự bám vào class hook sẵn có.
   * ---------------------------------------------------------------------- */
  function enhanceNode(node) {
    if (!(node instanceof HTMLElement)) return;

    // KPI mới → count-up khi vào viewport
    node.querySelectorAll?.(".kpi .value, [data-countup]").forEach((el) => {
      if (el.__mpCounted) return;
      if (!_io) { countUp(el); return; }
      const once = new IntersectionObserver((es, ob) => {
        es.forEach((e) => { if (e.isIntersecting) { countUp(el); ob.disconnect(); } });
      }, { threshold: 0.3 });
      once.observe(el);
    });

    // Card / claim / signal mới → cascade blur-rise
    cascade(node, ".card, .kpi, .claim-row, .radar-row, .step, .pillar");

    // Nhãn Soi Tin → đóng dấu (stamp)
    node.querySelectorAll?.(".claim-label, .verdict-card").forEach(stampLabel);

    // Regime badge (Uptrend/Downtrend) → gắn nhịp thở đúng chiều
    node.querySelectorAll?.(".regime-badge").forEach((b) => {
      const t = b.textContent.toLowerCase();
      if (/uptrend|phục hồi|tăng/.test(t)) b.classList.add("up");
      else if (/downtrend|suy yếu|giảm/.test(t)) b.classList.add("down");
    });

    // Radar có tín hiệu mới → 1 nhịp ECG giật
    if (node.querySelector?.(".radar-row, .claim-row") ||
        node.matches?.(".radar-row, .claim-row")) {
      window.MP && window.MP.beat && window.MP.beat();
    }

    // Text tổng hợp AI → typewriter (chỉ phần tử đánh dấu data-typewriter)
    node.querySelectorAll?.("[data-typewriter]").forEach((el) => {
      if (!el.__mpTyped) { el.__mpTyped = true; typewriter(el); }
    });
  }

  function watchDynamic() {
    const targets = [
      "#overview-result", "#overview-steps", "#heatmap", "#radar-body",
      "#soitin-result", "#portfolio-result", "#market-kpis", "#health-kpis",
      "#copilot-result", "#macro-result", "#quantum-result",
    ];
    const seen = new WeakSet();
    const obs = new MutationObserver((muts) => {
      muts.forEach((m) => m.addedNodes.forEach((n) => {
        if (seen.has(n)) return;
        seen.add(n);
        enhanceNode(n);
      }));
    });
    targets.forEach((sel) => {
      const el = document.querySelector(sel);
      if (el) obs.observe(el, { childList: true, subtree: true });
    });
  }

  function init() {
    aurora();
    mountEcg();
    cascade(document);
    autoCount();
    document.querySelectorAll("#radar-card, [data-radar-sweep]").forEach(radarSweep);
    watchDynamic();
  }

  // Public API
  window.MP = {
    countUp, flashDelta, cascade, ecgLine, typewriter,
    flipZoom, radarSweep, aurora, stampLabel,
    get ecg() { return ecg; },
    beat() { ecg && ecg.beat(); },
    reduced: REDUCED, heavyOk: HEAVY_OK,
    // cho phép gọi lại sau khi render nội dung động
    refresh() { cascade(document); autoCount(); },
  };

  if (document.readyState === "loading")
    document.addEventListener("DOMContentLoaded", init);
  else init();
})();
