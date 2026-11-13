// Local API — cổng AI mặc định (thay cho Gemini CDP qua chrome_bridge).
//
// Server local (dự án API share community) phơi endpoint kiểu OpenAI:
//   POST http://localhost:4000/v1/chat/completions
//   headers: { "x-api-key": <LOCAL_API_KEY> }
//   body:    { model: "gemini-cdp", messages: [...] }
// Nó đẩy task vào hàng đợi cho provider-agent lái Gemini web → EconoLens chỉ cần
// gọi HTTP, không cần Chrome cổng 9222, không Playwright/CDP, không dính CAPTCHA.
//
// RÀNG BUỘC THẬT CỦA SERVER (openai.routes.js + dispatcher.service.js):
//  1. Hội thoại bị gộp bằng nội suy chuỗi → content BẮT BUỘC là string (mảng
//     content-parts/ảnh sẽ thành "[object Object]" mà không báo lỗi).
//  2. Chỉ role "user" ghi "User:", role khác (kể cả "system") thành "Assistant:"
//     → gộp system vào tin nhắn user (normalizeMessages lo).
//  3. Provider chạy tuần tự + cooldown 30s/task, server chờ tối đa 1 tiếng.
//
// Cùng hợp đồng với bản Python (data-crawler/src/local_api.py,
// market-pulse/modules/common/local_api.py):
//   LOCAL_API_URL · LOCAL_API_MODEL · LOCAL_API_KEY · LOCAL_API_TIMEOUT
// Key đọc theo thứ tự: process.env → "data-crawler/.env" (file dùng chung cả hệ thống).

const fs = require('fs');
const path = require('path');

const DEFAULT_URL = 'http://127.0.0.1:59999/v1/chat/completions';
const DEFAULT_MODEL = 'gemini-2.5-flash';
// Task xếp hàng + cooldown 30s/provider → chờ vài phút là bình thường.
const DEFAULT_TIMEOUT_MS = 900000;

// <root>/econolens-chat/lib → <root>/data-crawler/.env
const SHARED_ENV = path.resolve(__dirname, '..', '..', 'data-crawler', '.env');

let _envCache = null;
function sharedEnv() {
  if (_envCache) return _envCache;
  _envCache = {};
  try {
    for (const line of fs.readFileSync(SHARED_ENV, 'utf8').split(/\r?\n/)) {
      const s = line.trim();
      if (!s || s.startsWith('#') || !s.includes('=')) continue;
      const i = s.indexOf('=');
      _envCache[s.slice(0, i).trim()] = s.slice(i + 1).trim().replace(/^["']|["']$/g, '');
    }
  } catch (_) { /* không có file dùng chung thì thôi */ }
  return _envCache;
}

function cfg(name, fallback = '') {
  return (process.env[name] || sharedEnv()[name] || fallback).trim();
}

const apiKey = () => cfg('LOCAL_API_KEY');
const apiUrl = () => cfg('LOCAL_API_URL', DEFAULT_URL);
const apiModel = () => cfg('LOCAL_API_MODEL', DEFAULT_MODEL);
function timeoutMs() {
  const raw = cfg('LOCAL_API_TIMEOUT');
  const n = raw ? Number(raw) * 1000 : DEFAULT_TIMEOUT_MS;
  return Number.isFinite(n) && n > 0 ? n : DEFAULT_TIMEOUT_MS;
}

/** Đã cấu hình đủ để dùng kênh này chưa (không gọi mạng). */
function configured() { return Boolean(apiKey()); }

function baseUrl() {
  const u = apiUrl();
  const i = u.indexOf('/v1/');
  return i > 0 ? u.slice(0, i) : u.replace(/\/+$/, '');
}

/** Server local có sống không — ping /health hoặc /api/status, không tốn lượt AI. */
async function available() {
  const base = baseUrl();
  for (const ep of ['/health', '/api/status']) {
    try {
      const res = await fetch(`${base}${ep}`, {
        signal: AbortSignal.timeout(3000)
      });
      if (res.ok) return true;
    } catch (_) { /* thử endpoint kế tiếp */ }
  }
  return false;
}

/**
 * Ép hội thoại về đúng thứ server hiểu: content là chuỗi, role chỉ user/assistant.
 * role "system" bị server gán nhãn "Assistant:" nên phải gộp vào tin nhắn user,
 * nếu không AI sẽ tưởng chỉ thị hệ thống là lời chính nó đã nói.
 */
function normalizeMessages(messages) {
  const out = [];
  let pending = '';
  for (const m of messages) {
    const role = String(m.role || 'user').toLowerCase();
    if (typeof m.content !== 'string') {
      throw new Error('Local API chỉ nhận content dạng chuỗi (không gửi được ảnh/content-parts).');
    }
    if (role === 'system') { pending = `${pending}\n\n${m.content}`.trim(); continue; }
    let content = m.content;
    if (pending && role === 'user') { content = `${pending}\n\n${content}`; pending = ''; }
    out.push({ role: role === 'assistant' ? 'assistant' : 'user', content });
  }
  if (pending) out.push({ role: 'user', content: pending });
  return out;
}

/**
 * Gửi hội thoại messages[{role,content}] → trả về text trả lời.
 * role hợp lệ: system | user | assistant (system sẽ được gộp vào user).
 */
async function chat(messages) {
  const key = apiKey();
  if (!key) {
    throw new Error('Thiếu LOCAL_API_KEY — đặt trong "data-crawler/.env" hoặc biến môi trường.');
  }
  // Chuẩn hóa TRƯỚC khi vào try, để lỗi sai định dạng không bị báo nhầm thành
  // "không gọi được server".
  const body = JSON.stringify({ model: apiModel(), messages: normalizeMessages(messages) });
  let res;
  try {
    res = await fetch(apiUrl(), {
      method: 'POST',
      headers: { 'content-type': 'application/json', 'x-api-key': key },
      body,
      signal: AbortSignal.timeout(timeoutMs())
    });
  } catch (e) {
    throw new Error(`Không gọi được Local API ở ${apiUrl()} (server local đã chạy chưa?): ${e.message}`);
  }
  if (res.status === 401 || res.status === 403) {
    throw new Error(`Local API từ chối (HTTP ${res.status}) — kiểm tra LOCAL_API_KEY.`);
  }
  if (!res.ok) {
    throw new Error(`Local API ${res.status}: ${(await res.text()).slice(0, 200)}`);
  }
  const data = await res.json();
  const text = data?.choices?.[0]?.message?.content || '';
  if (!text.trim()) throw new Error('Local API trả về nội dung rỗng.');
  return text;
}

/** Tóm tắt trạng thái cho UI (KHÔNG lộ API key). */
async function status() {
  return { url: apiUrl(), model: apiModel(), hasKey: configured(), up: await available() };
}

module.exports = { chat, status, available, configured, apiUrl, apiModel };
