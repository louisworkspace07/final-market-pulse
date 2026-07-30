// AI provider abstraction: Claude (Anthropic), Gemini (Google), Grok (xAI),
// Gemini Web (qua LOCAL API tự phát triển).
// Each takes (systemPrompt, messages[{role:'user'|'assistant', content}]) and returns text.

const localApi = require('./local_api');
const { ChromeBrowser } = require('./chrome_bridge');

// Kênh Gemini Web nay đi qua SERVER AI LOCAL (:4000) thay vì tự lái Chrome CDP:
// server local giữ phiên Gemini, EconoLens chỉ gọi HTTP. Đặt LOCAL_API_CDP_FALLBACK=1
// nếu muốn quay lại lái Chrome trực tiếp khi server local hỏng.
const CDP_FALLBACK = ['1', 'true', 'yes'].includes(
  String(process.env.LOCAL_API_CDP_FALLBACK || '').toLowerCase());

// 1 kết nối tới Chrome dùng chung (mở sẵn bằng scripts/launch_chrome.py, port 9222).
// Mỗi request mở 1 tab mới qua withTab() rồi đóng — cho phép chạy song song (cap CDP_MAX_TABS).
let geminiBrowser = null;
let geminiBrowserConnecting = null;

async function getGeminiBrowser() {
  if (geminiBrowser && geminiBrowser.ws && geminiBrowser.ws.readyState === 1) return geminiBrowser;
  if (geminiBrowserConnecting) return geminiBrowserConnecting;
  geminiBrowserConnecting = (async () => {
    const b = new ChromeBrowser(9222);
    const ok = await b.connectBrowser();
    if (!ok) {
      geminiBrowserConnecting = null;
      throw new Error("Không kết nối được Chrome ở cổng 9222. Hãy chạy launch_chrome (Gemini đã đăng nhập).");
    }
    geminiBrowser = b;
    geminiBrowserConnecting = null;
    return b;
  })();
  return geminiBrowserConnecting;
}

const PROVIDERS = {
  claude: {
    id: 'claude',
    name: 'Claude',
    vendor: 'Anthropic',
    model: process.env.CLAUDE_MODEL || 'claude-sonnet-4-6',
    envKey: 'ANTHROPIC_API_KEY',
    async chat(system, messages) {
      const res = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'x-api-key': process.env.ANTHROPIC_API_KEY,
          'anthropic-version': '2023-06-01'
        },
        body: JSON.stringify({
          model: this.model,
          max_tokens: 4096,
          system,
          messages: messages.map(m => ({ role: m.role, content: m.content }))
        })
      });
      if (!res.ok) throw new Error(`Claude API ${res.status}: ${await res.text()}`);
      const data = await res.json();
      return { text: data.content.map(c => c.text || '').join('') };
    }
  },

  gemini: {
    id: 'gemini',
    name: 'Gemini',
    vendor: 'Google',
    model: process.env.GEMINI_MODEL || 'gemini-2.5-flash',
    envKey: 'GEMINI_API_KEY',
    async chat(system, messages, useWebSearch = false) {
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent?key=${process.env.GEMINI_API_KEY}`;
      const payload = {
        systemInstruction: { parts: [{ text: system }] },
        contents: messages.map(m => ({
          role: m.role === 'assistant' ? 'model' : 'user',
          parts: [{ text: m.content }]
        })),
        generationConfig: { maxOutputTokens: 4096, responseMimeType: 'application/json' }
      };
      
      if (useWebSearch) {
        payload.tools = [{ googleSearch: {} }];
      }

      const res = await fetch(url, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(`Gemini API ${res.status}: ${await res.text()}`);
      const data = await res.json();
      const candidate = data.candidates?.[0];
      const text = (candidate?.content?.parts || []).map(p => p.text || '').join('');
      
      const sources = [];
      const chunks = candidate?.groundingMetadata?.groundingChunks || [];
      chunks.forEach(c => {
        if (c.web && c.web.uri) {
          sources.push({ uri: c.web.uri, title: c.web.title || c.web.uri });
        }
      });
      
      return { text, sources };
    }
  },

  grok: {
    id: 'grok',
    name: 'Grok',
    vendor: 'xAI',
    model: process.env.GROK_MODEL || 'grok-3',
    envKey: 'XAI_API_KEY',
    async chat(system, messages) {
      const res = await fetch('https://api.x.ai/v1/chat/completions', {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'authorization': `Bearer ${process.env.XAI_API_KEY}`
        },
        body: JSON.stringify({
          model: this.model,
          max_tokens: 4096,
          messages: [{ role: 'system', content: system }, ...messages]
        })
      });
      if (!res.ok) throw new Error(`Grok API ${res.status}: ${await res.text()}`);
      const data = await res.json();
      return { text: data.choices?.[0]?.message?.content || '' };
    }
  },

  gemini_web: {
    id: 'gemini_web',
    name: 'Gemini Web (Local API)',
    vendor: 'Local',
    model: 'Gemini qua server local',
    envKey: 'LOCAL_API_KEY',
    async chat(system, messages, useWebSearch = false) {
      let finalSystem = system;
      if (useWebSearch) {
        finalSystem += "\n\nCRITICAL: You MUST use Google Search to find real-time, up-to-date information for this query before answering. You MUST also append a \"Nguồn tham khảo:\" section with URLs at the end of your content block.";
      }
      finalSystem = "You are an API server. You MUST respond ONLY with a valid JSON object " +
        "matching the schema below. DO NOT include any conversational text.\n\n" + finalSystem;

      // Server local nhận đúng định dạng OpenAI → giữ nguyên vai trò từng lượt
      // (không phải nhồi cả hội thoại vào 1 prompt như hồi lái CDP trực tiếp).
      const payload = [
        { role: 'system', content: finalSystem },
        ...messages.map(m => ({ role: m.role === 'assistant' ? 'assistant' : 'user',
                                content: m.content }))
      ];

      try {
        return { text: await localApi.chat(payload) };
      } catch (err) {
        if (!CDP_FALLBACK) throw new Error(`Gemini Web (Local API) Error: ${err.message}`);
        // Dự phòng: lái Chrome CDP trực tiếp như trước (cần Chrome :9222 đã login).
        const browser = await getGeminiBrowser();
        const fullPrompt = "[SYSTEM INSTRUCTIONS]\n" + finalSystem + "\n\n" +
          "[CONVERSATION]\n" + messages.map(m => m.role.toUpperCase() + ":\n" + m.content).join("\n\n") + "\n\n" +
          "[REQUIREMENTS]\n" +
          "1. Output ONLY a ```json code block.\n" +
          "2. The JSON must exactly match the schema requested in the system instructions.\n" +
          "3. Ensure all double quotes inside JSON string values are properly escaped as \\\".";
        const res = await browser.withTab(tab => tab.ask(fullPrompt, true));
        if (!res.ok) throw new Error(`Gemini Web Error: ${res.error}`);
        return { text: res.text };
      }
    }
  }
};

function availableProviders() {
  return Object.values(PROVIDERS).map(p => ({
    id: p.id, name: p.name, vendor: p.vendor, model: p.model,
    // gemini_web nay cần LOCAL_API_KEY (server local) — nhưng key có thể nằm ở
    // "data-crawler/.env" dùng chung, nên hỏi client thay vì chỉ nhìn process.env.
    configured: p.id === 'gemini_web' ? localApi.configured() : Boolean(process.env[p.envKey])
  }));
}

module.exports = { PROVIDERS, availableProviders };
