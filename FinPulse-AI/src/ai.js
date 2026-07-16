// AI service (main process). Two modes:
//   - 'api'  : calls Claude API directly and returns text.
//   - 'web'  : never calls the network. Returns the compiled prompt so the
//              renderer can copy it to the clipboard for a web chatbox, then
//              the user pastes the answer back.
//
// All prompt-building lives here so both modes share the exact same prompts.

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const GEMINI_BASE = 'https://generativelanguage.googleapis.com/v1beta/models/';

const SYSTEM_BILINGUAL =
  'Bạn là chuyên gia phân tích tài chính. Trả lời chủ yếu bằng tiếng Việt, ' +
  'GIỮ NGUYÊN các thuật ngữ tài chính tiếng Anh (ví dụ: hawkish, yield, ' +
  'liquidity, basis points). Ngắn gọn, có cấu trúc, dùng markdown.';

// ---- Prompt builders -------------------------------------------------------

function articlePrompt(article) {
  return (
    `Phân tích bài báo tài chính sau và cho biết:\n` +
    `1. Tóm tắt 2-3 câu.\n` +
    `2. Tác động tới thị trường (asset class nào, hướng bullish/bearish).\n` +
    `3. Mức độ quan trọng (Low/Medium/High) và lý do.\n` +
    `4. Điều nhà giao dịch nên theo dõi tiếp theo.\n\n` +
    `--- BÀI BÁO ---\n` +
    `Tiêu đề: ${article.title || ''}\n` +
    `Nguồn: ${article.source || ''}\n` +
    `Nội dung: ${article.content || article.snippet || ''}\n` +
    `Link: ${article.link || ''}`
  );
}

function branchPrompt(rootTopic, pathLabels) {
  const currentNode = pathLabels.length
    ? pathLabels[pathLabels.length - 1]
    : rootTopic;
  const fullTrail = [rootTopic, ...pathLabels].join('  →  ');
  return (
    `⚠ CHỦ ĐỀ GỐC (bắt buộc bám sát xuyên suốt): "${rootTopic}".\n\n` +
    `Flow đầy đủ từ đầu đến hiện tại:\n  ${fullTrail}\n\n` +
    `Điểm hiện tại user đang đứng: "${currentNode}".\n\n` +
    `Nhiệm vụ: Đề xuất ĐÚNG 10 nhánh phụ (sub-topic) cụ thể, đa dạng góc nhìn, ` +
    `giúp user đào sâu thêm MỘT BẬC từ điểm hiện tại.\n` +
    `QUY TẮC BẮT BUỘC:\n` +
    `- Mỗi nhánh PHẢI liên quan trực tiếp đến cả chủ đề gốc "${rootTopic}" lẫn điểm hiện tại.\n` +
    `- Không được đề xuất nhánh chung chung hoặc lạc khỏi chủ đề gốc.\n` +
    `- Mỗi nhánh là một cụm ngắn 3-7 từ, cụ thể và actionable.\n\n` +
    `Chỉ trả về JSON thuần, không giải thích, đúng định dạng:\n` +
    `{"branches":["nhánh 1","nhánh 2", ... "nhánh 10"]}`
  );
}

function finalPrompt(rootTopic, pathLabels, extraNote) {
  return (
    `Người dùng đã xây dựng một flow phân tích theo cây nhánh.\n` +
    `Chủ đề gốc: "${rootTopic}".\n` +
    `Flow đã chọn (từ tổng quát → cụ thể):\n` +
    pathLabels.map((l, i) => `  ${i + 1}. ${l}`).join('\n') +
    (extraNote ? `\n\nGhi chú thêm của user: ${extraNote}` : '') +
    `\n\nDựa trên TOÀN BỘ flow trên, hãy đưa ra một bài phân tích tài chính ` +
    `tổng hợp gồm:\n` +
    `- **Bối cảnh & luận điểm chính**\n` +
    `- **Phân tích chi tiết theo flow đã chọn**\n` +
    `- **Rủi ro & yếu tố cần theo dõi**\n` +
    `- **Hàm ý giao dịch / hành động gợi ý**\n` +
    `Trình bày markdown, có heading rõ ràng.`
  );
}

// ---- API caller ------------------------------------------------------------

async function callApi({ apiKey, model, system, prompt, maxTokens = 1500 }) {
  if (!apiKey) throw new Error('Chưa cấu hình API key. Vào Settings để nhập.');
  const res = await fetch(ANTHROPIC_URL, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({
      model: model || 'claude-sonnet-4-6',
      max_tokens: maxTokens,
      system,
      messages: [{ role: 'user', content: prompt }]
    })
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body.slice(0, 300)}`);
  }
  const data = await res.json();
  return (data.content || []).map((b) => b.text || '').join('').trim();
}

async function callGemini({ apiKey, model, system, prompt, maxTokens = 1500 }) {
  if (!apiKey) throw new Error('Chưa cấu hình Gemini API key. Vào Settings để nhập.');
  const m = model || 'gemini-2.0-flash';
  const url = `${GEMINI_BASE}${m}:generateContent?key=${encodeURIComponent(apiKey)}`;
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 45000); // 45s timeout
  
  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      signal: controller.signal,
      body: JSON.stringify({
        system_instruction: { parts: [{ text: system }] },
        contents: [{ role: 'user', parts: [{ text: prompt }] }],
        generationConfig: {
          maxOutputTokens: maxTokens,
          temperature: 0.7
        }
      })
    });
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('API timeout sau 45s, có thể do mạng hoặc Google đang lỗi.');
    throw err;
  } finally {
    clearTimeout(timeoutId);
  }
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`Gemini ${res.status}: ${body.slice(0, 300)}`);
  }
  const data = await res.json();
  const parts = data?.candidates?.[0]?.content?.parts || [];
  return parts.map((p) => p.text || '').join('').trim();
}

// ---- Public API ------------------------------------------------------------

async function run({ task, config, payload }) {
  const { mode, apiKey, model, provider } = config;
  let prompt, system = SYSTEM_BILINGUAL, maxTokens = 1500;

  if (task === 'article') {
    prompt = articlePrompt(payload.article);
  } else if (task === 'branches') {
    prompt = branchPrompt(payload.rootTopic, payload.path || []);
    maxTokens = 1000;
  } else if (task === 'final') {
    prompt = finalPrompt(payload.rootTopic, payload.path || [], payload.note);
    maxTokens = 2500;
  } else {
    throw new Error('Unknown task: ' + task);
  }

  // Web/manual mode: hand the prompt back, no network call.
  if (mode && mode.startsWith('web')) {
    return { mode, prompt, system };
  }

  const text = provider === 'anthropic'
    ? await callApi({ apiKey, model, system, prompt, maxTokens })
    : await callGemini({ apiKey, model, system, prompt, maxTokens });

  // For branches, parse the JSON the model returned.
  if (task === 'branches') {
    return { mode: 'api', branches: parseBranches(text), raw: text };
  }
  return { mode: 'api', text };
}

function parseBranches(text) {
  const clean = String(text || '').replace(/```json/gi, '').replace(/```/g, '').trim();
  try {
    const match = clean.match(/\{[\s\S]*\}/);
    const obj = JSON.parse(match ? match[0] : clean);
    if (Array.isArray(obj.branches)) return obj.branches.map((b) => String(b).trim()).filter(Boolean).slice(0, 10);
  } catch (_) { }
  // Fallback: pull quoted strings, else split lines.
  const quoted = clean.match(/"([^"]{3,})"/g);
  if (quoted && quoted.length >= 3) {
    return quoted.map((q) => q.replace(/"/g, '').trim())
      .filter((s) => s && s.toLowerCase() !== 'branches').slice(0, 10);
  }
  return clean
    .split('\n')
    .map((l) => l.replace(/^[\s\-*\d.)\]\[{}",]+/, '').replace(/[",]+$/, '').trim())
    .filter((s) => s && s.toLowerCase() !== 'branches' && !s.startsWith('{'))
    .slice(0, 10);
}

module.exports = { run, parseBranches };
