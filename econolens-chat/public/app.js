// ================= State =================
const state = {
  token: localStorage.getItem('token') || null,
  user: null,
  personas: [],
  providers: [],
  persona: localStorage.getItem('persona') || 'student',
  provider: localStorage.getItem('provider') || null,
};

const $ = id => document.getElementById(id);
const API_BASE = window.location.pathname.includes('/embed_econolens') ? '/embed_econolens/api' : '/api';
const api = async (path, opts = {}) => {
  const res = await fetch(API_BASE + path, {
    ...opts,
    headers: {
      'content-type': 'application/json',
      ...(state.token ? { authorization: 'Bearer ' + state.token } : {}),
      ...(opts.headers || {})
    }
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && state.token) { logout(); throw new Error('Phiên hết hạn, vui lòng đăng nhập lại.'); }
  if (!res.ok) throw new Error(data.error || 'Lỗi máy chủ.');
  return data;
};

const STARTERS = {
  student: [
    'Lạm phát là gì? Giải thích đơn giản kèm ví dụ trà sữa 🧋',
    'GDP và GNP khác nhau như thế nào?',
    'Tại sao ngân hàng trung ương tăng lãi suất?',
    'Cung - cầu hoạt động ra sao? Cho mình quiz ôn tập!'
  ],
  analyst: [
    'Phân tích tác động của Fed giữ lãi suất cao kéo dài lên các nền kinh tế mới nổi',
    'So sánh tăng trưởng GDP Việt Nam với các nước ASEAN 5 năm gần đây',
    'Dùng mô hình AD-AS phân tích cú sốc cung dầu mỏ',
    'Kịch bản base/bull/bear cho kinh tế Việt Nam năm nay'
  ],
  investor: [
    'Lạm phát tăng thì nên cân nhắc các lớp tài sản nào?',
    'Chu kỳ kinh tế hiện tại đang ở giai đoạn nào và ý nghĩa với danh mục?',
    'So sánh rủi ro/cơ hội giữa vàng và trái phiếu lúc này',
    'Tỷ giá USD/VND biến động ảnh hưởng gì tới nhà đầu tư cá nhân?'
  ],
  policymaker: [
    'Đánh giá phương án tăng thuế VAT: lợi ích ngân sách vs tác động phân phối',
    'Kinh nghiệm quốc tế về kiểm soát giá bất động sản',
    'Lộ trình chuyển đổi xanh cho nền kinh tế đang phát triển',
    'Chính sách tiền tệ vs tài khóa: phối hợp thế nào khi lạm phát cao?'
  ]
};

// ================= Auth =================
let authMode = 'login';
document.querySelectorAll('.auth-tab').forEach(tab => {
  tab.onclick = () => {
    authMode = tab.dataset.mode;
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t === tab));
    $('nameField').style.display = authMode === 'register' ? '' : 'none';
    $('authSubmit').textContent = authMode === 'register' ? 'Tạo tài khoản' : 'Đăng nhập';
    $('authError').textContent = '';
  };
});

$('authForm').onsubmit = async e => {
  e.preventDefault();
  $('authError').textContent = '';
  $('authSubmit').disabled = true;
  try {
    const body = { email: $('emailInput').value.trim(), password: $('passwordInput').value };
    if (authMode === 'register') body.name = $('nameInput').value.trim();
    const data = await api('/' + authMode, { method: 'POST', body: JSON.stringify(body) });
    state.token = data.token;
    localStorage.setItem('token', data.token);
    await enterApp();
  } catch (err) {
    $('authError').textContent = err.message;
  } finally {
    $('authSubmit').disabled = false;
  }
};

function logout() {
  localStorage.removeItem('token');
  state.token = null;
  $('appScreen').style.display = 'none';
  $('authScreen').style.display = 'flex';
}
$('logoutBtn').onclick = logout;

// ================= App init =================
async function enterApp() {
  const meta = await api('/meta');
  state.personas = meta.personas;
  state.providers = meta.providers;
  state.user = meta.user;
  if (!state.providers.find(p => p.id === state.provider && p.configured)) {
    state.provider = (state.providers.find(p => p.configured) || state.providers[0]).id;
  }
  $('authScreen').style.display = 'none';
  $('appScreen').style.display = 'flex';
  $('userName').textContent = meta.user.name;
  $('userEmail').textContent = meta.user.email;
  $('userAvatar').textContent = (meta.user.name || '?')[0].toUpperCase();
  renderSidebar();
  await loadPersona(state.persona);
}

function renderSidebar() {
  $('personaList').innerHTML = '';
  for (const p of state.personas) {
    const el = document.createElement('div');
    el.className = 'persona-item' + (p.id === state.persona ? ' active' : '');
    el.style.setProperty('--p-color', p.color);
    el.innerHTML = `<span class="p-icon">${p.icon}</span><div><div class="p-name">${p.name}</div><div class="p-desc">${p.description}</div></div>`;
    el.onclick = () => loadPersona(p.id);
    $('personaList').appendChild(el);
  }
  $('providerList').innerHTML = '';
  for (const pr of state.providers) {
    const el = document.createElement('div');
    el.className = 'provider-item' + (pr.id === state.provider ? ' active' : '') + (pr.configured ? '' : ' disabled');
    el.title = pr.configured ? pr.model : 'Chưa cấu hình API key trong .env';
    el.innerHTML = `<span class="provider-dot"></span>${pr.name}<small>${pr.vendor}</small>`;
    el.onclick = () => {
      if (!pr.configured) return;
      state.provider = pr.id;
      localStorage.setItem('provider', pr.id);
      renderSidebar(); updateTopbar();
    };
    $('providerList').appendChild(el);
  }
  updateTopbar();
}

function currentPersona() { return state.personas.find(p => p.id === state.persona); }

function updateTopbar() {
  const p = currentPersona();
  const pr = state.providers.find(x => x.id === state.provider);
  $('topbarPersona').innerHTML = `<span>${p.icon}</span> ${p.name}`;
  $('topbarProvider').textContent = pr ? `${pr.name} · ${pr.model}` : '';
}

async function loadPersona(id) {
  state.persona = id;
  localStorage.setItem('persona', id);
  renderSidebar();
  const chat = $('chatArea');
  chat.innerHTML = '';
  const { history } = await api('/history/' + id);
  if (!history.length) {
    showWelcome();
  } else {
    for (const m of history) {
      if (m.role === 'user') addUserMsg(m.content);
      else addAiMsg(m.content, m.provider);
    }
    chat.scrollTop = chat.scrollHeight;
  }
}

function showWelcome() {
  const p = currentPersona();
  const w = document.createElement('div');
  w.className = 'welcome';
  w.innerHTML = `<h2>${p.icon} ${p.name}</h2><p>${p.description}</p><div class="starter-grid"></div>`;
  const grid = w.querySelector('.starter-grid');
  for (const q of STARTERS[p.id] || []) {
    const b = document.createElement('button');
    b.className = 'starter-card';
    b.textContent = q;
    b.onclick = () => { $('msgInput').value = q; send(); };
    grid.appendChild(b);
  }
  $('chatArea').appendChild(w);
}

$('clearBtn').onclick = async () => {
  if (!confirm('Xóa toàn bộ hội thoại của nhóm này?')) return;
  await api('/history/' + state.persona, { method: 'DELETE' });
  loadPersona(state.persona);
};

// ================= Chat =================
function addUserMsg(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  const bubble = document.createElement('div');
  bubble.className = 'bubble';
  bubble.textContent = text;
  el.appendChild(bubble);
  $('chatArea').appendChild(el);
  return el;
}

function addAiMsg(response, providerId) {
  const p = currentPersona();
  const pr = state.providers.find(x => x.id === providerId);
  const el = document.createElement('div');
  el.className = 'msg msg-ai';
  el.innerHTML = `<div class="ai-avatar">${p.icon}</div><div class="ai-body"><div class="ai-meta">${pr ? pr.name + ' · ' + pr.vendor : 'AI'}</div><div class="blocks"></div></div>`;
  renderBlocks(response.blocks || [], el.querySelector('.blocks'));
  $('chatArea').appendChild(el);

  // TTS: đọc to nội dung text/heading blocks đầu tiên nếu toggle bật
  try {
    const ttsBlocks = (response.blocks || []).filter(b => b.type === 'text' || b.type === 'heading');
    const ttsText = ttsBlocks.slice(0, 2).map(b => b.markdown || b.text || '').join('. ');
    if (ttsText) voiceIO.speak(ttsText);
  } catch (_) {}

  return el;
}

function addTyping() {
  const el = document.createElement('div');
  el.className = 'msg msg-ai';
  el.innerHTML = `<div class="ai-avatar">${currentPersona().icon}</div><div class="ai-body"><div class="blk typing"><span></span><span></span><span></span></div></div>`;
  $('chatArea').appendChild(el);
  el.scrollIntoView({ behavior: 'smooth' });
  return el;
}

async function send() {
  const input = $('msgInput');
  const text = input.value.trim();
  if (!text) return;
  
  if ($('deepDiveToggle') && $('deepDiveToggle').checked) {
    return startDeepDive(text);
  }
  
  input.value = '';
  input.style.height = 'auto';
  doSend(text, text);
}

let deepDiveData = null;

async function startDeepDive(originalText) {
  const input = $('msgInput');
  input.value = '';
  input.style.height = 'auto';
  const welcome = document.querySelector('.welcome');
  if (welcome) welcome.remove();
  
  const typing = addTyping();
  $('sendBtn').disabled = true;

  try {
    const data = await api('/clarify', {
      method: 'POST',
      body: JSON.stringify({ message: originalText, provider: state.provider })
    });
    typing.remove();
    
    if (data && data.questions && data.questions.length > 0) {
      deepDiveData = {
        originalText,
        questions: data.questions,
        answers: [],
        currentIndex: 0
      };
      $('deepDiveModal').style.display = 'flex';
      renderDeepDiveQuestion();
    } else {
      doSend(originalText, originalText);
    }
  } catch (err) {
    console.error(err);
    typing.remove();
    doSend(originalText, originalText);
  } finally {
    $('sendBtn').disabled = false;
  }
}

function renderDeepDiveQuestion() {
  const q = deepDiveData.questions[deepDiveData.currentIndex];
  $('ddTitle').textContent = q.question || 'Vui lòng làm rõ...';
  $('ddStep').textContent = `${deepDiveData.currentIndex + 1}/${deepDiveData.questions.length}`;
  
  const optsContainer = $('ddOptions');
  optsContainer.innerHTML = '';
  
  let selectedVal = null;
  const updateNextBtn = () => {
    const nextBtn = $('ddNext');
    if (selectedVal || $('ddOtherInput').value.trim()) {
      nextBtn.classList.add('active');
    } else {
      nextBtn.classList.remove('active');
    }
  };

  (q.options || []).forEach((opt, idx) => {
    const div = document.createElement('div');
    div.className = 'dd-option';
    div.innerHTML = `<span>${opt}</span> <div class="dd-option-num">${idx + 1}</div>`;
    div.onclick = () => {
      document.querySelectorAll('.dd-option').forEach(x => x.classList.remove('selected'));
      div.classList.add('selected');
      selectedVal = opt;
      $('ddOtherInput').value = '';
      updateNextBtn();
    };
    optsContainer.appendChild(div);
  });
  
  $('ddOtherInput').value = '';
  $('ddOtherInput').oninput = () => {
    if ($('ddOtherInput').value.trim()) {
      document.querySelectorAll('.dd-option').forEach(x => x.classList.remove('selected'));
      selectedVal = null;
    }
    updateNextBtn();
  };
  
  updateNextBtn();
  
  $('ddSkip').onclick = () => finishDeepDiveQuestion(null);
  $('ddNext').onclick = () => {
    const ans = selectedVal || $('ddOtherInput').value.trim();
    if (ans) finishDeepDiveQuestion(ans);
  };
  $('ddClose').onclick = () => {
     $('deepDiveModal').style.display = 'none';
     doSend(deepDiveData.originalText, deepDiveData.originalText);
  };
}

function finishDeepDiveQuestion(answer) {
  if (answer) {
    deepDiveData.answers.push({
      q: deepDiveData.questions[deepDiveData.currentIndex].question,
      a: answer
    });
  }
  
  deepDiveData.currentIndex++;
  if (deepDiveData.currentIndex < deepDiveData.questions.length) {
    renderDeepDiveQuestion();
  } else {
    $('deepDiveModal').style.display = 'none';
    let combined = deepDiveData.originalText;
    if (deepDiveData.answers.length > 0) {
      combined += '\n\n---\n*Thông tin bổ sung làm rõ:*\n' + deepDiveData.answers.map(x => `- ${x.q}: ${x.a}`).join('\n');
    }
    doSend(combined, deepDiveData.originalText);
  }
}

async function doSend(textToSend, displayAs) {
  const welcome = document.querySelector('.welcome');
  if (welcome) welcome.remove();
  addUserMsg(displayAs);
  const typing = addTyping();
  $('sendBtn').disabled = true;
  
  const useWebSearch = $('webSearchToggle') ? $('webSearchToggle').checked : false;

  try {
    const data = await api('/chat', {
      method: 'POST',
      body: JSON.stringify({ 
        message: textToSend, 
        persona: state.persona, 
        provider: state.provider,
        useWebSearch
      })
    });
    typing.remove();
    addAiMsg(data.response, data.provider).scrollIntoView({ behavior: 'smooth' });
  } catch (err) {
    typing.remove();
    const el = document.createElement('div');
    el.className = 'msg msg-ai';
    el.innerHTML = `<div class="ai-avatar">⚠️</div><div class="ai-body"><div class="error-bubble"></div></div>`;
    el.querySelector('.error-bubble').textContent = err.message;
    $('chatArea').appendChild(el);
    el.scrollIntoView({ behavior: 'smooth' });
  } finally {
    $('sendBtn').disabled = false;
    $('msgInput').focus();
  }
}

$('sendBtn').onclick = send;
$('msgInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
});
$('msgInput').addEventListener('input', e => {
  e.target.style.height = 'auto';
  e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
});

// ================= Dynamic block renderer =================
const CHART_COLORS = ['#6366f1', '#10b981', '#f59e0b', '#ef4444', '#0ea5e9', '#a855f7', '#ec4899', '#84cc16'];
const md = s => DOMPurify.sanitize(marked.parse(String(s || '')));

function renderBlocks(blocks, container) {
  for (const b of blocks) {
    try { container.appendChild(renderBlock(b)); }
    catch (e) { console.warn('block render failed', b, e); }
  }
}

function renderBlock(b) {
  const div = document.createElement('div');
  switch (b.type) {
    case 'heading':
      div.className = 'blk blk-heading';
      div.textContent = b.text;
      break;

    case 'text':
      div.className = 'blk blk-text';
      div.innerHTML = md(b.markdown || b.text);
      break;

    case 'metrics': {
      div.className = 'blk';
      const grid = document.createElement('div');
      grid.className = 'metrics-grid';
      for (const m of b.items || []) {
        const card = document.createElement('div');
        card.className = 'metric';
        card.innerHTML = `<div class="m-label"></div><div class="m-value"></div><div class="m-change ${m.trend || 'flat'}"></div>`;
        card.querySelector('.m-label').textContent = m.label || '';
        card.querySelector('.m-value').textContent = m.value || '';
        card.querySelector('.m-change').textContent =
          (m.trend === 'up' ? '▲ ' : m.trend === 'down' ? '▼ ' : '') + (m.change || '');
        grid.appendChild(card);
      }
      div.appendChild(grid);
      break;
    }

    case 'chart': {
      div.className = 'blk blk-chart';
      if (b.title) {
        const t = document.createElement('div');
        t.className = 'chart-title'; t.textContent = b.title;
        div.appendChild(t);
      }
      const wrap = document.createElement('div');
      wrap.className = 'chart-wrap';
      const canvas = document.createElement('canvas');
      wrap.appendChild(canvas);
      div.appendChild(wrap);
      const type = ['line','bar','pie','doughnut','radar','polarArea'].includes(b.chartType) ? b.chartType : 'bar';
      const isCircular = ['pie','doughnut','polarArea'].includes(type);
      const datasets = (b.datasets || []).map((d, i) => ({
        label: d.label,
        data: d.data,
        backgroundColor: isCircular ? CHART_COLORS : CHART_COLORS[i % CHART_COLORS.length] + (type === 'line' ? '33' : 'cc'),
        borderColor: isCircular ? '#1a1f38' : CHART_COLORS[i % CHART_COLORS.length],
        borderWidth: 2,
        fill: type === 'line',
        tension: .35,
        pointRadius: 3
      }));
      // defer until attached to DOM
      requestAnimationFrame(() => {
        new Chart(canvas, {
          type,
          data: { labels: b.labels || [], datasets },
          options: {
            responsive: true, maintainAspectRatio: false,
            plugins: { legend: { labels: { color: '#9aa3c7', font: { family: 'Inter' } } } },
            scales: isCircular ? {} : {
              x: { ticks: { color: '#9aa3c7' }, grid: { color: '#2a305266' } },
              y: { ticks: { color: '#9aa3c7' }, grid: { color: '#2a305266' } }
            }
          }
        });
      });
      break;
    }

    case 'table': {
      div.className = 'blk blk-table';
      if (b.title) {
        const t = document.createElement('div');
        t.className = 'table-title'; t.textContent = b.title;
        div.appendChild(t);
      }
      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      for (const h of b.headers || []) {
        const th = document.createElement('th'); th.textContent = h; trh.appendChild(th);
      }
      thead.appendChild(trh); table.appendChild(thead);
      const tbody = document.createElement('tbody');
      for (const row of b.rows || []) {
        const tr = document.createElement('tr');
        for (const cell of row) { const td = document.createElement('td'); td.textContent = cell; tr.appendChild(td); }
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);
      div.appendChild(table);
      break;
    }

    case 'callout':
      div.className = 'blk callout ' + (b.style || 'info');
      div.innerHTML = `<div class="c-title"></div><div class="c-body"></div>`;
      div.querySelector('.c-title').textContent =
        ({ info: 'ℹ️ ', warning: '⚠️ ', success: '✅ ', tip: '💡 ' }[b.style] || '') + (b.title || '');
      div.querySelector('.c-body').innerHTML = md(b.markdown || b.text);
      break;

    case 'comparison': {
      div.className = 'comparison';
      if (b.title) {
        const t = document.createElement('div');
        t.className = 'comp-title'; t.textContent = b.title;
        div.appendChild(t);
      }
      for (const side of [b.left, b.right]) {
        const col = document.createElement('div');
        col.className = 'comp-col';
        const h = document.createElement('h4'); h.textContent = side?.title || '';
        const ul = document.createElement('ul');
        for (const pt of side?.points || []) { const li = document.createElement('li'); li.textContent = pt; ul.appendChild(li); }
        col.append(h, ul);
        div.appendChild(col);
      }
      break;
    }

    case 'timeline': {
      div.className = 'blk blk-timeline';
      if (b.title) {
        const t = document.createElement('div');
        t.className = 'table-title'; t.textContent = b.title;
        div.appendChild(t);
      }
      for (const ev of b.events || []) {
        const item = document.createElement('div');
        item.className = 'timeline-item';
        item.innerHTML = `<div class="t-date"></div><div class="t-body"><strong></strong><p></p></div>`;
        item.querySelector('.t-date').textContent = ev.date || '';
        item.querySelector('strong').textContent = ev.title || '';
        item.querySelector('p').textContent = ev.description || '';
        div.appendChild(item);
      }
      break;
    }

    case 'quiz': {
      div.className = 'blk quiz';
      const q = document.createElement('div');
      q.className = 'q-question'; q.textContent = '📝 ' + (b.question || '');
      div.appendChild(q);
      const explain = document.createElement('div');
      explain.className = 'q-explain';
      explain.innerHTML = md(b.explanation || '');
      const buttons = [];
      (b.options || []).forEach((opt, i) => {
        const btn = document.createElement('button');
        btn.className = 'q-opt'; btn.textContent = opt;
        btn.onclick = () => {
          buttons.forEach(x => x.disabled = true);
          btn.classList.add(i === b.answerIndex ? 'correct' : 'wrong');
          if (i !== b.answerIndex) buttons[b.answerIndex]?.classList.add('correct');
          explain.style.display = 'block';
        };
        buttons.push(btn);
        div.appendChild(btn);
      });
      div.appendChild(explain);
      break;
    }

    case 'suggestions':
      div.className = 'suggestions';
      for (const s of b.items || []) {
        const chip = document.createElement('button');
        chip.className = 'sug-chip'; chip.textContent = '💬 ' + s;
        chip.onclick = () => { $('msgInput').value = s; send(); };
        div.appendChild(chip);
      }
      break;

    default:
      div.className = 'blk blk-text';
      div.innerHTML = md(b.markdown || b.text || JSON.stringify(b));
  }
  return div;
}

// ================= Voice I/O (Web Speech API) =================
const voiceIO = (() => {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const synth = window.speechSynthesis;
  let recognition = null;
  let isListening = false;

  /** Khởi tạo STT recognition object. */
  function init() {
    if (!SpeechRecognition) return null;
    const r = new SpeechRecognition();
    r.lang = 'vi-VN';
    r.interimResults = true;
    r.maxAlternatives = 1;
    r.continuous = false;

    r.onresult = (e) => {
      const transcript = Array.from(e.results)
        .map(res => res[0].transcript).join('');
      $('msgInput').value = transcript;
      $('msgInput').dispatchEvent(new Event('input'));
      setMicStatus(e.results[e.results.length - 1].isFinal ? '' : '🔴 Đang nghe...');
    };
    r.onend = () => {
      isListening = false;
      updateMicBtn(false);
      setMicStatus('');
      // Tự gửi nếu có nội dung
      const txt = $('msgInput').value.trim();
      if (txt) send();
    };
    r.onerror = (e) => {
      isListening = false;
      updateMicBtn(false);
      setMicStatus(e.error === 'no-speech' ? '' : `⚠ ${e.error}`);
    };
    return r;
  }

  function updateMicBtn(listening) {
    const btn = $('micBtn');
    if (!btn) return;
    btn.textContent = listening ? '⏹' : '🎙';
    btn.classList.toggle('mic-active', listening);
    btn.title = listening ? 'Dừng ghi âm' : 'Nhấn để nói (Speech-to-Text)';
  }

  function setMicStatus(msg) {
    const el = $('micStatus');
    if (el) el.textContent = msg;
  }

  /** Bắt đầu / dừng ghi âm. */
  function toggle() {
    if (!SpeechRecognition) {
      alert('Trình duyệt của bạn không hỗ trợ Web Speech API.\nDùng Chrome hoặc Edge để bật tính năng này.');
      return;
    }
    if (isListening) {
      recognition.stop();
      return;
    }
    recognition = init();
    if (!recognition) return;
    try {
      recognition.start();
      isListening = true;
      updateMicBtn(true);
      setMicStatus('🔴 Đang nghe...');
    } catch (e) {
      console.error('STT start error:', e);
      setMicStatus('⚠ Không thể bắt đầu ghi âm');
    }
  }

  /**
   * Đọc to văn bản bằng TTS.
   * @param {string} text - Văn bản cần đọc
   */
  function speak(text) {
    if (!synth || !text) return;
    const ttsToggle = $('ttsToggle');
    if (!ttsToggle || !ttsToggle.checked) return;

    synth.cancel(); // Dừng bất kỳ đoạn đọc nào đang chạy
    const clean = text.replace(/[#*`_~>|\[\]]/g, '').substring(0, 500); // trim markdown
    const utt = new SpeechSynthesisUtterance(clean);
    utt.lang = 'vi-VN';
    utt.rate = 0.95;
    utt.pitch = 1;

    // Ưu tiên giọng tiếng Việt nếu có
    const voices = synth.getVoices();
    const viVoice = voices.find(v => v.lang.startsWith('vi'));
    if (viVoice) utt.voice = viVoice;

    synth.speak(utt);
  }

  return { toggle, speak, get supported() { return !!SpeechRecognition; } };
})();

// Gắn sự kiện mic button
document.addEventListener('DOMContentLoaded', () => {
  const micBtn = $('micBtn');
  if (micBtn) {
    micBtn.addEventListener('click', () => voiceIO.toggle());
    if (!voiceIO.supported) {
      micBtn.style.opacity = '0.4';
      micBtn.title = 'Trình duyệt không hỗ trợ ghi âm (cần Chrome/Edge)';
    }
  }
});

// ================= Boot =================
if (state.token) {
  enterApp().catch(() => logout());
}
