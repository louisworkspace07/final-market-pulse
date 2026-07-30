# PLAN — Pivot "Market Pulse": sản phẩm cho F0, mobile-first, voice, an toàn pháp lý

> Nguồn yêu cầu: phản biện + note định hướng của trần khôi (06/07/2026). Định vị mới:
> **"Giúp F0 không chết vì thiếu thông tin và hiểu biết — đầu tư có cơ sở, không cảm tính."**
> Ràng buộc cứng: **sản phẩm KHÔNG đưa lời khuyên đầu tư** (pháp lý UBCKNN).
> Plan này ĐIỀU CHỈNH sản phẩm hiện có tại `EconoPulse-VN/` (:9999); plan Stock Explorer
> (`docs/plan-stock-explorer.md`) trở thành engine cho triết lý "càng đào càng sâu" — vẫn
> hiệu lực, thực thi sau Phase 2 của plan này.

---

## Phase 0 — Sự thật nền (đã kiểm chứng, không khám phá lại)

**Tài sản hiện có** (chi tiết từng file: `docs/phan-tich-4-du-an.md`):
- 6 trang :9999 (Tổng quan 5 bước, Copilot, Danh mục, Thị trường, Vĩ mô, Hệ sinh thái);
  chuỗi AI task có bằng chứng [N/E/TT/CD]; kênh Gemini CDP→API; S/R+VBP thuần Python.
- 4 dự án thành phần đang chạy: :5000, :5555, :3000, FinPulse (Electron).

**Phản biện phải xử lý (theo thứ tự nguy hiểm):**
1. Pháp lý "tư vấn đầu tư" — kịch bản xác suất theo mã cụ thể có thể bị coi là khuyến nghị.
2. QAOA đang được trình bày như trụ cột nhưng thua classical ở quy mô nhỏ (gap 3,27%).
3. Chưa có business model; 4. nguồn crawl dễ bị chặn; 5. flywheel chưa có bằng chứng.

**Công nghệ voice — Web Speech API (trình duyệt, KHÔNG cần server STT):**
- STT: `webkitSpeechRecognition` (Chrome/Edge), `lang='vi-VN'`, cần internet. Feature-detect,
  không có → ẩn nút mic (KHÔNG polyfill, KHÔNG Whisper server ở MVP — anti-pattern).
- TTS: `speechSynthesis` + `SpeechSynthesisUtterance`, chọn voice `lang` bắt đầu `vi`
  (Windows: Microsoft HoaiMy/An; Chrome: Google Tiếng Việt). Lưu ý đã biết:
  `getVoices()` rỗng lần gọi đầu → phải nghe event `voiceschanged`.

**Anti-patterns toàn plan:**
- CẤM wording ra lệnh hành động: "nên mua/bán/giữ", "khuyến nghị", "verdict đầu tư".
- CẤM thêm framework CSS/JS mới (giữ vanilla + Chart.js) — mobile-first bằng CSS hiện có.
- CẤM xoá module quantum — chỉ HẠ VỊ TRÍ + đổi cách trình bày.
- CẤM nói "AI khuyên rằng" trong TTS — voice chỉ đọc phần "dữ kiện chính".

---

## Phase 1 — Rebrand "Market Pulse" + Lớp an toàn pháp lý (LÀM TRƯỚC TIÊN)

**1a. Rebrand** (tìm-thay có kiểm soát):
- `grep -rn "EconoPulse" gateway/ modules/ README.md docs/` → thay brand hiển thị thành
  **Market Pulse** trong: 7 file HTML (`<h1>`, `<title>`, tagline, footer), `gateway/app.py`
  (print + SERVICES role text), `README.md`. Giữ nguyên tên thư mục `EconoPulse-VN/` (tránh
  gãy đường dẫn launch.json/scripts — đổi thư mục là việc riêng nếu user yêu cầu).
- Tagline mới: "Market Pulse — dữ liệu thật, phân tích có nguồn, cho người mới bắt đầu".

**1b. Lớp pháp lý (compliance layer) — sửa wording toàn hệ:**
- `modules/copilot/engine.py`: system prompt bỏ yêu cầu "verdict" dạng khuyến nghị →
  đổi trường `verdict` thành `tom_tat_du_kien` (tóm tắt dữ kiện, KHÔNG kết luận mua/bán);
  thêm luật: "TUYỆT ĐỐI không dùng từ nên mua/nên bán/khuyến nghị; chỉ mô tả dữ kiện,
  kịch bản và rủi ro". Disclaimer chuẩn (dùng MỌI NƠI, viết 1 lần ở
  `modules/common/legal.py` → import): *"Market Pulse cung cấp thông tin và phân tích
  dữ liệu, KHÔNG phải khuyến nghị đầu tư. Quyết định và trách nhiệm thuộc về nhà đầu tư."*
- `modules/market_overview/orchestrator.py` `_prompt_task3` + deep-dive T5 (khi làm):
  kịch bản đổi nhãn thành "Kịch bản tham khảo từ dữ liệu"; cấm từ khuyến nghị.
- Frontend: hint buttons Copilot đổi từ "Có nên đầu tư FPT?" → "FPT đang có những dữ kiện
  gì đáng chú ý?"; footer mọi trang thêm dòng disclaimer; `js/*.js` render disclaimer từ
  API (không hardcode 2 nơi).
- Kiểm tra tự động: `python scripts/check_legal_wording.py` — grep output mẫu của
  copilot/overview cho blacklist ["nên mua", "nên bán", "khuyến nghị mua", "chốt lời ngay"].

**1c. Hạ vị trí Quantum → "Lab":**
- `portfolio.html`: chuyển section Quantum xuống cuối, đổi heading thành
  "🔬 Lab: Thí nghiệm tối ưu lượng tử (không phải tính năng sản phẩm)".
- Thêm khối văn bản trình bày TRUNG THỰC (copy nguyên văn khung trả lời trần khôi đã soạn):
  gap 3,27% = thua classical ở quy mô nhỏ; giá trị = chứng minh pipeline QUBO + mở đường
  quy mô 1.527 mã/ràng buộc rời rạc nơi brute-force bất khả thi; kèm đoạn trả lời câu hỏi
  "sao không dùng CPLEX/Gurobi".
- (Tuỳ chọn, nếu còn thời gian trước hạn 30/07) `modules/quantum_finance`: thêm chế độ
  "chọn K=10 từ 100 mã VN100 + ràng buộc tỷ trọng bậc rời rạc" để minh hoạ không gian lớn.

**Verify:** grep "EconoPulse" chỉ còn trong tên thư mục/đường dẫn; blacklist wording = 0 hit
trên output thật của copilot (chạy 2 câu hỏi test); trang Danh mục hiện khung Lab với văn
bản trung thực; mọi trang có disclaimer footer.

---

## Phase 2 — Mobile-first + Dashboard F0 "3 câu hỏi lớn"

**2a. Mobile pass toàn site** (`gateway/static/style.css`):
- Breakpoint ≤700px: nav thành thanh cuộn ngang sticky (hoặc bottom-nav 5 icon); mọi
  `.grid-2`, `.pillar-grid`, `.scenario-grid`, `.kpi-row` về 1 cột; touch target ≥44px;
  font body ≥15px; bảng bọc `.table-wrap` cuộn ngang (đã có — rà soát lại từng trang).
- Verify bằng preview resize 375×812 từng trang, chụp màn hình.

**2b. Trang chủ mới cho F0** (thay index.html hiện tại; luồng 5 bước chuyển sang nút
"Phân tích chuyên sâu" trong trang):
- 3 card lớn trả lời 3 câu hỏi F0: **"Thị trường hôm nay thế nào?"** (breadth + khối ngoại
  từ board live, 1 câu tiếng Việt đơn giản), **"Tin gì quan trọng?"** (3 tin CBTT mới nhất,
  mỗi tin 1 dòng), **"Mã tôi quan tâm?"** (ô nhập mã → sang trang chi tiết khi có Stock
  Explorer; tạm thời sang Copilot).
- Triết lý "càng đào càng sâu" trên từng card: mặc định chỉ KẾT LUẬN 1 câu → chạm "Vì sao?"
  mở lý do → chạm tiếp mở số liệu + nguồn (audit trail). Cấu trúc `<details>` lồng 3 tầng,
  không cần JS phức tạp.
- Thuật ngữ có chấm hỏi: span `.term` (VD "khối ngoại", "RSI") → chạm hiện tooltip giải
  thích 1 câu cho F0 (từ điển tĩnh `js/glossary.js`, ~30 thuật ngữ).

**Verify:** trang chủ 375px: 3 card đọc được không cuộn ngang; mọi số trên card truy được
nguồn qua tầng 3; glossary tooltip hoạt động chạm/click.

---

## Phase 3 — Voice: hỏi bằng giọng nói + nghe trả lời

**3a. STT (nói để hỏi):** `js/voice.js` mới:
- `const SR = window.SpeechRecognition || window.webkitSpeechRecognition` — không có → ẩn mic.
- Nút 🎤 cạnh ô hỏi (trang chủ F0 + Copilot): nhấn → `sr.lang='vi-VN'; sr.start()`;
  `onresult` → điền text vào input + tự submit; trạng thái đang nghe (nút đỏ nhấp nháy).
- Lỗi mic/quyền → toast "Không nghe được — hãy gõ câu hỏi" (không chết luồng).

**3b. TTS (đọc trả lời):**
- Sau khi render câu trả lời copilot: nút 🔊 "Nghe tóm tắt" — đọc DUY NHẤT trường
  `tra_loi_don_gian` (Phase 4) hoặc `tom_tat_du_kien` + disclaimer rút gọn cuối
  ("Đây là thông tin tham khảo, không phải khuyến nghị đầu tư").
- Chọn voice: đợi `voiceschanged`, ưu tiên `voice.lang.startsWith('vi')`, fallback voice
  mặc định; nút ⏹ dừng đọc; hủy đọc khi chuyển trang.

**Verify (Chrome):** nói "FPT đang có dữ kiện gì?" → text điền đúng ≥90% và tự chạy; bấm
nghe → giọng Việt đọc tóm tắt; trình duyệt không hỗ trợ (Firefox STT) → nút mic ẩn, không lỗi console.

---

## Phase 4 — Định dạng trả lời 2 tầng cho F0 ("càng đào càng sâu" trong AI)

- `modules/copilot/engine.py` schema thêm 2 trường bắt buộc:
  - `tra_loi_don_gian`: 2-3 câu KHÔNG thuật ngữ, người mới đọc hiểu ngay (nguồn cho TTS + card tầng 1);
  - `thuat_ngu`: [{tu, giai_thich_1_cau}] các thuật ngữ đã dùng ở tầng sâu.
- `js/copilot.js` render: tầng 1 = `tra_loi_don_gian` chữ to; "Đào sâu hơn ▾" mở 3 trụ
  phản biện + kịch bản + audit trail (giữ nguyên cấu trúc hiện có); chips thuật ngữ.
- Deep-dive 5 task per-mã (plan Stock Explorer Phase 3) là tầng sâu nhất — không đổi,
  chỉ thêm `tra_loi_don_gian` vào T5.

**Verify:** hỏi 3 câu test → tầng 1 không chứa từ trong danh sách thuật ngữ; schema validation
pass; TTS đọc tầng 1 dưới 45 giây.

---

## Phase 5 — Cập nhật hồ sơ dự thi (docs/y-tuong-du-thi.md)

Sửa theo đúng 5 phản biện + note:
1. Tên: Market Pulse; định vị F0 ("không chết vì thiếu thông tin"); khác biệt: mobile + voice
   + progressive depth + minh bạch nguồn.
2. Mục PHÁP LÝ mới: ranh giới "cung cấp thông tin/phân tích" vs "khuyến nghị" (không đưa
   lời khuyên; wording đã enforce bằng code — dẫn `scripts/check_legal_wording.py`).
3. Mục QAOA viết lại theo khung trung thực (nguyên văn đoạn trần khôi soạn) + roadmap
   quy mô lớn; trả lời sẵn "sao không CPLEX/Gurobi".
4. Mục business model: B2C freemium F0 → B2B API cho CTCK (như Fiin/Vietstock); thí điểm
   CLB sinh viên = kiểm thử UX, KHÔNG phải bằng chứng thị trường (nói thẳng).
5. Mục rủi ro dữ liệu: nguồn 3 lớp fallback đã code (vnstock → categories.json →
   market.db) + kế hoạch chuyển DataFeed trả phí khi thương mại hoá; flywheel ghi là
   giả thuyết cần kiểm chứng, kèm cách đo (retention, số câu hỏi/tuần).
6. Bảng cạnh tranh: StockGuru/Cú Doha/Mập Thông Thái/VNSC... (từ khảo sát 12:03) + ô
   khác biệt của Market Pulse (trung lập đa nguồn, giải thích được, F0-first, voice).

**Verify:** đối chiếu checklist Điều 5 thể lệ; đọc lại toàn văn không còn chữ "khuyến nghị
đầu tư" ở vai trò tính năng.

---

## Phase 6 — Verification tổng

1. Chạy 5 luồng (gateway + 4 app) → services status xanh; regression 6 trang.
2. Mobile 375px từng trang (screenshot); Lighthouse-style check đơn giản: không lỗi console.
3. Legal sweep: `check_legal_wording.py` trên 5 output AI thật (2 copilot, 1 overview,
   2 deep-dive nếu đã có) = 0 vi phạm.
4. Voice demo end-to-end trên Chrome: hỏi bằng giọng → nghe trả lời.
5. Cập nhật README + memory (`market-pulse-pivot`) nếu có quyết định mới phát sinh.
