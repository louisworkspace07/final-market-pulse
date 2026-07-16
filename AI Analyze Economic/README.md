# 📈 EconoLens — Nền tảng AI tìm hiểu & phân tích kinh tế

Web app chatbox AI cho người muốn tìm hiểu kinh tế, với giao diện **render động** theo dữ liệu AI trả về (biểu đồ, bảng, chỉ số, quiz...) như một trang web chuyên nghiệp.

## Tính năng

- 🔐 **Đăng nhập / Đăng ký** (JWT, mật khẩu băm bcrypt) — bắt buộc đăng nhập trước khi dùng
- 👥 **4 nhóm đối tượng**, mỗi nhóm có AI được "tinh chỉnh" riêng:
  - 🎓 **Học sinh / Sinh viên** — giải thích dễ hiểu, ví dụ đời thường, quiz ôn tập
  - 📊 **Nhà phân tích** — số liệu, mô hình kinh tế, kịch bản, biểu đồ kỹ thuật
  - 💼 **Nhà đầu tư** — tác động thị trường, lớp tài sản, rủi ro/cơ hội
  - 🏛️ **Nhà hoạch định chính sách** — công cụ chính sách, trade-off, kinh nghiệm quốc tế
- 🤖 **3 mô hình AI tùy chọn**: Claude (Anthropic), Gemini (Google), Grok (xAI)
- 📊 **Giao diện động**: AI trả về JSON có cấu trúc → frontend render thành biểu đồ (Chart.js), bảng, thẻ chỉ số, timeline, so sánh 2 cột, callout, quiz tương tác, gợi ý câu hỏi
- 💾 Lưu lịch sử hội thoại riêng theo từng người dùng × từng nhóm đối tượng

## Cài đặt & chạy

```bash
  npm install
copy .env.example .env   # rồi điền ít nhất 1 API key
npm start
```

Mở http://localhost:3333 — đăng ký tài khoản và bắt đầu.

> Chỉ cần cấu hình API key cho mô hình bạn muốn dùng; mô hình chưa có key sẽ hiển thị mờ trong sidebar.

## Kiến trúc

```
server.js          Express: auth (JWT), /api/chat, /api/meta, /api/history
lib/providers.js   Lớp trừu tượng AI: Claude / Gemini / Grok (gọi qua fetch)
lib/personas.js    System prompt cho 4 nhóm đối tượng + schema JSON blocks
lib/db.js          Lưu trữ JSON file (users, chats) — không cần cài database
public/            Frontend SPA: index.html, style.css, app.js (block renderer)
data/              Tự tạo khi chạy: users.json, chats.json
```

### Cách giao diện động hoạt động

System prompt yêu cầu AI trả lời bằng JSON `{ "blocks": [...] }` với các loại block: `heading`, `text`, `metrics`, `chart`, `table`, `callout`, `comparison`, `timeline`, `quiz`, `suggestions`. Frontend (`app.js → renderBlock`) đọc từng block và render thành UI tương ứng — nội dung markdown được sanitize bằng DOMPurify.

## Thêm AI provider mới

Thêm 1 entry vào `lib/providers.js` với `id`, `name`, `model`, `envKey` và hàm `chat(system, messages)` trả về text — sidebar sẽ tự hiển thị.
