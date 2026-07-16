const WebSocket = require('ws');

const GEMINI_URL = "https://gemini.google.com/app";
const DONE = "@@@END@@@";
const INPUT_SELS = ["rich-textarea .ql-editor", ".ql-editor", 'div[contenteditable="true"]', "textarea", '[role="textbox"]'];
const ANSWER_SELS = [".model-response-text", "message-content", '[class*="model-response"]', ".markdown"];

// Trần số tab CDP chạy song song / mỗi process (tránh Google chặn bot). Chỉnh bằng env.
const MAX_TABS = parseInt(process.env.CDP_MAX_TABS || '3', 10);

function sanitize(t) {
    if (!t) return t;
    t = t.replace(DONE, "");
    t = t.replace(/@+\s*END\s*@+/gi, "");
    return t.trim();
}

// Semaphore đếm đơn giản: giới hạn số tab mở đồng thời.
class Semaphore {
    constructor(max) {
        this.max = max;
        this.count = 0;
        this.queue = [];
    }
    acquire() {
        if (this.count < this.max) {
            this.count++;
            return Promise.resolve();
        }
        return new Promise(resolve => this.queue.push(resolve));
    }
    release() {
        this.count--;
        const next = this.queue.shift();
        if (next) {
            this.count++;
            next();
        }
    }
}

// Kết nối tới 1 Chrome ĐÃ MỞ SẴN (scripts/launch_chrome.py) qua browser endpoint.
// Không launch, không kill Chrome — chỉ tạo/đóng tab qua Target.*.
class ChromeBrowser {
    constructor(port = 9222, log = console.log) {
        this.port = port;
        this.log = log;
        this.ws = null;               // control socket (browser-level)
        this._id = 0;
        this.pendingRequests = new Map();
        this.sem = new Semaphore(MAX_TABS);
    }

    async getVersion() {
        const res = await fetch(`http://127.0.0.1:${this.port}/json/version`);
        if (!res.ok) throw new Error(`/json/version ${res.status}`);
        return await res.json();
    }

    async connectBrowser(timeout = 30) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) return true;
        const start = Date.now();
        let wsUrl = null;
        while (Date.now() - start < timeout * 1000) {
            try {
                const v = await this.getVersion();
                if (v.webSocketDebuggerUrl) { wsUrl = v.webSocketDebuggerUrl; break; }
            } catch { /* Chrome chưa sẵn sàng */ }
            await new Promise(r => setTimeout(r, 600));
        }
        if (!wsUrl) return false;
        return new Promise((resolve) => {
            this.ws = new WebSocket(wsUrl, { maxPayload: 0 });
            this.ws.on('open', () => {
                this.log("[cdp] browser connected:", wsUrl);
                resolve(true);
            });
            this.ws.on('message', (data) => this._onMessage(data));
            this.ws.on('close', () => this._rejectAll("browser socket closed"));
            this.ws.on('error', () => resolve(false));
        });
    }

    _onMessage(data) {
        let msg;
        try { msg = JSON.parse(data); } catch { return; }
        if (msg.id && this.pendingRequests.has(msg.id)) {
            const { resolveReq, rejectReq } = this.pendingRequests.get(msg.id);
            this.pendingRequests.delete(msg.id);
            if (msg.error) rejectReq(new Error(msg.error.message || "cdp error"));
            else resolveReq(msg.result || {});
        }
    }

    _rejectAll(reason) {
        for (const { rejectReq } of this.pendingRequests.values()) {
            try { rejectReq(new Error(reason)); } catch { /* noop */ }
        }
        this.pendingRequests.clear();
    }

    async _sendBrowser(method, params = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            const ok = await this.connectBrowser();
            if (!ok) throw new Error("Không kết nối được Chrome (đã chạy launch_chrome chưa?).");
        }
        this._id++;
        const id = this._id;
        return new Promise((resolveReq, rejectReq) => {
            this.pendingRequests.set(id, { resolveReq, rejectReq });
            this.ws.send(JSON.stringify({ id, method, params }));
        });
    }

    // Tạo 1 tab mới, mở ws RIÊNG tới tab đó, bật Page/Runtime → trả về Tab.
    async openTab(url = GEMINI_URL) {
        const { targetId } = await this._sendBrowser("Target.createTarget", { url });
        const wsUrl = `ws://127.0.0.1:${this.port}/devtools/page/${targetId}`;
        const tab = new Tab(this, targetId, wsUrl, this.log);
        await tab._connect();
        return tab;
    }

    // Mở tab → chạy fn(tab) → luôn đóng tab; giới hạn MAX_TABS song song.
    async withTab(fn, url = GEMINI_URL) {
        await this.sem.acquire();
        let tab = null;
        try {
            tab = await this.openTab(url);
            return await fn(tab);
        } finally {
            if (tab) { try { await tab.close(); } catch { /* noop */ } }
            this.sem.release();
        }
    }

    async disconnect() {
        if (this.ws) { try { this.ws.close(); } catch { /* noop */ } }
        this.ws = null;
    }
}

// Một tab Gemini: ws riêng, bộ đếm id riêng, map pending riêng → cô lập hoàn toàn.
class Tab {
    constructor(browser, targetId, wsUrl, log = console.log) {
        this.browser = browser;
        this.targetId = targetId;
        this.wsUrl = wsUrl;
        this.log = log;
        this.ws = null;
        this._id = 0;
        this.pendingRequests = new Map();
    }

    _connect() {
        return new Promise((resolve, reject) => {
            this.ws = new WebSocket(this.wsUrl, { maxPayload: 0 });
            this.ws.on('open', async () => {
                try {
                    await this._send("Page.enable");
                    await this._send("Runtime.enable");
                    resolve(true);
                } catch (e) { reject(e); }
            });
            this.ws.on('message', (data) => {
                let msg;
                try { msg = JSON.parse(data); } catch { return; }
                if (msg.id && this.pendingRequests.has(msg.id)) {
                    const { resolveReq, rejectReq } = this.pendingRequests.get(msg.id);
                    this.pendingRequests.delete(msg.id);
                    if (msg.error) rejectReq(new Error(msg.error.message || "cdp error"));
                    else resolveReq(msg.result || {});
                }
            });
            this.ws.on('close', () => {
                for (const { rejectReq } of this.pendingRequests.values()) {
                    try { rejectReq(new Error("tab socket closed")); } catch { /* noop */ }
                }
                this.pendingRequests.clear();
            });
            this.ws.on('error', (e) => reject(e));
        });
    }

    _send(method, params = {}) {
        this._id++;
        const id = this._id;
        return new Promise((resolveReq, rejectReq) => {
            this.pendingRequests.set(id, { resolveReq, rejectReq });
            this.ws.send(JSON.stringify({ id, method, params }));
        });
    }

    async evaluate(expr, awaitPromise = false) {
        const r = await this._send("Runtime.evaluate", {
            expression: expr,
            returnByValue: true,
            awaitPromise: awaitPromise,
            userGesture: true
        });
        return r.result?.value;
    }

    async navigate(url) {
        await this._send("Page.navigate", { url });
    }

    async ask(prompt, newChat = true) {
        const marked = prompt + `\n\n---\nKhi đã viết xong TOÀN BỘ, kết thúc bằng đúng MỘT dòng riêng: ${DONE}`;

        try {
            if (newChat) {
                await this.navigate(GEMINI_URL);
                await new Promise(r => setTimeout(r, 2500));
            }
            // Jitter nhỏ tránh nhiều tab gõ cùng lúc → giảm rủi ro bị chặn.
            await new Promise(r => setTimeout(r, 500 + Math.floor(Math.random() * 1500)));

            const ins = `(function(){
                var ss=${JSON.stringify(INPUT_SELS)};
                var el=null;
                for(var i=0;i<ss.length;i++){
                    var e=document.querySelector(ss[i]);
                    if(e){el=e;break;}
                }
                if(!el)return false;
                el.focus();
                try{document.execCommand('insertText',false,${JSON.stringify(marked)});}catch(e){}
                if(el.textContent!==undefined&&el.textContent.trim()===''){
                    el.textContent=${JSON.stringify(marked)};
                    el.dispatchEvent(new Event('input',{bubbles:true}));
                }
                return true;
            })()`;

            const injected = await this.evaluate(ins);
            if (!injected) return { ok: false, error: "Không thấy ô nhập liệu, có thể bạn chưa đăng nhập tài khoản Google." };

            await new Promise(r => setTimeout(r, 900));

            const cnt = `(function(){
                var s=${JSON.stringify(ANSWER_SELS)};
                for(var i=0;i<s.length;i++){
                    var e=document.querySelectorAll(s[i]);
                    if(e.length) return e.length;
                }
                return 0;
            })()`;
            const base_n = (await this.evaluate(cnt)) || 0;

            const sub = `(function(){
                var bs=document.querySelectorAll('button[aria-label],button[mattooltip]');
                for(var i=0;i<bs.length;i++){
                    var b=bs[i];
                    var a=((b.getAttribute('aria-label')||'')+' '+(b.getAttribute('mattooltip')||'')).toLowerCase();
                    if(/(send|gửi|submit)/.test(a)&&!b.disabled){
                        b.click();
                        return 'btn';
                    }
                }
                var el=document.activeElement;
                var ev=new KeyboardEvent('keydown',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true});
                if(el){
                    el.dispatchEvent(ev);
                    el.dispatchEvent(new KeyboardEvent('keyup',{key:'Enter',code:'Enter',keyCode:13,which:13,bubbles:true}));
                }
                return 'enter';
            })()`;
            await this.evaluate(sub);

            const rd = `(function(){
                var s=${JSON.stringify(ANSWER_SELS)};
                for(var i=0;i<s.length;i++){
                    var e=document.querySelectorAll(s[i]);
                    if(e.length){
                        var el = e[e.length-1];
                        var fullText = (el.innerText||'').trim();
                        var code = el.querySelector('pre code') || el.querySelector('code');
                        var jsonText = code ? code.textContent.trim() : fullText;
                        return {n:e.length, t: fullText, j: jsonText};
                    }
                }
                return {n:0,t:'',j:''};
            })()`;

            let last = "", lastJ = "", stable = 0;
            const start = Date.now();
            while (Date.now() - start < 150000) { // 150s timeout
                await new Promise(r => setTimeout(r, 2000));
                const res = (await this.evaluate(rd)) || {};
                const n = res.n || 0;
                const t = res.t || "";
                const j = res.j || "";

                if (n <= base_n) continue;

                if (t.includes(DONE)) {
                    return { ok: true, text: sanitize(j.split(DONE)[0]) };
                }
                if (t.length >= 1 && t === last) {
                    stable++;
                    if (stable >= 3) {
                        return { ok: true, text: sanitize(j) };
                    }
                } else {
                    stable = 0;
                    last = t;
                    lastJ = j;
                }
            }
            return { ok: true, text: sanitize(lastJ) };
        } catch (e) {
            return { ok: false, error: e.message };
        }
    }

    async close() {
        // Đóng tab qua browser control socket, rồi đóng ws của tab.
        try { await this.browser._sendBrowser("Target.closeTarget", { targetId: this.targetId }); } catch { /* noop */ }
        if (this.ws) { try { this.ws.close(); } catch { /* noop */ } }
    }
}

module.exports = { ChromeBrowser, Tab, GEMINI_URL, MAX_TABS };
