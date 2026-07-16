const { app, BrowserWindow, ipcMain, session } = require('electron');

const path = require('path');
const { spawn } = require('child_process');
const http = require('http');
const fs = require('fs');
const os = require('os');
const Parser = require('rss-parser');
const feedsConfig = require('./src/feeds');
const ai = require('./src/ai');

const parser = new Parser({
  timeout: 12000,
  headers: { 'User-Agent': 'Mozilla/5.0 FinPulseAI/0.1' }
});

const CONFIG_PATH = path.join(app.getPath('userData'), 'config.json');

function loadConfig() {
  try {
    return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
  } catch (_) {
    return { mode: 'api', provider: 'gemini', apiKey: '', model: 'gemini-2.0-flash' };
  }
}
function saveConfig(cfg) {
  fs.writeFileSync(CONFIG_PATH, JSON.stringify(cfg, null, 2));
  return cfg;
}

let mainWindow;
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1320,
    height: 860,
    minWidth: 900,
    backgroundColor: '#0b0f17',
    title: 'FinPulse AI',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webviewTag: true
    }
  });
  mainWindow.removeMenu();

  // Tiêm preload chống dò Electron vào MỌI webview con.
  mainWindow.webContents.on('will-attach-webview', (_e, webPreferences) => {
    webPreferences.preload = path.join(__dirname, 'renderer', 'webview-preload.js');
    webPreferences.contextIsolation = false; // để preload sửa được navigator của trang
    webPreferences.nodeIntegration = false;
  });

  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  if (process.argv.includes('--dev')) mainWindow.webContents.openDevTools();
}

// Đã gỡ bỏ tính năng đổi UA (hardenAiSession) theo hướng dẫn

app.whenReady().then(() => {
  createWindow();
});

// ============================================================================
//  AI WINDOW BRIDGE — mở Gemini trong CỬA SỔ THẬT (top-level BrowserWindow),
//  ít bị Google chặn hơn <webview>; backend lái cửa sổ này (giống MT4 app lái
//  cửa sổ MT4). Dùng chung session 'persist:aichat' nên đăng nhập 1 lần.
// ============================================================================
const GEMINI = {
  url: 'https://gemini.google.com/app',
  input: ['.ql-editor', 'div[contenteditable="true"]', 'textarea', '[role="textbox"]'],
  answer: ['.model-response-text', 'message-content', '[class*="model-response"]', '.markdown']
};
const DONE = '<<<DONE>>>';
let aiWin = null;

function ensureAiWin(show) {
  if (aiWin && !aiWin.isDestroyed()) { if (show) { aiWin.show(); aiWin.focus(); } return aiWin; }
  aiWin = new BrowserWindow({
    width: 1100, height: 820, show: !!show, title: 'Gemini — FinPulse',
    backgroundColor: '#ffffff',
    webPreferences: {
      partition: 'persist:aichat',
      preload: path.join(__dirname, 'renderer', 'webview-preload.js'),
      contextIsolation: false,   // để preload spoof navigator của trang
      nodeIntegration: false
    }
  });
  aiWin.removeMenu();
  aiWin.on('closed', () => { aiWin = null; });
  aiWin.loadURL(GEMINI.url);
  return aiWin;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
function wcLoad(wc, url) {
  return new Promise((resolve) => {
    let done = false;
    const fin = () => { if (done) return; done = true; resolve(); };
    wc.once('did-finish-load', fin);
    setTimeout(fin, 9000);
    wc.loadURL(url);
  });
}
function sendStatus(s) {
  if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('aiwin-status-update', s);
}

ipcMain.handle('aiwin-show', () => {
  try { ensureAiWin(true); return { ok: true }; }
  catch (e) { console.error('[aiwin-show] error:', e); return { ok: false, error: String(e && e.message || e) }; }
});

ipcMain.handle('aiwin-send', async (_e, prompt) => {
  const win = ensureAiWin(false);
  const wc = win.webContents;
  const marked = prompt + '\n\n---\nKhi đã viết xong TOÀN BỘ nội dung, kết thúc bằng đúng MỘT dòng riêng: ' + DONE;
  try {
    sendStatus('mở chat mới…');
    await wcLoad(wc, GEMINI.url);
    await wait(2300);
    sendStatus('focus ô nhập…');
    let focused = await wc.executeJavaScript(
      `(function(){var ss=${JSON.stringify(GEMINI.input)};for(var i=0;i<ss.length;i++){var e=document.querySelector(ss[i]);if(e){e.focus();return true;}}return false;})()`);
    if (!focused) { await wait(1500); focused = await wc.executeJavaScript(
      `(function(){var ss=${JSON.stringify(GEMINI.input)};for(var i=0;i<ss.length;i++){var e=document.querySelector(ss[i]);if(e){e.focus();return true;}}return false;})()`); }
    if (!focused) throw new Error('Không thấy ô nhập — mở "Cửa sổ Gemini" và đăng nhập trước.');

    sendStatus('nhập prompt…');
    await wc.executeJavaScript(
      `(function(){var t=${JSON.stringify(marked)};var el=document.activeElement;if(!el)return false;try{document.execCommand('insertText',false,t);}catch(e){}if('value' in el && (!el.value||el.value.length<2)){el.value=t;el.dispatchEvent(new Event('input',{bubbles:true}));}return true;})()`);
    await wait(800);

    sendStatus('gửi…');
    try { wc.focus(); wc.sendInputEvent({ type: 'keyDown', keyCode: 'Enter' }); wc.sendInputEvent({ type: 'keyUp', keyCode: 'Enter' }); } catch (_) {}
    await wc.executeJavaScript(
      `(function(){var el=document.activeElement;var ev={key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true,cancelable:true};if(el){el.dispatchEvent(new KeyboardEvent('keydown',ev));el.dispatchEvent(new KeyboardEvent('keyup',ev));}var bs=document.querySelectorAll('button[aria-label],button[mattooltip]');for(var i=0;i<bs.length;i++){var a=((bs[i].getAttribute('aria-label')||'')+' '+(bs[i].getAttribute('mattooltip')||'')).toLowerCase();if(/send|gửi|submit/.test(a)&&!bs[i].disabled){bs[i].click();return 'btn';}}return 'enter';})()`);

    const readJS = `(function(){var sels=${JSON.stringify(GEMINI.answer)};for(var s=0;s<sels.length;s++){var els=document.querySelectorAll(sels[s]);if(els.length){var t=(els[els.length-1].innerText||'').trim();if(t.length>2)return t;}}return '';})()`;
    const start = Date.now();
    let last = '', stable = 0;
    while (Date.now() - start < 130000) {
      await wait(2200);
      const t = (await wc.executeJavaScript(readJS)) || '';
      if (t.includes(DONE)) { sendStatus('xong ✓'); return { ok: true, text: t.split(DONE)[0].trim() }; }
      if (t.length > 40 && t === last) { if (++stable >= 3) { sendStatus('xong ✓'); return { ok: true, text: t.trim() }; } }
      else { stable = 0; last = t; }
      sendStatus('đọc trả lời… (' + t.length + ' ký tự)');
    }
    sendStatus('hết giờ — trả về tạm');
    return { ok: true, text: last.trim() };
  } catch (err) {
    sendStatus('lỗi: ' + err.message);
    return { ok: false, error: err.message };
  }
});

// ============================================================================
//  QT BRIDGE — service Python + PyQt6 QWebEngine (Google CHO login trong Qt).
//  Electron spawn tiến trình Python, rồi gọi HTTP localhost:8765 để lấy output.
// ============================================================================
let qtProc = null;
function startQtBridge() {
  if (qtProc && !qtProc.killed) return { ok: true, already: true };
  const script = path.join(__dirname, 'bridge', 'gemini_bridge.py');
  const cmd = process.platform === 'win32' ? 'python' : 'python3';
  try {
    qtProc = spawn(cmd, [script], { cwd: __dirname });
    qtProc.stdout.on('data', (d) => console.log('[qt]', String(d).trim()));
    qtProc.stderr.on('data', (d) => console.error('[qt-err]', String(d).trim()));
    qtProc.on('exit', (code) => { console.log('[qt] exited', code); qtProc = null; });
    qtProc.on('error', (e) => { console.error('[qt] spawn error', e.message); qtProc = null; });
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}
function qtHttp(method, pathname, body) {
  return new Promise((resolve) => {
    const data = body ? Buffer.from(JSON.stringify(body)) : null;
    const req = http.request({
      host: '127.0.0.1', port: 8765, path: pathname, method,
      headers: data ? { 'Content-Type': 'application/json', 'Content-Length': data.length } : {}
    }, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
      res.on('end', () => { try { resolve(JSON.parse(b)); } catch (_) { resolve({ ok: false, error: 'bad response' }); } });
    });
    req.on('error', (e) => resolve({ ok: false, error: e.message }));
    req.setTimeout(160000, () => { req.destroy(); resolve({ ok: false, error: 'timeout' }); });
    if (data) req.write(data);
    req.end();
  });
}
ipcMain.handle('qtbridge-start', () => startQtBridge());
ipcMain.handle('qtbridge-health', () => qtHttp('GET', '/health'));
ipcMain.handle('qtbridge-ask', (_e, prompt) => qtHttp('POST', '/ask', { prompt }));
app.on('will-quit', () => { if (qtProc) { try { qtProc.kill(); } catch (_) {} } });

// Mỗi webview con: cho popup đăng nhập mở ngay trong webview
// (Google OAuth đôi khi bật cửa sổ mới).
app.on('web-contents-created', (_e, contents) => {
  if (contents.getType() === 'webview') {
    contents.setWindowOpenHandler(({ url }) => {
      contents.loadURL(url); // điều hướng popup ngay trong webview
      return { action: 'deny' };
    });
  }
});
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// ---- IPC -------------------------------------------------------------------

ipcMain.on('open-devtools', () => {
  if (mainWindow) mainWindow.webContents.openDevTools();
});

ipcMain.handle('get-categories', () =>
  feedsConfig.categories.map((c) => ({ id: c.id, label: c.label, icon: c.icon }))
);

ipcMain.handle('get-config', () => loadConfig());
ipcMain.handle('save-config', (_e, cfg) => saveConfig(cfg));

ipcMain.handle('fetch-category', async (_e, categoryId) => {
  const cat = feedsConfig.categories.find((c) => c.id === categoryId);
  if (!cat) return { items: [], errors: ['Unknown category'] };

  const results = await Promise.allSettled(
    cat.feeds.map((url) => parser.parseURL(url))
  );

  const items = [];
  const errors = [];
  results.forEach((r, i) => {
    if (r.status === 'fulfilled') {
      const source = r.value.title || new URL(cat.feeds[i]).hostname;
      (r.value.items || []).forEach((it) => {
        items.push({
          title: it.title || '(no title)',
          link: it.link || '',
          snippet: stripHtml(it.contentSnippet || it.content || '').slice(0, 400),
          content: stripHtml(it.content || it.contentSnippet || ''),
          source,
          date: it.isoDate || it.pubDate || ''
        });
      });
    } else {
      errors.push(`${cat.feeds[i]} — ${r.reason?.message || 'failed'}`);
    }
  });

  // Newest first, de-dup by title.
  const seen = new Set();
  const deduped = items.filter((it) => {
    const k = it.title.toLowerCase();
    if (seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  deduped.sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));

  return { items: deduped.slice(0, 60), errors };
});

ipcMain.handle('ai-run', async (_e, { task, payload }) => {
  const config = loadConfig();
  try {
    const out = await ai.run({ task, config, payload });
    return { ok: true, ...out };
  } catch (err) {
    return { ok: false, error: err.message };
  }
});

function stripHtml(s) {
  return String(s || '')
    .replace(/<[^>]*>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&#\d+;/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}
