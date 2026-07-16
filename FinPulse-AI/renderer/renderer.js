// ----------------------------- helpers --------------------------------------
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

function toast(msg, ms = 2200) {
  const t = $('#toast');
  t.textContent = msg;
  t.classList.remove('hidden');
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add('hidden'), ms);
}

// ----------------------------- markdown an toàn -> html ---------------------------
function md(src) {
  let s = String(src || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  s = s.replace(/^### (.*)$/gm, '<h3>$1</h3>')
    .replace(/^## (.*)$/gm, '<h2>$1</h2>')
    .replace(/^# (.*)$/gm, '<h1>$1</h1>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/`(.+?)`/g, '<code>$1</code>');
  // lists
  s = s.replace(/(?:^|\n)((?:\s*[-*] .*(?:\n|$))+)/g, (m, blk) => {
    const items = blk.trim().split('\n').map((l) => '<li>' + l.replace(/^\s*[-*]\s/, '') + '</li>').join('');
    return '\n<ul>' + items + '</ul>';
  });
  s = s.replace(/(?:^|\n)((?:\s*\d+\. .*(?:\n|$))+)/g, (m, blk) => {
    const items = blk.trim().split('\n').map((l) => '<li>' + l.replace(/^\s*\d+\.\s/, '') + '</li>').join('');
    return '\n<ol>' + items + '</ol>';
  });
  return s.split(/\n{2,}/).map((p) => /<(h\d|ul|ol)/.test(p) ? p : '<p>' + p.replace(/\n/g, '<br>') + '</p>').join('');
}

// ----------------------------- tabs -----------------------------------------
$$('.tab').forEach((tab) => tab.addEventListener('click', () => {
  $$('.tab').forEach((t) => t.classList.remove('active'));
  tab.classList.add('active');
  $$('.view').forEach((v) => v.classList.remove('active'));
  $('#view-' + tab.dataset.view).classList.add('active');
}));

// ----------------------------- config ---------------------------------------
let config = { mode: 'api', provider: 'gemini', apiKey: '', model: 'gemini-2.0-flash' };
function badgeText() {
  if (config.mode === 'web-webview') return 'Webview';
  if (config.mode === 'web-hiddenwin') return 'Window ẩn';
  if (config.mode === 'web-pyqt6') return 'PyQt6 Bridge';
  if (config.mode === 'web-auto') return 'Web-bridge';
  if (config.mode === 'web') return 'Web copy/paste';
  return config.provider === 'anthropic' ? 'Claude API' : 'Gemini API';
}

// Unified AI call: routes 'web-...' modes through their respective automation bridges,
// everything else straight to the main process (API or manual web mode).
async function aiInvoke(task, payload) {
  if (config.mode && config.mode.startsWith('web-')) {
    const built = await window.api.aiRun(task, payload); // {ok, mode:'web-auto', prompt}
    if (!built.ok) return built;
    // Mở chat MỚI khi bắt đầu flow mới (branches từ gốc) hoặc phân tích bài báo;
    // đào sâu nhánh / phân tích cuối -> GÕ TIẾP cùng phiên (liền mạch + nhanh).
    const p = payload.path || [];
    const newChat = task === 'article' || (task === 'branches' && p.length === 0);
    
    let r;
    if (config.mode === 'web-webview') {
      try {
        const text = await window.webBridge.send(built.prompt);
        r = { ok: true, text: text };
      } catch (err) {
        r = { ok: false, error: 'Webview Error: ' + err.message };
      }
    } else if (config.mode === 'web-hiddenwin') {
      r = await window.api.aiwinSend(built.prompt);
    } else {
      r = await window.api.qtbridgeAsk(built.prompt, newChat);
      if (!r.ok) {
        r.error = 'Gemini Bridge: ' + (r.error || '?') +
          ' — vào tab "AI Web" bấm Khởi động bridge và đăng nhập Gemini trước.';
      }
    }
    
    if (!r.ok) return r;
    const text = r.text || '';
    return task === 'branches'
      ? { ok: true, mode: 'api', branches: parseBranchesClient(text), text }
      : { ok: true, mode: 'api', text };
  }
  return window.api.aiRun(task, payload);
}

function parseBranchesClient(text) {
  const clean = String(text || '').replace(/```json/gi, '').replace(/```/g, '').trim();
  try {
    const m = clean.match(/\{[\s\S]*\}/);
    const obj = JSON.parse(m ? m[0] : clean);
    if (Array.isArray(obj.branches)) return obj.branches.map((b) => String(b).trim()).filter(Boolean).slice(0, 10);
  } catch (_) {}
  const quoted = clean.match(/"([^"]{3,})"/g);
  if (quoted && quoted.length >= 3) {
    return quoted.map((q) => q.replace(/"/g, '').trim())
      .filter((s) => s && s.toLowerCase() !== 'branches').slice(0, 10);
  }
  return clean.split('\n')
    .map((l) => l.replace(/^[\s\-*\d.)\]\[{}",]+/, '').replace(/[",]+$/, '').trim())
    .filter((s) => s && s.toLowerCase() !== 'branches' && !s.startsWith('{'))
    .slice(0, 10);
}
async function loadConfig() {
  config = await window.api.getConfig();
  $('#modeBadge').textContent = badgeText();
}
$('#settingsBtn').addEventListener('click', () => {
  $('#cfgMode').value = config.mode;
  $('#cfgProvider').value = config.provider || 'gemini';
  $('#cfgKey').value = config.apiKey || '';
  $('#cfgModel').value = config.model || 'gemini-2.0-flash';
  $('#settingsPanel').classList.toggle('open');
});
$('#closeSettingsBtn').addEventListener('click', () => {
  $('#settingsPanel').classList.remove('open');
});
$('#saveCfgBtn').addEventListener('click', async () => {
  config = await window.api.saveConfig({
    mode: $('#cfgMode').value,
    provider: $('#cfgProvider').value,
    apiKey: $('#cfgKey').value.trim(),
    model: $('#cfgModel').value.trim() || ($('#cfgProvider').value === 'anthropic' ? 'claude-sonnet-4-6' : 'gemini-2.0-flash')
  });
  $('#modeBadge').textContent = badgeText();
  $('#settingsPanel').classList.remove('open');
  toast('Đã lưu cấu hình');
});

// ----------------------------- news -----------------------------------------
let currentCat = null;
async function initCategories() {
  const cats = await window.api.getCategories();
  const list = $('#catList');
  list.innerHTML = '';
  cats.forEach((c, i) => {
    const el = document.createElement('div');
    el.className = 'cat-item' + (i === 0 ? ' active' : '');
    el.innerHTML = `<span class="ic">${c.icon}</span><span>${c.label}</span>`;
    el.addEventListener('click', () => {
      $$('.cat-item').forEach((x) => x.classList.remove('active'));
      el.classList.add('active');
      loadCategory(c);
    });
    list.appendChild(el);
  });
  if (cats[0]) loadCategory(cats[0]);
}

async function loadCategory(cat) {
  currentCat = cat;
  $('#catTitle').textContent = cat.label;
  $('#feedErrors').textContent = '';
  const grid = $('#newsGrid');
  grid.innerHTML = '<div class="empty-hint"><span class="loading"></span> Đang tải tin...</div>';
  const { items, errors } = await window.api.fetchCategory(cat.id);
  if (errors && errors.length) $('#feedErrors').textContent = '⚠ ' + errors.length + ' feed lỗi (đã bỏ qua)';
  if (!items.length) { grid.innerHTML = '<div class="empty-hint">Không tải được tin. Kiểm tra mạng rồi Refresh.</div>'; return; }
  grid.innerHTML = '';
  items.forEach((it) => grid.appendChild(newsCard(it)));
}

function newsCard(it) {
  const el = document.createElement('div');
  el.className = 'news-card';
  const dt = it.date ? new Date(it.date).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' }) : '';
  el.innerHTML = `<span class="hint">chuột phải ⟶</span>
    <h4>${escapeHtml(it.title)}</h4>
    <div class="snippet">${escapeHtml(it.snippet)}</div>
    <div class="meta"><span class="src">${escapeHtml(it.source)}</span><span>${dt}</span></div>`;
  el.addEventListener('contextmenu', (e) => { e.preventDefault(); showCtx(e, it); });
  return el;
}
function escapeHtml(s) { return String(s || '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

$('#refreshBtn').addEventListener('click', () => currentCat && loadCategory(currentCat));

// ----------------------------- context menu ---------------------------------
let ctxArticle = null;
function showCtx(e, article) {
  ctxArticle = article;
  const m = $('#ctxMenu');
  m.classList.remove('hidden');
  const x = Math.min(e.clientX, window.innerWidth - 220);
  const y = Math.min(e.clientY, window.innerHeight - 140);
  m.style.left = x + 'px';
  m.style.top = y + 'px';
}
document.addEventListener('click', () => $('#ctxMenu').classList.add('hidden'));
$('#ctxMenu').addEventListener('click', (e) => {
  const act = e.target.dataset.act;
  if (!act || !ctxArticle) return;
  if (act === 'open') { if (ctxArticle.link) window.open(ctxArticle.link, '_blank'); }
  else if (act === 'analyze') analyzeArticle(ctxArticle);
  else if (act === 'flow') sendArticleToFlow(ctxArticle);
});

// ----------------------------- AI: article analysis -------------------------
async function analyzeArticle(article) {
  openModal('analysisModal');
  $('#analysisTitle').textContent = 'AI phân tích';
  $('#analysisBody').innerHTML = '<div class="empty-hint"><span class="loading"></span> Đang phân tích...</div>';
  const res = await aiInvoke('article', { article });
  if (!res.ok) { $('#analysisBody').innerHTML = `<p style="color:var(--danger)">${escapeHtml(res.error)}</p>`; return; }
  if (res.mode === 'web') {
    closeModals();
    openWebMode(res.prompt, (answer) => {
      openModal('analysisModal');
      $('#analysisBody').innerHTML = '<div class="ai-output">' + md(answer) + '</div>';
    });
  } else {
    $('#analysisBody').innerHTML = '<div class="ai-output">' + md(res.text) + '</div>';
  }
}

function sendArticleToFlow(article) {
  $$('.tab').forEach((t) => t.classList.remove('active'));
  document.querySelector('.tab[data-view="flow"]').classList.add('active');
  $$('.view').forEach((v) => v.classList.remove('active'));
  $('#view-flow').classList.add('active');
  $('#rootInput').value = article.title.slice(0, 90);
  startFlow();
}

// ============================================================
// CÂY PHÂN NHÁNH — mỗi nhánh chẻ thêm 10 nhánh con
// Nhánh cũ KHÔNG BAO GIỜ biến mất khi chọn nhánh mới
// ============================================================
let rootTopic = '';
let treeRoot = null;  // node gốc của cây
let nodeIdCtr = 0;
let focusNode = null;  // node đang được focus (để Submit)

const SVGNS = 'http://www.w3.org/2000/svg';
const NODE_ICONS = ['◆', '✦', '▲', '⬡', '✧', '◈', '⬢', '★', '❖', '◇'];
const STAGE_PAD = 420;   // khoảng đệm xung quanh cây (tăng lên để nhãn không bị cắt)
const ROOT_R = 260;   // bán kính lấy nánh cấp 1 từ gốc
const SUB_R = 310;   // bán kính cố định cho mọi cấp con tiếp theo
const SUB_HALF = 85;    // góc ≥ ± 85° => 170° tổng => 10 node có ~105px giữa

// ---- Tạo node mới ----
function makeNode(label, parent) {
  return {
    id: nodeIdCtr++,
    label,
    parent,
    children: [],
    expanded: false,
    loading: false,
    x: 0, y: 0
  };
}

// ---- Lấy đường dẫn từ gốc đến node ----
function pathFromRoot(node) {
  const p = [];
  let cur = node;
  while (cur) { p.unshift(cur.label); cur = cur.parent; }
  return p; // [label gốc, ..., label node]
}

// ---- Duyệt toàn bộ cây ----
function walkTree(node, fn) {
  fn(node);
  node.children.forEach(c => walkTree(c, fn));
}

// node có nằm trên đường từ gốc tới `of` không (kể cả chính `of`)
function isAncestor(node, of) {
  let c = of;
  while (c) { if (c === node) return true; c = c.parent; }
  return false;
}

// ---- Gắn sự kiện nút ----
$('#startFlowBtn').addEventListener('click', startFlow);
$('#rootInput').addEventListener('keydown', (e) => { if (e.key === 'Enter') startFlow(); });
// Nút "Về gốc" — cuộn viewport về node gốc, không xóa gì
$('#backStepBtn').addEventListener('click', () => {
  if (!treeRoot) return;
  focusNode = null;
  renderTrail();
  panZoom.centerOn(treeRoot.x, treeRoot.y);
});
$('#submitFlowBtn').addEventListener('click', submitFlow);

// ---- Bắt đầu flow mới ----
function startFlow() {
  rootTopic = $('#rootInput').value.trim();
  if (!rootTopic) { toast('Nhập chủ đề trước'); return; }
  nodeIdCtr = 0;
  focusNode = null;
  treeRoot  = makeNode(rootTopic, null);
  renderTrail();
  renderSidebarTree();
  expandNode(treeRoot);
}

// ---- Thanh breadcrumb ----
function renderTrail() {
  const t = $('#trail');
  t.innerHTML = '';
  if (!treeRoot) return;
  const path = focusNode ? pathFromRoot(focusNode) : [rootTopic];
  path.forEach((label, i) => {
    const c = document.createElement('span');
    c.className = 'chip' + (i === 0 ? ' root' : '');
    c.textContent = label;
    t.appendChild(c);
  });
  $('#backStepBtn').disabled = false;
  $('#submitFlowBtn').disabled = !focusNode;
}

// ---- Bố cục cây PHÂN CẤP NGANG (tidy tree) — không bao giờ chồng nhau ----
const COL = 250;   // khoảng cách ngang giữa các cấp (đủ chứa nhãn)
const ROW = 58;    // khoảng cách dọc giữa các lá (đủ chứa nhãn 2 dòng)

function layoutTree() {
  if (!treeRoot) return;
  let rowCtr = 0;
  function assign(node, depth) {
    node._depth = depth;
    if (!node.children.length) {
      node._row = rowCtr++;
    } else {
      node.children.forEach((c) => assign(c, depth + 1));
      const first = node.children[0]._row;
      const last = node.children[node.children.length - 1]._row;
      node._row = (first + last) / 2;
    }
  }
  assign(treeRoot, 0);
  walkTree(treeRoot, (n) => {
    n.x = STAGE_PAD + n._depth * COL;
    n.y = STAGE_PAD + n._row * ROW;
    n._side = 'r'; // nhãn luôn nằm bên phải
  });
}

// ---- Mở rộng node: gọi AI để lấy 10 nhánh con ----
async function expandNode(node) {
  if (node.loading) return;
  if (node.expanded) {
    // Đã mở rộng rồi — chỉ cập nhật focus và cuộn đến
    focusNode = node === treeRoot ? null : node;
    renderTrail();
    scrollToNode(node);
    return;
  }

  node.loading = true;
  renderTreeCanvas();

  // Xây path cho AI: bao gồm node hiện tại để AI biết đang phân nhánh từ đâu
  const fullPath = pathFromRoot(node);
  const aiPath = fullPath.slice(1); // bỏ label gốc (đã truyền riêng qua rootTopic)

  const res = await aiInvoke('branches', { rootTopic, path: aiPath });
  node.loading = false;

  if (!res.ok) {
    toast('Lỗi AI: ' + res.error);
    renderTreeCanvas();
    return;
  }

  function applyBranches(branches) {
    node.children = (branches || []).map(label => {
      const c = makeNode(label, node);
      return c;
    });
    node.expanded = true;
    focusNode = node === treeRoot ? null : node;
    layoutTree();
    renderTreeCanvas();
    renderSidebarTree();
    renderTrail();
    scrollToNode(node);
  }

  if (res.mode === 'web') {
    openWebMode(res.prompt, (answer) => {
      let branches;
      try { branches = JSON.parse(answer.match(/\{[\s\S]*\}/)[0]).branches; }
      catch (_) { branches = answer.split('\n').map(l => l.replace(/^[\s\-*\d.)\]]+/, '').trim()).filter(Boolean).slice(0, 10); }
      applyBranches(branches);
    });
    node.loading = false;
    renderTreeCanvas();
    renderSidebarTree();
    return;
  }

  applyBranches(res.branches);
}

// ---- Vẽ cây phân cấp ngang (node tròn + nhãn phải, cạnh cong) ----
function renderTreeCanvas() {
  const area = $('#branchArea');
  area.innerHTML = '';
  if (!treeRoot) return;

  const areaW = area.clientWidth || 900;
  const areaH = area.clientHeight || 500;

  // Kích thước stage theo toạ độ lớn nhất
  let maxX = 0, maxY = 0;
  walkTree(treeRoot, (n) => { maxX = Math.max(maxX, n.x); maxY = Math.max(maxY, n.y); });
  const stageW = Math.max(maxX + 320, areaW * 1.2);
  const stageH = Math.max(maxY + 160, areaH * 1.2);

  const stage = document.createElement('div');
  stage.className = 'tree-stage';
  stage.style.width = stageW + 'px';
  stage.style.height = stageH + 'px';
  const svg = document.createElementNS(SVGNS, 'svg');
  svg.setAttribute('class', 'tree-lines');
  svg.setAttribute('width', stageW);
  svg.setAttribute('height', stageH);
  stage.appendChild(svg);

  // Cạnh cong ngang (parent phải -> con)
  walkTree(treeRoot, (nd) => {
    if (!nd.parent) return;
    const px = nd.parent.x, py = nd.parent.y, cx = nd.x, cy = nd.y;
    const mx = (px + cx) / 2;
    const p = document.createElementNS(SVGNS, 'path');
    p.setAttribute('d', `M ${px} ${py} C ${mx} ${py}, ${mx} ${cy}, ${cx} ${cy}`);
    const onPath = focusNode && isAncestor(nd, focusNode);
    p.setAttribute('class', 'tline ' + (nd.expanded ? 'acquired' : 'candidate') + (onPath ? ' onpath' : ''));
    svg.appendChild(p);
  });

  // Node
  walkTree(treeRoot, (nd) => {
    const type = !nd.parent ? 'root'
      : nd === focusNode ? 'active-spine'
      : nd.loading ? 'loading-node'
      : nd.expanded ? 'acquired' : 'candidate';
    const icon = !nd.parent ? '⚡' : (nd.expanded ? '✓' : NODE_ICONS[nd.id % NODE_ICONS.length]);
    const el = document.createElement('div');
    el.className = 'tnode ' + type + ' lateral';
    el.style.left = nd.x + 'px';
    el.style.top = nd.y + 'px';
    const ic = nd.loading ? '<span class="loading"></span>' : icon;
    const lbl = escapeHtml(nd.label) + (nd.loading ? '<div class="tprogress">⏳ đang hỏi…</div>' : '');
    el.innerHTML = `<div class="tcircle">${ic}</div><div class="tlabel">${lbl}</div>`;
    el.title = nd.label;
    stage.appendChild(el);
  });

  area.appendChild(stage);
  panZoom.centerOn((focusNode || treeRoot).x, (focusNode || treeRoot).y);
}

function scrollToNode(nd) {
  panZoom.centerOn(nd.x, nd.y);
}

// ---- Sidebar = NƠI CHỌN NHÁNH (breadcrumb tiến trình + danh sách nhánh con) ----
// (canvas constellation chỉ để HIỂN THỊ)
function renderSidebarTree() {
  const sidebar = $('#treeSidebar');
  sidebar.innerHTML = '';
  if (!treeRoot) {
    sidebar.innerHTML = '<div class="empty-hint">Chưa có dữ liệu. Nhập chủ đề và bấm Bắt đầu.</div>';
    return;
  }

  const current = focusNode || treeRoot;

  // ===== 1) BREADCRUMB tiến trình (bấm để quay lại bước trước) =====
  const path = [];
  let cur = current;
  while (cur) { path.unshift(cur); cur = cur.parent; }

  const head = document.createElement('div');
  head.className = 'progress-head';
  head.textContent = `Tiến trình · ${path.length} bước`;
  sidebar.appendChild(head);

  path.forEach((nd, i) => {
    const isLast = i === path.length - 1;
    const el = document.createElement('div');
    el.className = 'progress-step' + (isLast ? ' current' : '');
    el.innerHTML = `<span class="step-dot">${i === 0 ? '⚡' : i}</span>` +
      `<span class="step-label">${escapeHtml(nd.label)}</span>`;
    el.addEventListener('click', () => {
      focusNode = nd === treeRoot ? null : nd;
      renderTrail(); renderSidebarTree(); scrollToNode(nd);
    });
    sidebar.appendChild(el);
  });

  // ===== 2) DANH SÁCH NHÁNH CON để CHỌN =====
  const optHead = document.createElement('div');
  optHead.className = 'options-head';
  sidebar.appendChild(optHead);

  if (current.loading) {
    optHead.innerHTML = '<span class="loading" style="width:12px;height:12px;border-width:2px;"></span> Đang tạo nhánh…';
    return;
  }
  if (!current.children.length) {
    optHead.textContent = 'Nhánh cuối — bấm “Phân tích nhánh này” để tổng hợp.';
    return;
  }

  optHead.textContent = `Chọn nhánh để đi sâu (${current.children.length})`;
  current.children.forEach((child) => {
    const el = document.createElement('div');
    el.className = 'option-item' + (child.expanded ? ' done' : '') + (child.loading ? ' loading' : '');
    const icon = child.loading
      ? '<span class="loading" style="width:12px;height:12px;border-width:2px;"></span>'
      : (child.expanded ? '✓' : NODE_ICONS[child.id % NODE_ICONS.length]);
    el.innerHTML = `<span class="option-icon">${icon}</span>` +
      `<span class="option-label">${escapeHtml(child.label)}</span>` +
      `<span class="option-arrow">${child.expanded ? '' : '›'}</span>`;
    el.addEventListener('click', () => {
      if (child.loading) return;
      focusNode = child;
      renderTrail();
      renderSidebarTree();
      scrollToNode(child);
      if (!child.expanded) expandNode(child); // đi sâu -> lấy 10 nhánh con
    });
    sidebar.appendChild(el);
  });
}

// ---- Gửi phân tích tổng hợp ----
async function submitFlow() {
  if (!focusNode && treeRoot && !treeRoot.expanded) { toast('Hãy chọn ít nhất một nhánh trước'); return; }
  $('#outputDrawer').classList.add('open');
  const out = $('#aiOutput');
  out.innerHTML = '<div class="empty-hint"><span class="loading"></span> AI đang tổng hợp &amp; phân tích...</div>';
  const note = $('#noteInput').value.trim();
  const path = focusNode ? pathFromRoot(focusNode).slice(1) : [];
  const res = await aiInvoke('final', { rootTopic, path, note });
  if (!res.ok) { out.innerHTML = `<p style="color:var(--danger)">${escapeHtml(res.error)}</p>`; return; }
  if (res.mode === 'web') {
    openWebMode(res.prompt, (answer) => { out.innerHTML = md(answer); });
    out.innerHTML = '<div class="empty-hint">Đang chờ kết quả từ web chatbox...</div>';
  } else {
    out.innerHTML = md(res.text);
  }
}

$('#copyOutBtn').addEventListener('click', () => {
  navigator.clipboard.writeText($('#aiOutput').innerText);
  toast('Đã sao chép kết quả');
});
$('#closeDrawerBtn').addEventListener('click', () => $('#outputDrawer').classList.remove('open'));

// ----------------------------- web mode modal & auto ------------------------
let webCallback = null;

function openWebMode(prompt, cb) {
  webCallback = cb;
  $('#webPrompt').value = prompt;
  $('#webAnswer').value = '';
  openModal('webModal');
}
$('#copyPromptBtn').addEventListener('click', () => {
  navigator.clipboard.writeText($('#webPrompt').value);
  toast('Đã copy prompt — dán vào web chatbox');
});
$('#useAnswerBtn').addEventListener('click', () => {
  const ans = $('#webAnswer').value.trim();
  if (!ans) { toast('Dán output vào đã'); return; }
  closeModals();
  if (webCallback) webCallback(ans);
});

// ----------------------------- Web Automation Full State Machine ------------
let _poll_gen = 0;
let _poll_busy = false;

window.webBridge = {
  getWebView() { return document.getElementById('geminiWeb'); },
  
  openHome() {
    const s = document.getElementById('webSite').value;
    const urls = {
      gemini: 'https://gemini.google.com/app',
      chatgpt: 'https://chatgpt.com/',
      claude: 'https://claude.ai/new',
      grok: 'https://grok.com/'
    };
    this.getWebView().loadURL(urls[s] || urls.gemini);
  },
  
  reload() {
    const s = document.getElementById('webSite').value;
    const urls = {
      gemini: 'https://gemini.google.com/app',
      chatgpt: 'https://chatgpt.com/?temporary-chat=true',
      claude: 'https://claude.ai/new',
      grok: 'https://grok.com/?new'
    };
    this.getWebView().loadURL(urls[s] || urls.gemini);
  },

  send(prompt) {
    return new Promise((resolve, reject) => {
      if (_poll_busy) return reject(new Error('Đang xử lý một yêu cầu khác'));
      _poll_busy = true;
      _poll_gen++;
      const gen = _poll_gen;
      const webview = this.getWebView();
      const status = document.getElementById('webStatus');
      
      status.textContent = 'Bắt đầu luồng...';
      this.reload();

      const onLoaded = async () => {
        webview.removeEventListener('dom-ready', onLoaded);
        webview.removeEventListener('did-stop-loading', onLoaded);
        status.textContent = 'Đã tải trang, đang chèn prompt...';

        // Đợi Focus và chèn text
        const injectJs = `
          (function(){
            return new Promise((resolve) => {
              let attempts = 0;
              let timer = setInterval(() => {
                const ss = ['rich-textarea [contenteditable="true"]', '#prompt-textarea', '.ProseMirror', '.ql-editor', '[contenteditable="true"]', '[role="textbox"]', 'textarea'];
                let e = null;
                for(const s of ss){ e = document.querySelector(s); if(e && e.offsetParent !== null) break; }
                
                if(e){
                  clearInterval(timer);
                  e.focus();
                  document.execCommand('insertText', false, ${JSON.stringify(prompt)});
                  if (e.textContent.trim() === '') {
                    e.textContent = ${JSON.stringify(prompt)};
                    e.dispatchEvent(new Event('input', {bubbles: true}));
                  }
                  resolve(true);
                } else if(attempts > 15) {
                  clearInterval(timer);
                  resolve(false);
                }
                attempts++;
              }, 500);
            });
          })();
        `;
        const inserted = await webview.executeJavaScript(injectJs);
        if (!inserted) {
          _poll_busy = false;
          status.textContent = 'Lỗi: Không tìm thấy ô nhập';
          return reject(new Error('Không tìm thấy ô nhập liệu sau 7.5s'));
        }

        await new Promise(r => setTimeout(r, 750));
        if (gen !== _poll_gen) return;
        
        status.textContent = 'Đang gửi prompt...';
        const submitJs = `
          (function(){
            return new Promise((resolve) => {
              let attempts = 0;
              let timer = setInterval(() => {
                let btn = document.querySelector('button[aria-label="Send message"], button[data-testid="send-button"], button.send-button, .send-button');
                if (btn && !btn.disabled && btn.offsetParent !== null) {
                  clearInterval(timer);
                  btn.click();
                  resolve(true);
                } else if(attempts > 10) {
                  clearInterval(timer);
                  resolve(false);
                }
                attempts++;
              }, 500);
            });
          })();
        `;
        const submitted = await webview.executeJavaScript(submitJs);
        if (!submitted) {
          _poll_busy = false;
          status.textContent = 'Lỗi: Không tìm thấy nút Gửi';
          return reject(new Error('Không tìm thấy nút Gửi'));
        }

        status.textContent = 'Đang đợi AI trả lời...';
        this.waitResponse(gen, resolve, reject, 0, "");
      };

      webview.addEventListener('dom-ready', onLoaded);
      webview.addEventListener('did-stop-loading', onLoaded);
    });
  },

  waitResponse(gen, resolve, reject, attempt, lastText) {
    if (gen !== _poll_gen) return;
    if (attempt > 75) { // Timeout ~110s
      _poll_busy = false;
      document.getElementById('webStatus').textContent = 'Timeout!';
      return reject(new Error('AI trả lời quá lâu (Timeout)'));
    }

    const readJs = `
      (function(){
        function isPrompt(t){
          return t.indexOf('CHÚ Ý CÁC QUY TẮC')>=0 || t.indexOf('Tuyệt đối tuân thủ')>=0;
        }
        var sels=['.markdown', '.model-response-text', 'message-content', '[data-message-author-role="assistant"]', '.font-claude-message', '.response-content', '[class*="model-response"]'];
        for(var s=0;s<sels.length;s++){
          var els=document.querySelectorAll(sels[s]);
          for(var i=els.length-1;i>=0;i--){
             var t=(els[i].innerText||'').trim();
             if(t.length>40 && !isPrompt(t)){
                var btn = document.querySelector('button[aria-label="Send message"], button[data-testid="send-button"]');
                var done = (btn && !btn.disabled);
                return {text: t, done: done};
             }
          }
        }
        return {text: '', done: false};
      })()
    `;

    this.getWebView().executeJavaScript(readJs).then(res => {
      if (gen !== _poll_gen) return;
      if (res && res.text) {
        if (res.done || (res.text === lastText && attempt > 5)) {
           _poll_busy = false;
           document.getElementById('webStatus').textContent = 'Hoàn thành';
           resolve(res.text);
        } else {
           setTimeout(() => this.waitResponse(gen, resolve, reject, attempt + 1, res.text), 1500);
        }
      } else {
        setTimeout(() => this.waitResponse(gen, resolve, reject, attempt + 1, ""), 1500);
      }
    }).catch(err => {
      setTimeout(() => this.waitResponse(gen, resolve, reject, attempt + 1, lastText), 1500);
    });
  }
};

// ----------------------------- modal plumbing -------------------------------
function openModal(id) { $('#overlay').classList.remove('hidden'); $('#' + id).classList.remove('hidden'); }
function closeModals() {
  $('#overlay').classList.add('hidden');
  $$('.modal').forEach((m) => m.classList.add('hidden'));
}
$('#overlay').addEventListener('click', closeModals);
$$('[data-close]').forEach((b) => b.addEventListener('click', closeModals));

// ----------------------------- Pan & Zoom (transform-based) -----------------
const panZoom = (function () {
  const area = $('#branchArea');
  let scale = 1, panX = 0, panY = 0;
  let dragging = false, hasMoved = false;
  let startX = 0, startY = 0, startPanX = 0, startPanY = 0;
  const THRESHOLD = 5;
  const MIN_SCALE = 0.15, MAX_SCALE = 2.5;

  // ---- Tạo zoom panel UI ----
  const zoomPanel = document.createElement('div');
  zoomPanel.className = 'zoom-panel';
  zoomPanel.innerHTML = `
    <button id="zoomInBtn" title="Phóng to">+</button>
    <input type="range" id="zoomSlider" class="zoom-slider" min="15" max="250" value="100" />
    <button id="zoomOutBtn" title="Thu nhỏ">−</button>
    <span class="zoom-label" id="zoomLabel">100%</span>
  `;
  area.appendChild(zoomPanel);

  const slider = $('#zoomSlider');
  const label  = $('#zoomLabel');

  function applyTransform() {
    const stage = area.querySelector('.tree-stage');
    if (stage) stage.style.transform = `translate(${panX}px, ${panY}px) scale(${scale})`;
    slider.value = Math.round(scale * 100);
    label.textContent = Math.round(scale * 100) + '%';
  }

  function setScale(s, cx, cy) {
    const oldScale = scale;
    scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, s));
    // Zoom về phía con trỏ chuột
    if (cx !== undefined) {
      const rect = area.getBoundingClientRect();
      const mx = cx - rect.left, my = cy - rect.top;
      panX = mx - (mx - panX) * (scale / oldScale);
      panY = my - (my - panY) * (scale / oldScale);
    }
    applyTransform();
  }

  // ---- Mouse wheel zoom ----
  area.addEventListener('wheel', (e) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.12 : 0.89;
    setScale(scale * factor, e.clientX, e.clientY);
  }, { passive: false });

  // ---- Slider zoom ----
  slider.addEventListener('input', () => {
    const rect = area.getBoundingClientRect();
    setScale(parseInt(slider.value) / 100, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  // Ngăn slider trigger drag
  zoomPanel.addEventListener('mousedown', (e) => e.stopPropagation());

  // ---- Nút + / − ----
  $('#zoomInBtn').addEventListener('click', () => {
    const rect = area.getBoundingClientRect();
    setScale(scale * 1.25, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });
  $('#zoomOutBtn').addEventListener('click', () => {
    const rect = area.getBoundingClientRect();
    setScale(scale * 0.8, rect.left + rect.width / 2, rect.top + rect.height / 2);
  });

  // ---- Drag pan ----
  area.addEventListener('mousedown', (e) => {
    if (e.button !== 0) return;
    if (e.target.closest('.tnode') || e.target.closest('.zoom-panel')) return;
    dragging = true;
    hasMoved = false;
    startX = e.clientX;  startY = e.clientY;
    startPanX = panX;    startPanY = panY;
    area.style.cursor = 'grabbing';
    e.preventDefault();
  });

  window.addEventListener('mousemove', (e) => {
    if (!dragging) return;
    const dx = e.clientX - startX, dy = e.clientY - startY;
    if (Math.abs(dx) > THRESHOLD || Math.abs(dy) > THRESHOLD) hasMoved = true;
    panX = startPanX + dx;
    panY = startPanY + dy;
    applyTransform();
  });

  window.addEventListener('mouseup', () => {
    if (!dragging) return;
    dragging = false;
    area.style.cursor = 'grab';
  });

  area.addEventListener('click', (e) => {
    if (hasMoved) { e.stopPropagation(); hasMoved = false; }
  }, true);

  // Căn điểm (x,y) trong stage vào giữa khung nhìn
  function centerOn(x, y) {
    panX = area.clientWidth / 2 - x * scale;
    panY = area.clientHeight / 2 - y * scale;
    applyTransform();
  }
  function reset() { scale = 1; panX = 0; panY = 0; applyTransform(); }

  // QUAN TRỌNG: phải return API để panZoom.centerOn(...) hoạt động
  return { centerOn, applyTransform, setScale, reset };
})();

// ----------------------------- debug button ---------------------------------
$('#debugBtn').addEventListener('click', () => {
  if (window.api && window.api.openDevTools) {
    window.api.openDevTools();
  }
});

// ----------------------------- AI Web tab wiring ----------------------------
(function aiWebTab() {
  const btn = $('#qtStartBtn');
  const status = $('#webStatus');
  if (!btn) return;
  let polling = null;

  btn.addEventListener('click', async () => {
    status.textContent = 'đang khởi động cửa sổ Qt…';
    const r = await window.api.qtbridgeStart();
    if (!r.ok) { status.textContent = 'lỗi spawn Python: ' + (r.error || '?'); return; }
    if (!polling) {
      polling = setInterval(async () => {
        const h = await window.api.qtbridgeHealth();
        status.textContent = h && h.ok
          ? '✅ Bridge sẵn sàng — đăng nhập Gemini trong cửa sổ Qt rồi dùng Phân nhánh AI.'
          : '⏳ đang chờ bridge lên…';
      }, 1500);
    }
  });
})();

// ----------------------------- boot -----------------------------------------
(async function boot() {
  await loadConfig();
  await initCategories();
})();
