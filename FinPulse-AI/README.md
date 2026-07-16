# FinPulse AI ⚡

Desktop app (Electron) gồm 2 phần:

1. **News Dashboard** — tin tài chính đa danh mục (Markets, Crypto, Forex, Economy, Commodities, Business) lấy từ RSS feeds free (CNBC, Yahoo Finance, MarketWatch, CoinDesk, FXStreet, BBC...). **Chuột phải** vào một tin để:
   - 🤖 AI phân tích bài đó
   - 🔗 Mở bài gốc
   - 🌿 Đưa vào AI Interface

2. **AI Interface (cây nhánh)** — nhập 1 chủ đề → AI đề xuất **10 nhánh phụ** → chọn nhánh để đào sâu → lặp lại bao nhiêu lần tùy ý → **Submit** → AI tổng hợp toàn bộ flow đã chọn và trả về bài phân tích hiển thị động bên phải.

## AI: 2 chế độ (đổi trong ⚙️ Settings)
- **Web mode** (mặc định) — không dùng API. App tạo prompt, bạn **Copy** dán vào web chatbox AI, rồi dán câu trả lời lại. Hợp với định hướng "không dùng API".
- **API mode** — nhập Claude API key, mọi bước (sinh nhánh, phân tích) tự động. Model mặc định `claude-sonnet-4-6`.

Output mặc định **song ngữ**: tiếng Việt + giữ thuật ngữ tài chính tiếng Anh.

## Chạy
```bash
npm install
npm start
```

## Cấu trúc
- `main.js` — Electron main, IPC, fetch RSS (tránh CORS), đọc/ghi config.
- `src/feeds.js` — danh sách RSS theo danh mục (thêm/bớt tùy ý).
- `src/ai.js` — build prompt + gọi Claude API (dùng chung cho cả 2 mode).
- `renderer/` — UI (HTML/CSS/JS thuần, không framework).

Config lưu tại thư mục userData của app (`config.json`).
