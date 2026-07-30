/* Market Pulse — shell.js: theme sáng/tối + ⌘K command palette.
   Nạp trong base.html SAU common.js. Theme đã được set pre-paint bằng inline
   script ở <head> (tránh FOUC) — ở đây chỉ gắn nút toggle + palette. */

/* ========================================================================
   1) Theme toggle — localStorage "mp_theme" (dark mặc định)
   ======================================================================== */
(function initTheme() {
  const btn = document.getElementById("theme-toggle");
  if (!btn) return;
  const sync = () => {
    const light = document.documentElement.dataset.theme === "light";
    // Ảnh 3: nút dùng icon SVG (không emoji) → đổi #id trong <use>, KHÔNG ghi
    // textContent (sẽ xoá mất thẻ <svg> bên trong nút).
    const use = btn.querySelector("use");
    if (use) use.setAttribute("href", `/static/design/icons.svg#${light ? "ic-sun" : "ic-moon"}`);
    else btn.textContent = light ? "☀" : "☾";
    btn.title = light ? "Chuyển giao diện tối" : "Chuyển giao diện sáng";
  };
  sync();
  btn.onclick = () => {
    const cur = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    document.documentElement.dataset.theme = cur;
    localStorage.setItem("mp_theme", cur);
    sync();
    // chart đọc màu lúc khởi tạo → thông báo cho trang tự vẽ lại nếu muốn
    window.dispatchEvent(new CustomEvent("mp:theme", { detail: cur }));
  };
})();

/* ========================================================================
   2) ⌘K / Ctrl+K command palette — trang + mã cổ phiếu + hành động
   ======================================================================== */
(function initCmdk() {
  const PAGES = [
    ["👋", "Bắt đầu", "/bat-dau"],
    ["🌐", "Thị trường", "/"],
    ["📉", "Sức khỏe DN", "/market.html"],
    ["🧮", "Bộ lọc", "/bo-loc"],
    ["💼", "Danh mục", "/portfolio.html"],
    ["⭐", "Theo dõi", "/watchlist.html"],
    ["🧭", "Copilot", "/copilot.html"],
    ["🔍", "Soi Tin", "/soitin.html"],
    ["⚖️", "So sánh", "/so-sanh"],
    ["📊", "Bảng giá", "/banggia.html"],
    ["🕷️", "Dữ liệu Crawl", "/data.html"],
    ["🔬", "Quantum Lab", "/quantum-lab"],
    ["📈", "Vĩ mô", "/macro.html"],
    ["📐", "Phương pháp", "/methodology.html"],
    ["📖", "Thuật ngữ", "/kien-thuc"],
    ["🧩", "Hệ sinh thái", "/apps.html"],
  ];
  const ACTIONS = [
    ["⟳", "Cập nhật giá thị trường (P6)", () =>
      fetch("/api/market/refresh_prices", { method: "POST" }).then(() =>
        alert("Đã bắt đầu cập nhật giá — theo dõi ở trang Tổng quan."))],
    ["▶", "Chạy phân tích Tổng quan", () => (location.href = "/")],
  ];

  let stocks = null;      // nạp lười từ health_scores.json
  let items = [];         // danh sách đang hiển thị [{ic,label,sub,run}]
  let sel = 0;

  // ---- dựng DOM 1 lần
  const dlg = document.createElement("div");
  dlg.id = "cmdk";
  dlg.innerHTML =
    '<div class="cmdk-box" role="dialog" aria-label="Tìm nhanh">' +
    '<input id="cmdk-input" placeholder="Gõ mã cổ phiếu, tên trang, hành động…" autocomplete="off">' +
    '<div id="cmdk-list"></div>' +
    '<div class="cmdk-foot">↑↓ chọn · Enter mở · Esc đóng</div></div>';
  dlg.style.display = "none";
  document.body.appendChild(dlg);
  const input = dlg.querySelector("#cmdk-input");
  const list = dlg.querySelector("#cmdk-list");

  function open() {
    dlg.style.display = "";
    input.value = "";
    render("");
    setTimeout(() => input.focus(), 0);
    if (!stocks) {
      getData("health_scores").then((d) => {
        stocks = (d.companies || []).map((c) => ({
          sym: c.symbol, name: c.name || "", zone: c.z_zone || "",
        }));
        if (dlg.style.display !== "none") render(input.value);
      }).catch(() => { stocks = []; });
    }
  }
  function close() { dlg.style.display = "none"; }

  function render(q) {
    q = q.trim().toLowerCase();
    items = [];
    for (const [ic, label, href] of PAGES) {
      if (!q || label.toLowerCase().includes(q))
        items.push({ ic, label, sub: "Trang", run: () => (location.href = href) });
    }
    for (const [ic, label, fn] of ACTIONS) {
      if (!q || label.toLowerCase().includes(q))
        items.push({ ic, label, sub: "Hành động", run: fn });
    }
    if (stocks && q) {
      const qs = q.toUpperCase();
      stocks
        .filter((s) => s.sym.startsWith(qs) || s.name.toLowerCase().includes(q))
        .slice(0, 8)
        .forEach((s) => items.push({
          ic: "🏢", label: s.sym, sub: s.name,
          run: () => (location.href = "/co-phieu/" + s.sym),
        }));
    }
    items = items.slice(0, 12);
    sel = 0;
    list.innerHTML = items.map((it, i) =>
      `<div class="cmdk-item${i === sel ? " sel" : ""}" data-i="${i}">
        <span class="ci">${it.ic}</span><span class="cl">${it.label}</span>
        <span class="cs">${it.sub}</span></div>`).join("") ||
      '<div class="cmdk-empty">Không có kết quả</div>';
  }

  function move(d) {
    if (!items.length) return;
    sel = (sel + d + items.length) % items.length;
    list.querySelectorAll(".cmdk-item").forEach((el, i) =>
      el.classList.toggle("sel", i === sel));
    const el = list.querySelector(".cmdk-item.sel");
    if (el) el.scrollIntoView({ block: "nearest" });
  }

  input.addEventListener("input", () => render(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
    else if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
    else if (e.key === "Enter" && items[sel]) { close(); items[sel].run(); }
    else if (e.key === "Escape") close();
  });
  list.addEventListener("click", (e) => {
    const el = e.target.closest(".cmdk-item");
    if (el) { close(); items[+el.dataset.i].run(); }
  });
  dlg.addEventListener("click", (e) => { if (e.target === dlg) close(); });

  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      dlg.style.display === "none" ? open() : close();
    }
  });
  const trigger = document.getElementById("tb-search");
  if (trigger) trigger.onclick = open;
})();
