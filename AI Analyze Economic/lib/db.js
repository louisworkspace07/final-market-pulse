// Ảnh 16 · Kho dữ liệu chat — MỖI USER MỘT FILE RIÊNG.
//
// Trước: toàn bộ lịch sử mọi người dùng nằm chung 1 file chats.json, key
// "userId:persona". Càng dùng file càng phình, mỗi lần ghi phải serialize lại
// TOÀN BỘ dữ liệu của tất cả user, và không thể đưa riêng hồ sơ 1 người cho AI.
// Nay: data/chat/<userId>.json — tách biệt hoàn toàn, ghi chỉ chạm file của
// đúng người đó, và có thêm `profile` để cá nhân hoá câu trả lời.
//
// Vì sao JSON chứ không SQLite: `node:sqlite` trên Node 24 vẫn là API
// EXPERIMENTAL ("might change at any time"), còn better-sqlite3 là native dep
// hay lỗi build trên Windows. Dữ liệu chat mỗi người rất nhỏ (cap 40 tin nhắn),
// JSON per-user đã đủ và không thêm rủi ro. Nâng lên SQLite khi cần truy vấn.
const fs = require('fs');
const path = require('path');

const DATA_DIR = path.join(__dirname, '..', 'data');
const USERS_FILE = path.join(DATA_DIR, 'users.json');
const CHATS_FILE = path.join(DATA_DIR, 'chats.json');     // kho CŨ, chỉ để migrate
const CHAT_DIR = path.join(DATA_DIR, 'chat');

const MAX_MSG = 40;                                        // giữ 40 tin/persona

if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true });
if (!fs.existsSync(CHAT_DIR)) fs.mkdirSync(CHAT_DIR, { recursive: true });

function load(file, fallback) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return fallback; }
}
function save(file, data) {
  // ghi tạm rồi rename → không để lại file hỏng nếu tiến trình chết giữa chừng
  const tmp = file + '.tmp';
  fs.writeFileSync(tmp, JSON.stringify(data, null, 2), 'utf8');
  fs.renameSync(tmp, file);
}

function userFile(userId) {
  // userId do server sinh (u_<base36>) nhưng vẫn chặn ../ cho chắc
  return path.join(CHAT_DIR, String(userId).replace(/[^\w-]/g, '_') + '.json');
}
function loadUser(userId) {
  return load(userFile(userId), { userId, profile: {}, personas: {} });
}
function saveUser(userId, data) {
  save(userFile(userId), data);
}

// ---- migrate 1 lần từ chats.json chung sang từng file ------------------------
function migrateIfNeeded() {
  const flag = path.join(CHAT_DIR, '.migrated');
  if (fs.existsSync(flag) || !fs.existsSync(CHATS_FILE)) return;
  try {
    const old = load(CHATS_FILE, {});
    const byUser = {};
    for (const key of Object.keys(old)) {
      const i = key.lastIndexOf(':');
      if (i < 0) continue;
      const uid = key.slice(0, i), persona = key.slice(i + 1);
      byUser[uid] = byUser[uid] || loadUser(uid);
      byUser[uid].personas[persona] = old[key];
    }
    for (const uid of Object.keys(byUser)) saveUser(uid, byUser[uid]);
    fs.copyFileSync(CHATS_FILE, CHATS_FILE + '.bak');       // giữ bản gốc
    fs.writeFileSync(flag, new Date().toISOString(), 'utf8');
    const n = Object.keys(byUser).length;
    if (n) console.log(`[db] Đã tách lịch sử chat của ${n} người dùng sang data/chat/`);
  } catch (e) {
    console.error('[db] migrate lỗi (giữ nguyên kho cũ):', e.message);
  }
}
migrateIfNeeded();

const db = {
  users: load(USERS_FILE, []),

  findUser(email) {
    return this.users.find(u => u.email === String(email).toLowerCase());
  },
  createUser({ email, name, passwordHash }) {
    const user = {
      id: 'u_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 8),
      email: String(email).toLowerCase(),
      name,
      passwordHash,
      createdAt: new Date().toISOString()
    };
    this.users.push(user);
    save(USERS_FILE, this.users);
    return user;
  },

  getHistory(userId, persona) {
    return loadUser(userId).personas[persona] || [];
  },
  appendHistory(userId, persona, messages) {
    const u = loadUser(userId);
    const arr = u.personas[persona] || (u.personas[persona] = []);
    arr.push(...messages);
    if (arr.length > MAX_MSG) u.personas[persona] = arr.slice(-MAX_MSG);
    saveUser(userId, u);
  },
  clearHistory(userId, persona) {
    const u = loadUser(userId);
    delete u.personas[persona];
    saveUser(userId, u);
  },

  // ---- hồ sơ người dùng: để AI trả lời sát người hỏi (ảnh 16) ----
  getProfile(userId) {
    return loadUser(userId).profile || {};
  },
  setProfile(userId, patch) {
    const u = loadUser(userId);
    u.profile = { ...(u.profile || {}), ...(patch || {}), updatedAt: new Date().toISOString() };
    saveUser(userId, u);
    return u.profile;
  }
};

module.exports = db;
