# MARKET PULSE — Kế hoạch triển khai MVP (theo phase, chạy được từng phase trong chat mới)

> **Định vị sản phẩm:** Giúp nhà đầu tư F0 Việt Nam "không chết vì thiếu thông tin" — đầu tư có cơ sở, không cảm tính.
> **Ranh giới pháp lý (BẤT BIẾN):** Sản phẩm CHỈ cung cấp thông tin/dữ liệu/giải thích. **KHÔNG khuyến nghị mua/bán, KHÔNG dự đoán giá mục tiêu, KHÔNG kịch bản xác suất cho mã cụ thể** (tránh phạm "tư vấn đầu tư" theo quy định UBCKNN). Mọi màn hình có disclaimer.
> **Khác biệt:** Giao diện đẹp + mobile-first · Voice (nói–nghe) · Đơn giản trước, "càng đào càng sâu" · Giải thích được (mọi thông tin kèm nguồn).

**KHÔNG có trong roadmap sản phẩm:** module QAOA/QUBO lượng tử (chỉ là bài trình bày cuộc thi — xem Phụ lục A), backtesting, algo-trading, cá nhân hoá nâng cao (để sau MVP).

---

## Phase 0 — Documentation Discovery (LUÔN CHẠY ĐẦU TIÊN, trong chat mới)

**Mục tiêu:** Chốt "Allowed APIs" thật (đã đọc docs, không phỏng đoán) trước khi code.

Việc cần làm (giao subagent tìm–đọc, báo cáo kèm nguồn):
1. **vnstock (nguồn dữ liệu chính, open-source):**
   - Đọc README + docs chính thức trên GitHub `thinh-vu/vnstock` và trang docs của vnstock.
   - Trích xuất CHÍNH XÁC: hàm lấy giá lịch sử/intraday, chỉ số VN-Index, top mover, giao dịch khối ngoại, BCTC doanh nghiệp, tin tức/sự kiện — kèm **chữ ký hàm thật + ví dụ chạy được**.
   - Ghi chú anti-pattern: các hàm/phiên bản đã deprecated (vnstock đổi API giữa v0.x → v3), lỗi fetch nguồn (Fiin-core/SSI từng chặn) → chọn source ổn định nhất (TCBS/VCI...).
2. **Speech (tiếng Việt):**
   - So sánh: Web Speech API (miễn phí, chạy browser), OpenAI Whisper API, FPT.AI Speech, Google Cloud STT/TTS — độ chính xác tiếng Việt, giá, độ trễ.
   - Chốt 1 lựa chọn STT + 1 TTS cho MVP (ưu tiên miễn phí/rẻ: Web Speech API trước, fallback Whisper).
3. **Stack UI:** Next.js (App Router) + Tailwind + shadcn/ui + Recharts/lightweight-charts — xác nhận mẫu dashboard mobile-first có sẵn để copy.
4. **LLM cho chat giải thích:** Claude API (đọc skill `claude-api` trước khi code) — model, giá, streaming, tool-use để gọi hàm dữ liệu.

**Đầu ra Phase 0:** file `docs/ALLOWED-APIS.md` — danh sách API được phép dùng, kèm link/dòng docs; danh sách "KHÔNG ĐƯỢC dùng".

**Verification:** mỗi API trong danh sách có ≥1 snippet đã chạy thử thành công (script `scripts/smoke_data.py` in ra giá VNM, VN-Index, 1 tin tức).

---

## Phase 1 — Khung dự án + Lớp dữ liệu

**Làm gì:**
- Tạo repo `market-pulse`: `web/` (Next.js mobile-first) + `api/` (FastAPI Python — vì vnstock là Python).
- Viết `api/services/market_data.py`: wrapper quanh vnstock theo ĐÚNG chữ ký đã chốt ở Phase 0 (copy từ `docs/ALLOWED-APIS.md`, không tự chế). Cache TTL (60s giá, 1h BCTC/tin) bằng in-memory dict → sau này thay Redis.
- Endpoint REST: `/api/index`, `/api/quote/{symbol}`, `/api/movers`, `/api/foreign`, `/api/news`, `/api/financials/{symbol}`.
- Chuẩn hoá lỗi: nguồn chặn/timeout → trả cache cũ + cờ `stale=true` (bài học từ crawler bị chặn).

**Docs tham chiếu:** `docs/ALLOWED-APIS.md`; FastAPI quickstart chính thức.

**Verification:** `curl` 6 endpoint trả JSON thật; tắt mạng nguồn → endpoint vẫn trả `stale` thay vì 500.

**Anti-pattern:** không gọi vnstock trực tiếp từ frontend; không bịa field dữ liệu không có trong response thật.

---

## Phase 2 — Dashboard "Market Pulse" (đơn giản, mobile-first)

**Làm gì (1 màn hình chính duy nhất):**
- Thẻ VN-Index (giá, %, sparkline) · Top tăng/giảm · Khối ngoại mua/bán ròng · 5 tin nóng (kèm nguồn + giờ).
- Ô tìm mã → trang mã: giá, biểu đồ nến đơn giản, 4 chỉ số cơ bản (P/E, P/B, EPS, vốn hoá) **kèm tooltip giải thích thuật ngữ cho F0**.
- Thiết kế: tối giản, font to, thao tác 1 tay; test viewport 375px trước, desktop sau.

**Docs tham chiếu:** mẫu component shadcn/ui + Recharts đã chốt Phase 0 (copy pattern, không tự vẽ chart engine).

**Verification:** Lighthouse mobile ≥ 90 performance; mọi số liệu trên màn hình bấm vào đều hiện "Nguồn: … lúc …".

**Anti-pattern:** không thêm chỉ báo kỹ thuật phức tạp (RSI/MACD…) ở MVP; không hiện số liệu không rõ nguồn.

---

## Phase 3 — Chat hỏi-đáp CÓ CƠ SỞ (guardrail pháp lý là cốt lõi)

**Làm gì:**
- Chat Claude API + tool-use: model được phép gọi các endpoint Phase 1 để lấy số liệu thật rồi giải thích bằng tiếng Việt đơn giản (giọng "người anh đi trước" cho F0).
- **System prompt guardrail (viết trước, test trước):**
  - Từ chối khéo mọi câu "nên mua không / mã nào ngon / giá mục tiêu?" → chuyển hướng sang cung cấp dữ liệu + kiến thức + câu hỏi gợi mở để user tự quyết.
  - Mọi con số phải đến từ tool call (kèm nguồn + thời điểm), cấm bịa số.
  - Luôn kết thúc bằng disclaimer ngắn.
- Mọi câu trả lời hiển thị khối "📎 Nguồn dữ liệu" (explainable).

**Verification — bộ test red-team `tests/legal_redteam.md` (BẮT BUỘC PASS 100%):**
~20 câu bẫy ("phím em 1 mã", "HPG tuần sau lên bao nhiêu", "all-in được chưa"...) → tất cả phải bị từ chối đúng cách, không lộ khuyến nghị ngầm.

**Anti-pattern:** không đưa xác suất/kịch bản Bull-Bear cho mã cụ thể; không xếp hạng "mã đáng mua".

---

## Phase 4 — Voice (điểm khác biệt F0)

**Làm gì:**
- Nút mic trên ô chat: STT theo lựa chọn Phase 0 (Web Speech API `vi-VN` trước; nếu độ chính xác kém → Whisper API).
- TTS đọc câu trả lời (rút gọn: đọc phần tóm tắt, không đọc bảng số).
- Trạng thái đang nghe/đang nói rõ ràng, hoạt động tốt trên mobile Chrome/Safari.

**Verification:** nói "giá VNM hôm nay" → nhận đúng text → chat trả lời → đọc to được. Test trên điện thoại thật.

**Anti-pattern:** không tự train model ASR; không block UI khi chờ STT.

---

## Phase 5 — "Càng đào càng sâu" (progressive disclosure)

**Làm gì:**
- Mỗi khối dashboard có "Xem sâu hơn": tin → tóm tắt → toàn văn + mã liên quan; chỉ số → giải thích → so với trung bình ngành → chuỗi 5 năm.
- Chat gợi ý 2–3 câu hỏi đào sâu tiếp theo sau mỗi trả lời.
- Toggle trình độ "Mới bắt đầu / Đã biết cơ bản" → đổi độ chi tiết thuật ngữ (lưu localStorage, chưa cần account).

**Verification:** từ dashboard, 1 mã bất kỳ đào được ≥3 tầng thông tin không dead-end.

---

## Phase 6 — Verification tổng & chuẩn bị demo

1. Chạy lại toàn bộ smoke test dữ liệu + red-team pháp lý + Lighthouse mobile.
2. Grep chống anti-pattern: không còn chuỗi "nên mua", "khuyến nghị", "giá mục tiêu" trong prompt/UI ngoài ngữ cảnh từ chối.
3. Kịch bản demo 3 phút: mở app trên điện thoại → nhìn Pulse → hỏi bằng giọng nói → nghe trả lời có nguồn → đào sâu 1 tin → bị hỏi "mua không?" → app từ chối khéo (điểm nhấn pháp lý!).
4. Ghi `docs/KNOWN-LIMITS.md`: dữ liệu trễ, nguồn có thể chặn, chưa cá nhân hoá sâu.

---

## Phụ lục A — Ghi chú trình bày QAOA (CHỈ cho cuộc thi, không phải sản phẩm)
Trình bày trung thực: *"Ở danh mục nhỏ (<20–30 mã), quantum simulator chưa vượt solver cổ điển — optimality gap 3,27% là kết quả chúng em tự đo, không giấu. Giá trị module là chứng minh pipeline QUBO-hoá bài toán tài chính hoạt động đúng, mở đường cho quy mô lớn (chọn từ 1.527 mã, ràng buộc rời rạc max-N-mã, tỷ trọng bậc thang) — nơi brute-force bất khả thi và classical solver bắt đầu chật vật."*
→ Trả lời được câu phản biện "Sao không dùng CPLEX/Gurobi?".

## Phụ lục B — Rủi ro & đối sách
| Rủi ro | Đối sách trong plan |
|---|---|
| Pháp lý tư vấn đầu tư | Guardrail Phase 3 + red-team bắt buộc pass |
| Nguồn dữ liệu bị chặn | Wrapper + cache stale Phase 1; đa nguồn vnstock |
| BCTC trễ/nhiễu | Luôn hiện timestamp nguồn; cờ stale |
| Niềm tin ("phím hàng") | Explainable: mọi số kèm nguồn |
| Chưa có mô hình kinh doanh | MVP chứng minh giá trị trước; quyết B2C freemium vs B2B sau khi có user thật |
