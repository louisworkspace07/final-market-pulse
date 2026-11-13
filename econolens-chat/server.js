require('dotenv').config();
const express = require('express');
const path = require('path');
const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const db = require('./lib/db');
const personas = require('./lib/personas');
const { PROVIDERS, availableProviders } = require('./lib/providers');

const app = express();
const PORT = process.env.PORT || 3333;
const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-me';

app.use(express.json({ limit: '1mb' }));
app.use(express.static(path.join(__dirname, 'public')));

// ---------- Auth ----------
function auth(req, res, next) {
  const token = (req.headers.authorization || '').replace(/^Bearer /, '');
  try {
    req.user = jwt.verify(token, JWT_SECRET);
    next();
  } catch {
    res.status(401).json({ error: 'Vui lòng đăng nhập.' });
  }
}

app.post('/api/register', async (req, res) => {
  const { email, name, password } = req.body || {};
  if (!email || !password || !name) return res.status(400).json({ error: 'Thiếu thông tin.' });
  if (password.length < 6) return res.status(400).json({ error: 'Mật khẩu tối thiểu 6 ký tự.' });
  if (db.findUser(email)) return res.status(409).json({ error: 'Email đã được đăng ký.' });
  const user = db.createUser({ email, name, passwordHash: await bcrypt.hash(password, 10) });
  const token = jwt.sign({ id: user.id, name: user.name, email: user.email }, JWT_SECRET, { expiresIn: '7d' });
  res.json({ token, user: { id: user.id, name: user.name, email: user.email } });
});

app.post('/api/login', async (req, res) => {
  const { email, password } = req.body || {};
  const user = email && db.findUser(email);
  if (!user || !(await bcrypt.compare(password || '', user.passwordHash))) {
    return res.status(401).json({ error: 'Email hoặc mật khẩu không đúng.' });
  }
  const token = jwt.sign({ id: user.id, name: user.name, email: user.email }, JWT_SECRET, { expiresIn: '7d' });
  res.json({ token, user: { id: user.id, name: user.name, email: user.email } });
});

// ---------- Meta ----------
app.get('/api/meta', auth, (req, res) => {
  res.json({
    personas: Object.values(personas).map(({ system, ...p }) => p),
    providers: availableProviders(),
    user: { name: req.user.name, email: req.user.email }
  });
});

app.get('/api/history/:persona', auth, (req, res) => {
  res.json({ history: db.getHistory(req.user.id, req.params.persona) });
});

app.delete('/api/history/:persona', auth, (req, res) => {
  db.clearHistory(req.user.id, req.params.persona);
  res.json({ ok: true });
});

// ---------- Chat ----------
function extractJson(text) {
  // Models sometimes wrap JSON in fences or add prose — extract the outermost object.
  const cleaned = text.replace(/```json|```/g, '').trim();
  try { return JSON.parse(cleaned); } catch {}
  const start = cleaned.indexOf('{');
  const end = cleaned.lastIndexOf('}');
  if (start >= 0 && end > start) {
    try { return JSON.parse(cleaned.slice(start, end + 1)); } catch {}
  }
  return { blocks: [{ type: 'text', markdown: text }] };
}

app.post('/api/chat', auth, async (req, res) => {
  const { message, persona: personaId, provider: providerId, useWebSearch } = req.body || {};
  const persona = personas[personaId];
  const provider = PROVIDERS[providerId];
  if (!message || !persona || !provider) return res.status(400).json({ error: 'Yêu cầu không hợp lệ.' });
  if (provider.envKey && !process.env[provider.envKey]) {
    return res.status(400).json({ error: `${provider.name} chưa được cấu hình. Thêm ${provider.envKey} vào file .env rồi khởi động lại server.` });
  }

  const history = db.getHistory(req.user.id, personaId)
    .slice(-10)
    .map(m => ({ role: m.role, content: m.role === 'assistant' ? JSON.stringify(m.content) : m.content }));

  try {
    const result = await provider.chat(persona.system, [...history, { role: 'user', content: message }], useWebSearch);
    const parsed = extractJson(result.text);

    if (result.sources && result.sources.length > 0) {
      if (!parsed.blocks) parsed.blocks = [];
      const sourceLinks = result.sources.map((s, idx) => `- [${s.title}](${s.uri})`);
      parsed.blocks.push({
        type: 'text',
        markdown: `\n\n---\n**🌐 Nguồn tham khảo (Google Search):**\n` + sourceLinks.join('\n')
      });
    }

    db.appendHistory(req.user.id, personaId, [
      { role: 'user', content: message, ts: Date.now() },
      { role: 'assistant', content: parsed, provider: providerId, ts: Date.now() }
    ]);
    res.json({ response: parsed, provider: providerId });
  } catch (err) {
    console.error('[chat error]', err.message);
    res.status(502).json({ error: 'Lỗi gọi AI: ' + err.message });
  }
});

app.post('/api/clarify', auth, async (req, res) => {
  const { message, provider: providerId } = req.body || {};
  const provider = PROVIDERS[providerId];
  if (!message || !provider) return res.status(400).json({ error: 'Yêu cầu không hợp lệ.' });
  if (provider.envKey && !process.env[provider.envKey]) {
    return res.status(400).json({ error: `${provider.name} chưa cấu hình.` });
  }

  const system = `Nhiệm vụ của bạn là đọc câu hỏi của người dùng và tạo ra 1 đến 3 câu hỏi trắc nghiệm ĐỂ LÀM RÕ NGỮ CẢNH hoặc mục đích của họ trước khi trả lời. Trả về đúng định dạng JSON:
{ "questions": [ { "question": "...", "options": ["A", "B", "C"] } ] }
Không giải thích gì thêm, KHÔNG BAO GỒM BẤT KỲ ĐỊNH DẠNG markdown NÀO NGOÀI json code block.`;

  try {
    const raw = await provider.chat(system, [{ role: 'user', content: message }]);
    const parsed = extractJson(raw.text);
    res.json(parsed);
  } catch (err) {
    console.error('[clarify error]', err.message);
    res.status(502).json({ error: 'Lỗi gọi AI: ' + err.message });
  }
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`EconoLens running at http://localhost:${PORT}`);
    for (const p of availableProviders()) {
      console.log(`  ${p.configured ? '✓' : '✗'} ${p.name} (${p.model})${p.configured ? '' : ` — set ${PROVIDERS[p.id].envKey} in .env`}`);
    }
  });
}

module.exports = app;
