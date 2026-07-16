# Plan F0 — Market Pulse nhìn bằng mắt người mù tịt chứng khoán

> Rà soát 2026-07-26 trên hệ thống ĐANG CHẠY (`:9999`), dữ liệu thật trong
> `Crawl Data/database/market.db`. Mọi phát hiện dưới đây đều kèm bằng chứng
> quan sát được, không suy đoán.

## 0 · Giả định về F0

F0 = người chưa từng mua cổ phiếu. Khi mở app, trong đầu họ có đúng 5 câu hỏi:

1. Hôm nay thị trường **tốt hay xấu**? (không phải "VN-Index 1.848,25" là bao nhiêu)
2. Công ty này **làm nghề gì**, bán cái gì?
3. Nó **khỏe hay yếu**, so với ai?
4. Đắt hay rẻ — và **đắt so với cái gì**?
5. Tôi **nên xem gì tiếp theo**?

Hệ thống hiện trả lời tốt câu 3 và 4 (cho người đã biết đọc), **bỏ trống câu 1, 2, 5**,
và có vài lỗi làm F0 mất niềm tin ngay trong 10 giây đầu.

---

## 1 · Lỗi PHÁ VỠ NIỀM TIN (P0 — sửa trước mọi thứ khác)

F0 không đánh giá được nội dung phân tích, nên họ đánh giá bằng **độ nhất quán**.
Ba lỗi sau khiến app trông như bị hỏng.

### 1.1 Cùng 1 trang, 2 điểm sức khỏe khác nhau

Trên `/co-phieu/FPT` hiển thị đồng thời:

| Vị trí | Điểm | F-Score | ROE |
|---|---|---|---|
| Card "Sức khỏe doanh nghiệp" | **63** | 4/**7** | 25,7% |
| Card "Hồ sơ doanh nghiệp" | **68** | 5/**8** | 23,59% |

Nguyên nhân: **hai engine độc lập** cùng đổ lên 1 trang —
`d.health` (từ `modules/business_health`, thang F-Score /7) và
`d.ai.data.metrics` (từ `Crawl Data/src/fundamentals.py`, thang /8).
Xác nhận qua `GET /api/stock/FPT`: `health.health_score=63` còn
`ai.data.metrics.health_score=68`.

**Sửa:** chọn 1 nguồn chân lý duy nhất cho "điểm sức khỏe" (đề xuất:
`business_health`, vì nó là engine có công thức công khai trên trang Phương pháp).
Nguồn còn lại đổi nhãn thành "chỉ số AI dùng khi phân tích" hoặc bỏ khỏi UI.
Không được để 2 con số cùng tên trên 1 màn hình.
File: `EconoPulse-VN/gateway/static/js/stock.js` (`#ov-health` ~dòng 449) và
khối "Hồ sơ doanh nghiệp".

### 1.2 Ngày dữ liệu hiện `01/01/1970`

Card sức khỏe ghi "Dữ liệu doanh nghiệp · 01/01/1970".
Nguyên nhân: `stock.js:458` truyền `ts: h.year` — `h.year` là **năm tài chính**
(vd `2025`), nhưng hàm format hiểu là epoch giây → ra 1970.

**Sửa:** đổi thành nhãn "Số liệu năm 2025" thay vì timestamp.

### 1.3 Dữ liệu cũ nhưng không nói là cũ

| Nguồn | Mốc mới nhất | So với hôm nay (26/07) |
|---|---|---|
| `price` | 2026-07-24 | trễ 2 ngày |
| `index_ohlc` | 2026-07-17 | **trễ 9 ngày** |
| Chỉ số trên trang chủ | 07/07/2026 | **trễ 19 ngày** |

Trang chủ ghi "VNINDEX 1.848,25 tính đến 07/07/2026" bằng chữ nhỏ màu xám —
F0 sẽ đọc đó là giá **hôm nay**.

**Sửa:** badge tuổi dữ liệu có màu (xanh ≤1 phiên, vàng 2–5, đỏ >5 phiên) đặt
cạnh chính con số, kèm nút "Cập nhật ngay". Đã có sẵn `data_age_s` trong
`/api/health` — chỉ thiếu phần hiển thị.

### 1.4 Chỉ 37% mã có phân tích AI

576/1.531 mã có `ai_analysis`. F0 bấm đại 1 mã → 63% khả năng gặp trang không có
lời giải thích nào. Hiện không có thông báo gì, chỉ là thiếu section.

**Sửa:** nếu mã chưa có AI → hiện rõ "Mã này chưa được phân tích. [Phân tích ngay]"
+ ước lượng thời gian chờ (~3 phút, xem §5 phần hạ tầng).

---

## 2 · Khoảng trống HIỂU (F0 đọc mà không hiểu)

### 2.1 Câu hỏi số 1 "hôm nay tốt hay xấu" không được trả lời

Trang chủ mở đầu bằng: `VNINDEX · 1.848,25 · Tăng/Đứng/Giảm 246/205/444 ·
Trần/Sàn 32/40 mã kịch biên · Tổng KLGD 564.558.500`.

F0 không biết: chỉ số là gì, 1.848 là cao hay thấp, "trần/sàn" là gì,
"kịch biên" là gì, "độ rộng" là gì, 564 triệu cổ phiếu là nhiều hay ít.

**Sửa:** thêm **1 dòng kết luận bằng tiếng Việt thường** ngay đầu trang, cỡ chữ
lớn nhất màn hình, sinh từ chính dữ kiện đã có (không cần AI):

> "Hôm nay thị trường **nghiêng về giảm** — cứ 10 mã thì 5 mã giảm, 3 mã tăng.
> Thanh khoản ở mức **trung bình** so với 20 phiên gần đây."

Quy tắc thuần số học, không phải khuyến nghị → không đụng `legal.py`.

### 2.2 Từ viết tắt không giải thích ở nơi xuất hiện

Đếm trên trang chủ: `KLGD`, `NN ròng (CP)`, `%phiên`, `T6`, `trần/sàn`, `kịch biên`.
Trên trang cổ phiếu: `P/E`, `P/B`, `ROE`, `RSI 14`, `MA20/MA50`, `Altman Z''`,
`Piotroski F`, `vùng Xám`, `Sổ lệnh 3 bậc`, `CFO`, `LNST`, `Nợ/VCSH`.

Trang `/kien-thuc` có giải thích, và trang `/bat-dau` nói "rê chuột vào gạch chân
chấm" — nhưng **các nhãn viết tắt ở bảng thì không có gạch chân**, và trên điện
thoại thì không rê chuột được.

**Sửa:** (a) viết đủ chữ ở lần xuất hiện đầu ("KLGD" → "Khối lượng giao dịch");
(b) tooltip chuyển sang tap-to-open cho mobile; (c) mỗi card có 1 dòng
"nghĩa là gì" luôn hiện, không cần tương tác.

### 2.3 Bẫy nguy hiểm: top tăng giá toàn cổ phiếu thanh khoản chết

Top tăng giá trang chủ hiện: `CAD +25,00% (KLGD **800** cp)`,
`DPH +14,95% (100 cp)`, `KGM +14,89% (100 cp)`, `GGG +14,29% (100 cp)`.

F0 đọc "tăng 25%" và nghĩ đây là cơ hội. Thực tế khớp 100–800 cổ phiếu — gần như
không mua bán được, và một lệnh nhỏ cũng đẩy giá kịch trần.

**Sửa (ưu tiên cao — đây là chỗ F0 dễ mất tiền nhất):** gắn nhãn cảnh báo
"⚠ thanh khoản rất thấp — 800 cp/phiên" ngay trong dòng, và mặc định **lọc bỏ**
mã có KLGD dưới ngưỡng (vd < 50.000 cp) khỏi bảng Top, có toggle "hiện tất cả".
Đây là dữ kiện, không phải khuyến nghị.

### 2.4 Không có "xem gì tiếp theo"

Hết trang cổ phiếu là hết. Không có bước kế. `/bat-dau` tồn tại nhưng là trang
rời, F0 không tự tìm tới.

**Sửa:** cuối mỗi trang có 1 khối "Bước tiếp theo" gợi ý 2–3 hành động cụ thể
(so sánh với mã cùng ngành / xem mã khỏe nhất ngành / đọc thuật ngữ vừa gặp).

---

## 3 · Dữ liệu ĐÃ CRAWL nhưng UI chưa dùng

Đây là phần "được nhiều nhất với ít công nhất" — dữ liệu đã nằm sẵn trên đĩa.

| Dữ liệu | Đang nằm ở | Trạng thái UI |
|---|---|---|
| **Mô tả doanh nghiệp làm gì** | `companies/<mã>/profile.json` → `overview.company_profile` | **Không hiển thị** |
| Room ngoại / sở hữu NN | cùng file, đã whitelist | có nối API, UI chưa bày rõ |
| Sự kiện DN (cổ phiếu thưởng, niêm yết thêm, GD nội bộ) | bảng `events` — **41.531 dòng** | Card cổ tức báo "chưa có dữ liệu" |
| Tin tức | bảng `news` — **75.732 dòng** | có tab, chưa gắn với biến động giá |
| Giá lịch sử | bảng `price` — **753.225 dòng** | có chart |

### 3.1 Thiếu nghiêm trọng nhất: F0 không biết công ty làm gì

`GET /api/stock/FPT` trả `profile: {}`. Trong khi
`companies/FPT/profile.json` có sẵn:

> "Công ty Cổ phần FPT (FPT) có tiền thân là Công ty Công nghệ Thực phẩm được
> thành lập năm 1988…"

Nguyên nhân: `modules/stock_page/api.py` (~dòng 104) có whitelist
`_SAFE_PROFILE_KEYS` chỉ gồm các trường **số**, không có `company_profile`.

**Sửa:** thêm `"company_profile"` và `"organ_name"` vào whitelist, render thành
card "Doanh nghiệp này làm gì?" đặt **ngay dưới tên mã**, trên mọi chỉ số.

⚠️ **Giữ nguyên việc loại bỏ `rating` / `target_price` / `upside_to_target_percent`.**
File `profile.json` của FPT có `rating: BUY`, `target_price: 90300` — đây là
khuyến nghị của CTCK. Whitelist hiện đang chặn đúng theo `legal.py` (Luật CK 2019
Điều 71). Khi thêm trường mới **không được** nới lỏng chỗ này.

### 3.2 Card cổ tức báo sai "chưa có"

Trang FPT: "Chưa có lịch sử chi trả cổ tức trong DB."
Thực tế `events` của FPT có "Phát hành cổ phiếu — Cổ phiếu thưởng tỉ lệ 15.0%",
"Niêm yết bổ sung 10.260.939 cổ phiếu", "Giao dịch nội bộ"…
Chỉ là `value_per_share` NULL nên bộ lọc cổ tức không bắt được.

**Sửa:** đổi card thành "Sự kiện doanh nghiệp" hiển thị timeline mọi loại sự kiện,
cổ tức chỉ là một loại. Dữ liệu đã có sẵn 41k dòng.

---

## 4 · Trực quan hoá còn thiếu

> ⚠ Phần này và Phase 3 đã được **PHỤ LỤC D** thay thế & mở rộng
> (34 biểu đồ + kiến trúc AI viết lời dẫn). Đọc D trước khi thi công.

Chart **có render** (lightweight-charts + 20 SVG). Vấn đề không phải thiếu chart
mà là **những con số quan trọng nhất lại đang ở dạng chữ**.

| Đang là | Nên là |
|---|---|
| "Phân bố mật độ giá" = danh sách 12 dòng `104,30 → 4,2%` | Biểu đồ cột ngang, tô đậm vùng giá hiện tại |
| "P/E 15,9 — thấp hơn trung vị ngành (18,2)" | Thanh trượt có vạch: mã ↔ trung vị ngành ↔ dải ngành |
| "Điểm sức khỏe 63" (số trần) | Đồng hồ + **so với trung vị ngành** + 3 mức chữ: Yếu / Trung bình / Khỏe |
| "Khối ngoại: mua 213,7k / bán 589,8k" | Cột đối xứng 2 chiều + chuỗi 20 phiên để thấy xu hướng |
| Danh sách mã cùng ngành: `SK 49 · ROE 12,5%` | Kèm sparkline giá 30 phiên |
| Tin tức và giá nằm 2 tab rời | Chấm sự kiện **trên** chart giá — F0 thấy "tin này → giá phản ứng thế này" |

Ưu tiên số 1 trong nhóm này là **chấm sự kiện trên chart giá**: nó trả lời trực
quan câu "vì sao giá chạy", mà dữ liệu (75k tin + 41k sự kiện + 753k dòng giá)
đã có đủ, chỉ thiếu phần nối.

---

## 5 · Kế hoạch thi công

Sắp theo **(giá trị cho F0) ÷ (công sức)**, không theo thứ tự trang.

### Phase 1 — Ngừng chảy máu niềm tin (nửa ngày)

| # | Việc | File |
|---|---|---|
| 1.1 | Gộp về 1 điểm sức khỏe duy nhất | `gateway/static/js/stock.js` |
| 1.2 | Sửa ngày 01/01/1970 | `stock.js:458` |
| 1.3 | Badge tuổi dữ liệu có màu + nút cập nhật | `stock.js`, `home-v3.js` |
| 1.4 | Nhãn "chưa phân tích" + nút chạy AI cho 63% mã còn lại | `stock.js` |

**Nghiệm thu:** mở `/co-phieu/FPT`, mọi con số cùng tên chỉ xuất hiện 1 giá trị;
không còn ngày 1970; thấy rõ dữ liệu cũ mấy phiên.

### Phase 2 — Trả lời 5 câu hỏi của F0 (1–2 ngày)

| # | Việc | File |
|---|---|---|
| 2.1 | Card "Doanh nghiệp này làm gì?" | `modules/stock_page/api.py` (+`company_profile` vào whitelist), `stock.js` |
| 2.2 | Dòng kết luận thị trường bằng tiếng Việt thường ở đầu trang chủ | `home-v3.js` |
| 2.3 | Cảnh báo + lọc mặc định mã thanh khoản thấp ở bảng Top | `home-v3.js`, `market.js` |
| 2.4 | Timeline sự kiện DN thay card cổ tức rỗng | `stock.js`, `modules/stock_page/api.py` |
| 2.5 | Khối "Bước tiếp theo" cuối trang | `stock.js` |

**Nghiệm thu:** người chưa từng mua cổ phiếu mở trang FPT, tự nói được
"công ty này làm gì" và "hôm nay thị trường thế nào" mà không hỏi ai.

### Phase 3 — Trực quan hoá (2–3 ngày)

> ⚠ Đã mở rộng thành **PHỤ LỤC D** — 5 việc dưới đây là tập con của D1 (F7, E1, I3, F7, H1).

| # | Việc |
|---|---|
| 3.1 | Chấm sự kiện/tin trên chart giá (ưu tiên cao nhất) |
| 3.2 | Thanh trượt định giá P/E–P/B so ngành |
| 3.3 | Đồng hồ sức khỏe có mốc trung vị ngành + nhãn chữ |
| 3.4 | Cột ngang cho phân bố mật độ giá |
| 3.5 | Sparkline trong danh sách mã cùng ngành |

### Phase 4 — Ngôn ngữ & mobile (1–2 ngày)

| # | Việc |
|---|---|
| 4.1 | Viết đủ chữ mọi từ viết tắt ở lần xuất hiện đầu |
| 4.2 | Tooltip tap-to-open cho mobile |
| 4.3 | Dịch nốt nhãn tiếng Anh còn sót (`sector: Technology` → "Công nghệ") |
| 4.4 | Gộp `/bat-dau` thành lớp onboarding hiện ở lần mở đầu tiên |

### Hạ tầng chặn Phase 1.4

Phủ sóng AI từ 37% → 100% hiện bị chặn bởi tốc độ Local API:
provider chạy **tuần tự + nghỉ 30s/task**, 1 mã multipass = 5 task ≈ **3 phút**.
955 mã còn thiếu ≈ **48 giờ chạy liên tục**.

Ba hướng, chọn 1 trước khi chạy nền:
1. Giảm `cooldown` trong `API share comunity/server/src/services/dispatcher.service.js:152`.
2. Thêm provider-agent thứ 2 (dispatcher đã hỗ trợ nhiều provider).
3. Hạ multipass 5 lượt → 1 lượt cho nhóm mã ít người xem, giữ 5 lượt cho VN30/VN100.

---

## 6 · Ranh giới không được vượt

Mọi thay đổi trên đều là **mô tả dữ kiện**, không phải khuyến nghị:

- Không thêm "nên mua/bán", không hiện `rating`, `target_price`, `upside`.
- Câu kết luận thị trường (§2.1) chỉ đếm số mã tăng/giảm — không dự đoán.
- Cảnh báo thanh khoản (§2.3) nêu số cổ phiếu khớp — không nói "tránh mã này".
- Giữ nguyên `modules/common/legal.py` và `check_payload` ở mọi output AI.

---

# PHỤ LỤC A · Phân tích AI có đọc được không, và dữ kiện đã đủ chưa?

> Bổ sung 2026-07-26 theo câu hỏi: F0 đọc phân tích AI thì sao, và một trang cổ
> phiếu đã đủ dữ kiện cho **cả F0 lẫn người chuyên nghiệp** chưa.
> Đo trên 576 bản ghi `ai_analysis` thật. **Chưa thi công.**

## A1 · Vấn đề lớn nhất: nhiều mã KHÔNG có phân tích AI, chỉ có bản báo lỗi

Mở `/co-phieu/FPT` — mã tiêu biểu nhất thị trường — phần AI ghi nguyên văn:

> "AI chưa phân tích được (lỗi: Tất cả lượt khía cạnh đều lỗi). Chỉ hiển thị số
> liệu định lượng — chưa có nhận định của chuyên gia AI."

Thống kê 576 bản ghi:

| Tình trạng | Số mã | Tỉ lệ |
|---|---|---|
| `mode=ai_error` (quant-only, không có nhận định) | 58 | 10% |
| **0 khía cạnh** lưu được → tab "Chuyên sâu" trống | **163** | **28%** |
| Không có `key_drivers`/`causes` | 77 | 13% |
| Đủ 4 khía cạnh | 409 | 71% |

Cộng với 955 mã chưa từng chạy AI (§1.4): **F0 bấm ngẫu nhiên 1 mã thì xác suất
đọc được một nhận định AI hoàn chỉnh chỉ khoảng 27%** (409/1.531).

**Việc cần làm:** phân biệt rõ 3 trạng thái trên UI thay vì để lẫn —
"chưa phân tích" / "phân tích lỗi, chỉ có số liệu" / "có phân tích đầy đủ".
Hiện cả ba đều trông na ná nhau nên F0 tưởng hệ thống hỏng.

## A2 · Câu chữ AI hiện tại chưa dịch sang tiếng F0

Bản quant-only sinh ra câu như:

> "Điểm sức khỏe 68/100, F-Score 5/8. ROE 23.59%, biên ròng 14.77%, Nợ/VCSH 0.48."
> "P/E 11.06, P/B 2.88 → hợp lý."

Đây là **đọc số thành lời**, không phải giải thích. F0 vẫn không biết ROE là gì,
23,59% là cao hay thấp, "Nợ/VCSH 0.48" nghĩa là an toàn hay nguy hiểm.

**Việc cần làm:** mỗi câu AI kèm 1 mệnh đề so sánh có mốc —
"ROE 23,6% — cứ 100 đồng vốn chủ tạo ra 23,6 đồng lãi/năm, **cao hơn 90% doanh
nghiệp cùng ngành**". Mốc so sánh (`peer.pct.roe = 90.7`) ĐÃ CÓ trong API,
chỉ chưa đưa vào câu chữ.

Kèm theo: 2 chế độ đọc cho cùng một nội dung — **"Giải thích đơn giản"** (mặc
định cho F0) và **"Bản đầy đủ"** (giữ nguyên thuật ngữ cho người chuyên nghiệp).

## A3 · Mâu thuẫn số liệu ngay giữa các tab (nối tiếp §1.1)

Cùng mã FPT, cùng thời điểm:

| Chỉ số | Tab Tổng quan | Tab Phân tích | `ai_analysis` |
|---|---|---|---|
| Điểm sức khỏe | 63 | 62,5 | **68** |
| F-Score | 4/7 | 4/7 | **5/8** |
| ROE | 25,7% | 25,68% | **23,59%** |
| P/E | **15,9** | — | **11,06** |

P/E lệch 15,9 vs 11,06 là lệch **44%** — đủ để đảo ngược kết luận "đắt hay rẻ".
Nguyên nhân: hai engine tính trên hai kỳ báo cáo khác nhau.

**Việc cần làm:** cùng §1.1 — một nguồn chân lý, và mọi con số phải kèm **kỳ dữ
liệu** ("P/E theo BCTC quý 2/2026") thay vì để trần.

## A4 · Card cổ tức báo "chưa có" trong khi dữ liệu nằm ngay tab bên cạnh

Tab Tổng quan: *"Chưa có lịch sử chi trả cổ tức trong DB."*
Tab Phân tích, cùng lúc, cùng mã:

```
dividends.history = [
  {"date":"2026-05-22","event":"Trả cổ tức bằng tiền mặt","value_per_share":1000.0},
  {"date":"2025-11-19","event":"Trả cổ tức bằng tiền mặt","value_per_share":1000.0}
]
dividends.dividend_yield = 2.97%
```

Đây là lỗi nối dữ liệu thuần túy, không phải thiếu dữ liệu. Gộp chung với §3.2.

## A5 · Đủ cho F0 chưa? — Thiếu 4 thứ, đều không cần crawl thêm

| Thiếu | F0 cần để làm gì | Nguồn đã có |
|---|---|---|
| Doanh nghiệp làm gì | câu hỏi số 2 của F0 | `profile.json` → `company_profile` (§3.1) |
| Quy mô dễ hình dung | "107,8 nghìn tỷ" là to hay nhỏ? | xếp hạng vốn hóa trong ngành — tính được từ `companies` |
| Vì sao giá chạy | nối tin ↔ giá | `news` 75k + `events` 41k + `price` (§4) |
| Nên xem gì tiếp | không bị cụt đường | peer list đã có, chỉ thiếu điều hướng |

## A6 · Đủ cho người chuyên nghiệp chưa? — **Đã tính rồi nhưng KHÔNG nối ra UI**

Đây là phát hiện đáng giá nhất: `Crawl Data` đã tính sẵn 3 bộ chỉ tiêu cao cấp và
lưu trong `ai_analysis.metrics`, nhưng `/api/stock/<sym>/analysis` **không trả về**
(top keys hiện có: cashflow, combo, dividends, dupont, health, leverage, margins,
onebar, peers, radar, roe_roa, valuation).

| Đã tính, chưa hiển thị | Giá trị với dân chuyên | Module |
|---|---|---|
| **`sector_model`** — chỉ tiêu ĐÚNG ngành (ngân hàng: NIM/CIR/LDR/CAR thay vì biên gộp vô nghĩa) | Rất cao. Không có cái này thì mọi so sánh ngân hàng đều sai bản chất | `src/sector_metrics.py` |
| **`earnings_quality`** — CFO vs LNST, accrual: "lãi có tiền thật đỡ không" | Rất cao. Đây là cờ cảnh báo gian lận sổ sách sớm nhất | `src/earnings_quality.py` |
| **`valuation_band`** — P/E, P/B percentile so LỊCH SỬ 3 NĂM CỦA CHÍNH MÃ | Cao. Trả lời "đắt/rẻ so với chính nó", tránh bẫy so trung vị ngành | `src/fundamentals.py` |

Ngoài ra chưa nối: cổ đông lớn / giao dịch nội bộ / lịch sử vốn điều lệ
(`companies/<mã>/ownership/*.json` — P2 đã crawl).

**Kết luận:** với dân chuyên, trang cổ phiếu **chưa đủ** — nhưng thiếu ở tầng
**ống dẫn**, không thiếu ở tầng tính toán. Chi phí bổ sung thấp bất thường.

## A7 · Dọn dẹp pháp lý (P0 — không lộ ra ngoài nhưng phải xử lý)

25/576 bản ghi `ai_analysis` vẫn còn `investment_rating` với giá trị khuyến nghị:
`'tích lũy'` (15), `'theo dõi'` (8), `'giảm tỷ trọng'` (2) — toàn bộ là bản ghi cũ
sinh từ kênh `mode=gemini` trước khi vá.

Đã kiểm chứng: **API hiện đang chặn** — `/api/stock/ACE` trả `investment_rating: None`.
Nên đây **chưa phải rò rỉ**, nhưng là bom hẹn giờ: bất kỳ export/endpoint mới nào
đọc thẳng `ai_analysis` đều làm lộ.

**Việc cần làm:** (1) script xoá field trong 25 bản ghi; (2) thêm test chặn
regression trong `Crawl Data/tests/`; (3) chạy `check_payload` cả lúc GHI chứ
không chỉ lúc trả về.

## A8 · Bổ sung vào kế hoạch

| Phase | Thêm việc |
|---|---|
| **1 (P0)** | A7 dọn 25 bản ghi `investment_rating` + test chặn regression |
| **1 (P0)** | A3 thống nhất số liệu giữa 3 tab + gắn kỳ dữ liệu vào mọi chỉ số |
| **2** | A1 phân biệt 3 trạng thái AI; A4 nối lại card cổ tức |
| **2** | A2 chế độ "Giải thích đơn giản" / "Bản đầy đủ" |
| **3** | **A6 nối `sector_model` + `earnings_quality` + `valuation_band` ra tab Chuyên sâu** — đòn bẩy cao nhất cho nhóm chuyên nghiệp |
| **3** | Nối ownership (cổ đông lớn, giao dịch nội bộ) |

---

# PHỤ LỤC B · Kiểm kê: AI thực sự được cho ăn bao nhiêu dữ liệu?

> Bổ sung 2026-07-26. Đo bằng cách **sinh ra đúng prompt thật** của mã FPT
> (`analyzer._build_aspect_prompts`) rồi đếm, không đọc code suy đoán. **Chưa sửa.**

## B1 · Con số tổng

| | |
|---|---|
| Dữ liệu 1 mã có trên đĩa | **952 KB** (chưa kể 3.206 dòng `financials` trong DB) |
| Thực sự đưa vào prompt | **13.747 ký tự ≈ 3.400 token** (cả 5 lượt cộng lại) |
| **Tỉ lệ dùng** | **~1,4%** |

Chi tiết 5 lượt: financial 2.748 · valuation 2.620 · growth 2.138 · risk 4.302 ·
overall 1.939 (ký tự).

## B2 · ĐÃ cho vào

| Khối | Nội dung | Độ phủ |
|---|---|---|
| Chỉ số định lượng | DT/LNST kỳ mới nhất + QoQ/YoY, biên gộp–ròng–EBIT, ROE/ROA/ROIC, P/E P/B EV/EBITDA, Nợ/VCSH, health score, F-Score | đầy đủ (đã tính sẵn) |
| Mô hình ngành | `sector_model` — NIM/CIR/LDR nếu là ngân hàng | đầy đủ |
| Chất lượng lợi nhuận | `earnings_quality` — CFO vs LNST, accrual | đầy đủ (gửi 2 lần: lượt financial + risk) |
| Bảng cân đối | 8 chỉ tiêu | **8 / 109 chỉ tiêu** |
| Dải định giá | `valuation_band` percentile 3 năm | đầy đủ |
| So sánh ngành | trung vị P/E, P/B, ROE, biên ròng, Nợ/VCSH | đầy đủ |
| Vĩ mô | chỉ số thị trường, USD/VND, GDP/CPI/lãi suất | đầy đủ |
| Tin & sự kiện | 18 mục top theo trọng số | **18 / 105 mục** |
| Kỹ thuật giá | 8 con số tóm tắt (momentum 1M/3M/6M/1Y, đỉnh–đáy 52T, biến động) | **8 số / 497 phiên** |
| Sở hữu | 5 cổ đông lớn, khối ngoại 1 phiên, vốn điều lệ | **5 / 73 cổ đông** |

## B3 · CHƯA cho vào

| Dữ liệu bỏ trống | Quy mô | Vì sao đáng tiếc |
|---|---|---|
| **Doanh nghiệp làm gì** (`company_profile`) | 1 đoạn | **AI đang phân tích FPT mà không biết FPT bán gì.** Đã xác minh: đoạn mô tả KHÔNG có mặt trong bất kỳ prompt nào |
| **Chuỗi nhiều năm** | 2022–2024 | Prompt chỉ có kỳ mới nhất + YoY. Đếm từ khoá năm trong prompt: 2022→0, 2023→0, 2024→0 lần. AI **không thấy xu hướng 3–5 năm**, chỉ thấy 1 lát cắt |
| Kết quả kinh doanh nguyên bản | 400 bản ghi / 25 chỉ tiêu | 0 dòng vào prompt |
| Lưu chuyển tiền tệ nguyên bản | 656 bản ghi / 41 chỉ tiêu | 0 dòng vào prompt |
| Bảng cân đối phần còn lại | 101 / 109 chỉ tiêu | phải thu, người mua trả trước, vay ngắn/dài hạn chi tiết… |
| `ratio.json` | 406 bản ghi / 58 chỉ tiêu | có sẵn trailing EPS, các vòng quay… |
| Chuỗi giá | 497 phiên | AI không tự đọc được mẫu hình giá |
| Tin còn lại | 87 / 105 mục | |
| Lãnh đạo & công ty con | 9 lãnh đạo, 14 cty con | quản trị, cấu trúc tập đoàn |
| Cổ đông còn lại + giao dịch nội bộ | 68 cổ đông | |
| Lịch sử cổ tức | có trong `events` | |
| Room ngoại / sở hữu nhà nước | có trong `profile.json` | |
| Lịch sử khối ngoại | `foreign_history.jsonl` | prompt chỉ có **1 phiên** |

## B4 · ⚠ Đang bơm 1 dữ kiện SAI vào AI

Prompt gửi: `- Vốn điều lệ (mới nhất): 20 tỷ`

Thực tế FPT có 1.714.326.422 cổ phiếu → vốn điều lệ ≈ **17.143 tỷ**.
Sai **857 lần**.

Nguyên nhân: `_ownership_block` lấy `capital_history[-1]` coi như "mới nhất",
nhưng mọi bản ghi trong `capital_history.json` đều có `date: "NaT"` nên danh sách
không hề được sắp theo thời gian — phần tử cuối lại chính là vốn điều lệ **thuở
mới thành lập**.

Đây là loại lỗi nguy hiểm nhất: AI không có cách nào biết con số sai, nên sẽ
lập luận trên nền dữ kiện sai và nói rất tự tin.

**Sửa:** bỏ qua bản ghi `date="NaT"`, hoặc suy vốn điều lệ từ
`issue_share × mệnh giá 10.000đ`, hoặc bỏ hẳn dòng này khỏi prompt nếu không xác
định được kỳ.

## B5 · Đề xuất ưu tiên (Phase 3)

Ngân sách hiện chỉ ~3.400 token/mã — rất rẻ so với mức Gemini chịu được. Có thể
tăng gấp 5–10 lần mà vẫn an toàn. Thứ tự nên thêm:

1. **B4 sửa lỗi vốn điều lệ** — đang làm hỏng chất lượng suy luận, sửa gần như không tốn gì.
2. **Mô tả doanh nghiệp** (~1.000 ký tự) — cho AI biết đang phân tích cái gì. Rẻ nhất, tác động lớn nhất.
3. **Chuỗi 5 năm DT/LNST/biên/CFO** (~600 ký tự) — chuyển AI từ "chụp ảnh 1 kỳ" sang "đọc xu hướng". Dữ liệu đã có trong `combo` của gateway.
4. **Bảng cân đối mở rộng 8 → ~25 chỉ tiêu** (~800 ký tự) — thêm phải thu, tồn kho, vay ngắn/dài hạn.
5. **Lịch sử cổ tức + room ngoại** (~300 ký tự).
6. Nâng tin từ 18 → 30 mục, kèm ngày để AI nối tin với biến động giá.

Ước tính sau khi thêm: ~8.000–9.000 token/mã, vẫn dưới ngưỡng an toàn, và độ phủ
dữ liệu tăng từ 1,4% lên khoảng 5–6%.

---

# PHỤ LỤC C · So sánh quý trước / năm trước — moi thêm gì từ market.db?

> Trả lời câu hỏi: *"dựa vào database thêm được những dữ liệu gì vào prompt không —
> kiểu so sánh với quý trước hay với năm trước?"*
> Toàn bộ số liệu dưới đây đo trực tiếp trên `Crawl Data/database/market.db`
> ngày 2026-07-27, KHÔNG crawl thêm một dòng nào.

## C0 · Kho dữ liệu hiện có trong market.db

| Bảng | Quy mô | Đang dùng cho prompt? |
|---|---|---|
| `financials` — 4 statement | 1.531 mã · `income_statement` 25 chỉ tiêu, `balance_sheet` 109, `cash_flow` 41, `ratio` 58 | chỉ vài chỉ số tính sẵn + 8 dòng BCĐKT |
| `price` | 1.551 mã · 753.225 phiên (2024-01 → 2026-07) | 8 con số tóm tắt |
| `index_ohlc` | VNINDEX (2014→), VN30, HNXINDEX — 1.997–3.014 phiên | **0** |
| `events` | 41.000+ bản ghi, 15 loại sự kiện | vài mục lẫn trong "tin tức" |
| `news` | 75.732 tin / 1.531 mã | 18 mục |
| `companies.sector` | 1.531/1.531 mã có ngành · 19 ngành | trung vị ngành |
| `market_news` | 57 tin toàn thị trường | **0** |

### Bộ kỳ báo cáo thực tế (đây là mấu chốt)

Chữ ký kỳ phổ biến nhất — **1.011/1.531 mã**:

```
2022 · 2023 · 2024 · 2025 · 2025-Q2 · 2025-Q3 · 2025-Q4 · 2026-Q1
```

Tức là: **4 năm liền + 4 quý liền, nhưng THIẾU đúng quý cùng kỳ năm ngoái**
(2025-Q1). Đó chính là lý do prompt hiện tại gần như không bao giờ có dòng
"YoY quý".

Đã kiểm chứng số quý là **rời rạc, không lũy kế**: FPT Q1+Q2+Q3+Q4 năm 2025
= 70.112,8 tỷ = đúng bằng FY2025 (tỷ lệ 1,0000). Điều này mở ra C1.

---

## C1 · 🔴 Ưu tiên cao nhất: khôi phục "so cùng kỳ năm ngoái" cho 1.052 mã

**Hiện trạng.** `fundamentals.py:97` tính `yoy_q = _yoy(rev_q, 4)` — cần 5 quý
liên tiếp. Đo thật: **chỉ 17/1.531 mã** đủ điều kiện. 1.514 mã còn lại, prompt
gửi cho AI dòng này mà không có "YoY quý":

```
- Doanh thu (quý 2026-Q1): 12.480 tỷ | QoQ: -38,3% | YoY năm: +11,6%
```

**Cách khôi phục.** Vì quý rời rạc và có sẵn số cả năm:

```
Q1(y-1) = FY(y-1) − Q2(y-1) − Q3(y-1) − Q4(y-1)
```

Đo trên toàn thị trường:

| Tình huống | Số mã |
|---|---|
| Có sẵn quý cùng kỳ trực tiếp | 17 |
| **Suy ra được bằng FY − 3 quý** | **1.052** |
| Không làm được (thiếu quý hoặc thiếu FY) | 414 |

→ Số mã có "YoY quý" đi từ **17 → 1.069** (~93% số mã có dữ liệu quý).

**VÌ SAO QUAN TRỌNG — con số này mới là điều đáng giật mình.** So sánh phân bố
tăng trưởng doanh thu 2026-Q1 trên 1.03x mã:

| | P25 | Trung vị | P75 | % mã âm |
|---|---|---|---|---|
| QoQ (Q1 so Q4) — **đang gửi cho AI** | −35,6% | **−10,9%** | +5,1% | **67,5%** |
| YoY cùng quý (Q1/2026 so Q1/2025 suy ra) | −5,9% | **+11,8%** | +35,4% | 33,2% |

Quý 4 là quý cao điểm của phần lớn doanh nghiệp Việt Nam, nên Q1 so Q4 **âm ở
2/3 thị trường vì mùa vụ, không phải vì kinh doanh xấu đi**. Prompt hiện tại
đưa đúng con số đó vào và không kèm bất kỳ cảnh báo mùa vụ nào → AI đang bị
**đẩy hệ thống về phía kết luận "suy giảm"** cho hầu hết mã. Đây là sai lệch
nghiêm trọng nhất phát hiện được cho tới giờ, còn nặng hơn lỗi vốn điều lệ ở B4
vì nó ảnh hưởng 2/3 thị trường chứ không phải 1 dòng dữ kiện.

**Việc cần làm**
- `fundamentals.py`: thêm `_derive_missing_quarter()` cho `income_statement` và
  `cash_flow` (chỉ áp dụng cho chỉ tiêu **dòng chảy**, tuyệt đối không áp cho
  `balance_sheet` vì đó là số dư thời điểm).
- Gắn cờ nguồn: `yoy_q_source: "reported" | "derived"`; prompt ghi rõ
  `(suy ra từ BCTC năm)` để AI không coi là số công bố.
- `_metrics_block`: khi có `yoy_q`, đặt nó **trước** QoQ và thêm một câu
  ngắn — *"QoQ Q1 so Q4 chịu ảnh hưởng mùa vụ, ưu tiên đọc YoY cùng quý."*

Chi phí prompt: ~+150 ký tự. Đây là thay đổi rẻ nhất mà tác động lớn nhất trong
toàn bộ tài liệu này.

---

## C2 · Chuỗi 4 năm — đã nằm sẵn trong RAM rồi vẫn bị vứt đi

`fundamentals.py:98-100` đã tính `trend_q` (8 kỳ gần nhất) và `trend_periods`,
nhưng `_metrics_block` **không hề dùng**. Dữ liệu đã tính, đã ở trong biến `m`,
chỉ việc in ra.

Coverage đo được:

- **1.459/1.531 mã** có đủ BCĐKT 4 năm 2022–2025
- **1.472/1.531 mã** có đủ `ratio` 4 năm 2022–2025 (58 chỉ tiêu/kỳ)
- **1.516 mã** có ≥4 kỳ năm ở `income_statement`

Đề xuất khối mới — dạng bảng, AI đọc xu hướng tốt hơn nhiều so với 1 lát cắt:

Đề xuất khối mới (số dưới đây là **số thật của FPT** lấy từ market.db, không phải
ví dụ bịa):

```
### CHUỖI 4 NĂM + 3 QUÝ GẦN NHẤT (tỷ đồng)
Kỳ        DT       LNST    Biên gộp  Biên ròng  Nợ/VCSH
2022      44.010   6.491     39,0%     14,7%     1,04
2023      52.618   7.788     38,6%     14,8%     1,01
2024      62.849   9.427     37,7%     15,0%     1,02
2025      70.113  11.232     36,9%     16,0%     1,01
2025-Q3   17.205   2.902     37,9%     16,9%     0,93
2025-Q4   20.225   2.995     34,8%     14,8%     1,01
2026-Q1   12.480   2.477     34,0%     19,8%     0,71
```

Chỉ nhìn bảng này đã thấy hai chuyện mà prompt hiện tại **không thể hiện ra được**:

1. **Biên gộp bào mòn liên tục 4 năm**: 39,0% → 38,6% → 37,7% → 36,9%, và quý
   gần nhất chỉ còn 34,0% — thấp nhất chuỗi. AI hiện chỉ thấy đúng một con số
   biên gộp của kỳ mới nhất, không có gì để so.
2. **Biên gộp thấp nhất nhưng biên ròng cao nhất** ở 2026-Q1 (34,0% vs 19,8%) —
   dấu hiệu lợi nhuận đến từ ngoài hoạt động cốt lõi. Đây đúng là loại câu hỏi
   người phân tích chuyên nghiệp muốn AI đặt ra, và hiện nó không có dữ liệu để
   đặt.

Lưu ý: không đưa ROE vào dòng quý (ROE quý chưa năm hóa, để cạnh ROE năm sẽ gây
hiểu nhầm). Chi phí: ~600–700 ký tự.

---

## C3 · TTM — bốn quý gần nhất (1.127 mã làm được)

Có ≥4 quý liên tiếp: **1.127 mã**. Từ đó tính được:

- **DT/LNST TTM** = tổng 4 quý gần nhất → phản ánh 12 tháng vừa qua, không bị
  lệch như số FY2025 đã cũ 7 tháng.
- **EPS TTM → P/E TTM**. P/E hiện tại trong prompt lấy từ `ratio` theo kỳ năm;
  với mã có Q1 đột biến thì P/E năm và P/E TTM lệch rất xa.
- **TTM so TTM cùng kỳ** — thước đo tăng trưởng mượt nhất, sạch mùa vụ hoàn toàn.

Chi phí: ~120 ký tự (3 dòng).

---

## C4 · So với VNINDEX — bảng `index_ohlc` chưa được dùng một lần nào

Đã kiểm: FPT khớp **492/497 phiên** với `index_ohlc.VNINDEX` theo ngày. Vậy tính
được ngay, không cần nguồn mới:

- **Sức mạnh tương đối (RS)**: mã +8% trong 3 tháng khi VNINDEX +15% là **thua
  thị trường 7 điểm** — hiện AI chỉ thấy "+8%" và rất dễ khen.
- **Beta ~250 phiên**: đo mức độ nhạy với thị trường (dữ kiện rủi ro, không phải
  khuyến nghị).
- **Tương quan & max drawdown** so với chỉ số cùng giai đoạn.

Bổ sung vào khối *Kỹ thuật giá* của lượt **risk**:

```
- So VNINDEX: 1M -2,1 điểm | 3M -7,0 điểm | 1Y +12,4 điểm (RS)
- Beta 250 phiên: 1,18 | Sụt sâu nhất 1 năm: -24,3% (VNINDEX -11,0%)
```

Chi phí: ~200 ký tự.

---

## C5 · Cổ tức — 6.414 bản ghi/1.047 mã, prompt chỉ có 1 con số "tỷ suất"

Bảng `events` có `Trả cổ tức bằng tiền mặt` kèm `value_per_share`. Từ đó dựng
được lịch sử chi trả:

```
- Cổ tức tiền mặt: 2026-05-22: 1.000đ/CP | 2025-11-19: 1.000đ/CP
  → 2.000đ/năm, tỷ suất ~3,2% theo giá hiện tại; đã trả đều 4 năm liên tục
```

Tính đều đặn của cổ tức là dữ kiện quan trọng với nhóm F0 lẫn nhà đầu tư thu
nhập, và nó cũng vá luôn lỗi §3.2 (card cổ tức báo "chưa có" trong khi dữ liệu
nằm ngay bảng bên cạnh). Chi phí: ~150 ký tự.

---

## C6 · Sự kiện doanh nghiệp — đang bị trộn lẫn vào "tin tức"

15 loại sự kiện, trong đó có những loại làm thay đổi cấu trúc vốn mà AI nên tách
riêng khỏi tin báo chí:

| Loại | Toàn thị trường |
|---|---|
| Giao dịch nội bộ (cá nhân/tổ chức/người liên quan) | 18.014 |
| Phát hành cổ phiếu | 2.750 |
| Niêm yết thêm | 1.420 |
| ĐHĐCĐ bất thường | 1.135 |
| Chuyển sàn / tạm dừng niêm yết | 375 |

Đề xuất tách một khối **SỰ KIỆN PHA LOÃNG & QUẢN TRỊ** riêng cho lượt *risk*,
kèm ngày, thay vì để lẫn trong danh sách 18 tin xếp theo trọng số. Phát hành cổ
phiếu + niêm yết thêm là dữ kiện pha loãng EPS — AI hiện gần như không nhìn thấy.

Chi phí: ~250 ký tự.

---

## C7 · Xếp hạng trong ngành thay vì chỉ trung vị ngành

`companies.sector` phủ **1.531/1.531 mã**, 19 ngành. Prompt hiện chỉ đưa *trung
vị ngành* — AI biết "ROE ngành ≈ 12%, công ty 28%" nhưng không biết 28% là hạng
mấy trong bao nhiêu công ty.

```
- Xếp hạng ngành Công nghệ (42 cty): ROE #3/42 (P93) | Biên ròng #5/42 (P88)
  | P/E #31/42 (P26) | Nợ/VCSH #18/42 (P57)
```

Xếp hạng percentile là **mô tả vị trí**, không phải khuyến nghị — vẫn nằm trong
ranh giới `legal.py`. Chi phí: ~150 ký tự.

---

## C8 · Tổng hợp & thứ tự thi công

| # | Hạng mục | Mã hưởng lợi | Chi phí prompt | Sửa ở đâu |
|---|---|---|---|---|
| C1 | **YoY cùng quý suy ra + cảnh báo mùa vụ** | 1.052 | +150 | `fundamentals.py`, `analyzer._metrics_block` |
| B4 | Sửa lỗi vốn điều lệ (Phụ lục B) | toàn bộ | 0 | `analyzer._ownership_block` |
| C2 | Chuỗi 4 năm + 4 quý (đã tính sẵn) | 1.459 | +650 | `analyzer._metrics_block` |
| C3 | TTM & P/E TTM | 1.127 | +120 | `fundamentals.py` |
| C5 | Lịch sử cổ tức | 1.047 | +150 | khối mới, đọc `events` |
| C4 | RS/Beta so VNINDEX | ~1.500 | +200 | `analyzer._price_block` |
| C7 | Xếp hạng percentile trong ngành | 1.531 | +150 | `analyzer._peer_block` |
| C6 | Tách sự kiện pha loãng & quản trị | ~1.400 | +250 | khối mới, đọc `events` |

Cộng dồn **~+1.670 ký tự ≈ +420 token/lượt**. Gộp với các đề xuất ở B5, tổng
ngân sách rơi vào **~9.000–10.000 token/mã** — vẫn thấp hơn nhiều so với ngưỡng
Local API chịu được.

**Nguyên tắc khi thi công**
1. Mọi số **suy ra** phải gắn nhãn `(suy ra từ BCTC năm)` trong prompt — không
   được để AI tưởng là số công bố.
2. Không suy ra quý cho `balance_sheet` (số dư thời điểm, phép trừ vô nghĩa).
3. Ngưỡng kiểm tra: nếu `|FY − Σ4 quý| / FY > 2%` thì coi là dữ liệu không nhất
   quán, bỏ qua phép suy ra thay vì gửi số sai.
4. Toàn bộ khối mới đều là **mô tả dữ kiện**, không kèm hàm ý mua/bán — chạy
   `check_payload()` như cũ.

**Chưa thi công** — theo yêu cầu "vẫn làm trong plan chưa sửa vội".

---

## C9 · 🔴 LỖI ĐANG CHẶN THI CÔNG: server Local API giới hạn prompt 10.000 ký tự

Phát hiện khi chạy thử thật 5 lượt cho FPT ngày 2026-07-27.

**Nguồn gốc.** `API share comunity/server/src/models/Task.js:18`:

```js
prompt: { type: String, required: true, maxlength: 10000 }
```

Mongoose chặn ở tầng model → server trả `HTTP 400 Validation Error`.

**Vì sao mới lộ ra.** `LocalApiSession` (thêm trong đợt chuyển sang Local API)
phát lại toàn bộ lịch sử mỗi lượt để giữ ngữ cảnh, mà server lại **gộp mọi
message thành MỘT chuỗi `prompt`**. Payload cộng dồn qua từng lượt:

| Lượt | Lịch sử | Prompt | Gửi đi | Kết quả |
|---|---|---|---|---|
| 1 financial | 0 | 2.748 | 2.893 | ✅ 28,7s |
| 2 valuation | 4.748 | 2.620 | 7.325 | ✅ 27,1s |
| 3 growth | 9.368 | 2.138 | **10.992** | ❌ 400 |
| 4 risk | — | 4.302 | **13.156** | ❌ 400 |
| 5 overall | — | 2.926 | **11.780** | ❌ 400 |

429 mã chạy thành công trước đó (2026-07-23 → 25) đều là **trước** khi có
session — mỗi lượt gửi riêng nên luôn dưới 10.000.

**Làm hỏng thêm ở tầng client.** `local_api.ask()` coi mọi mã lỗi ngoài 401/403
là tạm thời → thử lại 3 lần với **đúng payload quá dài đó**, backoff 3s + 9s.
Cộng thêm vòng vá của `_analyze_multipass` (sleep 10s/lượt): mỗi mã đốt khoảng
**20 request chắc chắn thất bại** và ~1 phút chờ vô ích.

**Ba việc cần làm**
1. **Chặn ngay ở client**: 400 = lỗi cứng, không retry (giống 401/403). Sửa 1
   dòng trong `local_api.py` + 3 bản sao ở các dự án khác.
2. **Chọn cách giữ ngữ cảnh**:
   - *(a)* Bỏ phát lại lịch sử — quay về hành vi đã chạy tốt cho 429 mã. Mất
     ngữ cảnh giữa các lượt, nhưng lượt tổng hợp vốn đã được truyền tóm tắt 4
     khía cạnh nên tổn thất nhỏ. **Khuyến nghị**, vì sửa được ngay.
   - *(b)* Nâng `maxlength` phía server lên ~60.000 — giữ được ngữ cảnh, nhưng
     là sửa dự án khác và cần kiểm lại giới hạn của Gemini web ở provider-agent.
3. **Quan trọng với Phụ lục B/C**: nếu chọn (a), trần 10.000 ký tự/lượt là
   ràng buộc cứng khi thêm dữ liệu. Lượt `risk` hiện đã 4.302 ký tự (max đo
   được trên 430 mã: 5.221). Toàn bộ đề xuất B5 + C8 cộng lại ~+1.700 ký tự
   vẫn nằm trong trần, nhưng **phải theo dõi lượt `risk` và `overall`** — đây
   là hai lượt sát trần nhất.

---

# PHỤ LỤC D · Trang cổ phiếu kể chuyện bằng biểu đồ

> **MỤC TIÊU DO NGƯỜI DÙNG ĐẶT (2026-07-27):** AI phải dựng **càng nhiều biểu đồ
> càng tốt**. Không dừng ở số liệu và chữ. Mỗi thứ đưa cho người dùng phải là thứ
> **nhìn được, đọc được lời giải thích, và so được với quá khứ**. Số lần gọi AI
> cho 1 mã **không giới hạn**.
>
> Phụ lục này thay thế và mở rộng §4 + Phase 3 của kế hoạch gốc — hai phần đó chỉ
> liệt kê 5–6 chỗ "nên là biểu đồ", còn đây là kiến trúc đầy đủ.

## D0 · Ranh giới không được vượt: AI KHÔNG sinh số

Đây là quyết định kiến trúc quan trọng nhất, và nó phải được chốt trước khi viết
dòng code đầu tiên.

| | AI được làm | AI KHÔNG được làm |
|---|---|---|
| Chọn biểu đồ nào phù hợp với mã này | ✅ | |
| Viết tiêu đề, cách đọc, so sánh quá khứ | ✅ | |
| Chỉ ra kỳ nào đáng chú ý (bằng **nhãn kỳ**) | ✅ | |
| Đọc ra con số trên trục | | ❌ |
| Sinh mảng dữ liệu để vẽ | | ❌ |
| Sinh SVG/HTML biểu đồ | | ❌ |

**Vì sao tuyệt đối:** ngay trong bản phân tích FPT vừa chạy, AI đã tự mâu thuẫn
giữa hai lượt về con số tăng trưởng (lượt tài chính nói LNST −4,6% YoY, lượt tăng
trưởng nói +19,1% "so cùng kỳ"). Nếu để AI sinh mảng dữ liệu, cái sai đó biến
thành **đường kẻ trên biểu đồ** — người dùng không có cách nào phát hiện. Số liệu
chỉ được lấy từ `market.db` bằng Python thuần.

Cơ chế: AI trả về **spec tham chiếu**, không trả về dữ liệu.

```json
{
  "chart_id": "margin_trend",
  "series": ["gross_margin_y", "net_margin_y"],
  "highlight_periods": ["2026-Q1"],
  "title": "Biên lãi gộp bào mòn 4 năm liên tiếp",
  "read_this": "Đường trên là biên gộp…",
  "history_note": "Mức 34,0% của quý gần nhất là thấp nhất trong toàn bộ chuỗi.",
  "annotations": [{"period": "2026-Q1", "note": "biên gộp thấp nhất, biên ròng cao nhất"}]
}
```

`series` và `highlight_periods` chỉ chấp nhận **ID có trong danh mục**. Validator
gặp ID lạ → loại bỏ biểu đồ đó, không render. Không có đường nào cho số ảo lọt qua.

---

## D1 · Danh mục biểu đồ dựng được NGAY từ dữ liệu đã crawl

34 biểu đồ dưới đây không cần crawl thêm gì. Cột "Cần" ghi phần dữ liệu còn
thiếu (tham chiếu Phụ lục C).

### A · Kết quả kinh doanh — `income_statement`, tối đa 16 kỳ

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| A1 | Doanh thu & LNST theo năm 2022–2025 | cột kép | — |
| A2 | Doanh thu theo quý + đường TTM | cột + đường | C3 |
| A3 | Biên gộp / ròng / EBIT theo thời gian | 3 đường | C2 |
| A4 | Doanh thu → giá vốn → chi phí BH → QLDN → LNST | waterfall | — |
| A5 | Cùng quý năm nay vs năm ngoái | cột đối chiếu | **C1** |
| A6 | Doanh thu theo quý × năm | heatmap mùa vụ | C1 |
| A7 | EPS cơ bản theo kỳ | cột | — |

### B · Bảng cân đối — 109 chỉ tiêu, 1.459 mã đủ 4 năm

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| B1 | Cơ cấu tài sản 4 năm | vùng chồng | — |
| B2 | Cơ cấu nguồn vốn: nợ ngắn/dài + VCSH | cột chồng | — |
| B3 | Nợ/VCSH + thanh toán hiện hành | 2 trục | — |
| B4 | Tồn kho / phải thu / phải trả quy ra ngày | 3 đường | mở rộng 8→25 chỉ tiêu |
| B5 | Vòng quay tiền mặt (CCC) theo năm | cột | như trên |

### C · Dòng tiền — 41 chỉ tiêu

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| C1 | CFO / CFI / CFF theo năm | cột nhóm | — |
| C2 | CFO so LNST (chất lượng lợi nhuận) | 2 đường + vùng chênh | — |
| C3 | Dòng tiền tự do = CFO − đầu tư TSCĐ | cột | — |

### D · Hiệu quả sinh lời

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| D1 | DuPont 3 tầng theo năm | 3 đường | — (đã có bảng) |
| D2 | ROE / ROA / ROIC theo năm | đường | — |
| D3 | ROE của mã trên phân phối toàn ngành | dot-on-distribution | **C7** |

### E · Định giá

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| E1 | P/E theo thời gian + dải percentile 3 năm | đường + band | — (`valuation_band` đã có) |
| E2 | P/B tương tự | đường + band | — |
| E3 | Ngành: P/E (x) × ROE (y), tô đậm mã | scatter | C7 |
| E4 | Giá so EPS TTM | 2 trục | C3 |

### F · Giá & thị trường — 753.225 phiên, index từ 2014

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| F1 | Giá + khối lượng | nến + cột | — |
| F2 | **Chấm sự kiện/tin trên chart giá** | overlay | — |
| F3 | Mã so VNINDEX quy về 100 | 2 đường | **C4** |
| F4 | Sụt sâu nhất (drawdown) theo thời gian | vùng | C4 |
| F5 | Beta trượt 60 phiên | đường | C4 |
| F6 | Khối ngoại mua/bán ròng lũy kế | cột + đường | — |
| F7 | Phân bố mật độ giá | cột ngang | — (đang là 12 dòng chữ) |

### G · Cổ tức & sở hữu — 6.414 bản ghi cổ tức / 1.047 mã

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| G1 | Cổ tức tiền mặt/CP theo năm + tỷ suất | cột + đường | **C5** |
| G2 | Payout ratio theo năm | cột | — |
| G3 | Cơ cấu cổ đông lớn | donut | — |
| G4 | Lịch sử tăng vốn điều lệ | bậc thang | **sửa lỗi B4 trước** |

### H · So sánh ngành — 19 ngành, phủ 1.531/1.531 mã

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| H1 | Xếp hạng mã trong ngành theo từng chỉ tiêu | bar ranking | C7 |
| H2 | Mã so trung vị ngành, 6 trục | radar | — |

### I · Tổng hợp

| # | Biểu đồ | Loại | Cần |
|---|---|---|---|
| I1 | Trục thời gian sự kiện + tin trọng số cao | timeline | — |
| I2 | Điểm 4 khía cạnh AI | radar / 4 đồng hồ | — (điểm đã có) |
| I3 | Thẻ điểm sức khỏe có mốc trung vị ngành | gauge | — |

**Tổng: 34 biểu đồ.** Trong đó **21 cái dựng được ngay hôm nay**, 13 cái chờ các
mục C1–C7 và lỗi B4.

---

## D2 · Mỗi biểu đồ đi kèm 4 thứ AI viết

Đây là phần trả lời "đọc giải thích, so sánh với quá khứ":

| Trường | Nội dung | Dành cho |
|---|---|---|
| `title` | 1 câu nói thẳng biểu đồ đang cho thấy điều gì — không phải tên trục | tất cả |
| `read_this` | 2–4 câu: nhìn vào đâu, đường nào nghĩa là gì, tăng/giảm nói lên điều gì | F0 |
| `history_note` | So với chính lịch sử mã: "thấp nhất 4 năm", "lần đầu vượt trung vị ngành từ 2023" | tất cả |
| `annotations[]` | Các kỳ đáng chú ý + lý do, ghim thẳng lên biểu đồ | chuyên nghiệp |

`history_note` **bắt buộc** cho mọi biểu đồ có trục thời gian — đó chính là yêu
cầu "so sánh với quá khứ". Không có trường này thì biểu đồ bị loại ở validator.

Ngoài ra, nhóm biểu đồ nào cũng có **1 đoạn dẫn chung** (`section_story`) nối các
biểu đồ trong nhóm lại thành một mạch — để người đọc không phải tự ghép 34 mảnh.

---

## D3 · Ngân sách gọi AI

Người dùng cho phép không giới hạn số lần gọi, nhưng vẫn phải đo để biết thi công
được tới đâu. Số đo thật từ FPT: **29s + 30s + 12s + …** mỗi lượt, trung bình
~30s/lượt qua Local API (tuần tự, cooldown 30s).

| Phương án | Số lần gọi | Thời gian/mã | Tổng 576 mã |
|---|---|---|---|
| 1 lượt / 1 biểu đồ | 34 | 20–35 phút | 8–14 ngày chạy liên tục |
| **1 lượt / 1 nhóm (A…I)** | **9** | **5–8 phút** | **2–3 ngày** |
| 1 lượt / 3 nhóm gộp | 3 | 2 phút | 20 giờ |

**Khuyến nghị: 9 lượt theo nhóm.** Mỗi lượt AI nhận dữ liệu của cả nhóm rồi viết
lời cho 3–7 biểu đồ cùng lúc — như vậy lời dẫn trong một nhóm mới nhất quán, và
đó cũng chính là chỗ bản phân tích hiện tại đang hỏng (các lượt mâu thuẫn nhau).

Cộng với 5 lượt phân tích chữ đang có → **14 lượt/mã, ~7–10 phút/mã**.

**Chi phí thật thấp hơn nhiều nhờ 2 điều:**
1. **Biểu đồ không cần AI để vẽ.** 34 biểu đồ hiện ra ngay khi có dữ liệu; lời
   dẫn AI đắp lên sau. Trang không bao giờ trống vì AI chậm.
2. **Lời dẫn chỉ cần sinh lại khi có BCTC mới** (mỗi quý), không phải mỗi ngày.
   Chart giá cập nhật hằng ngày mà không tốn lượt AI nào.

**Phân tầng:** VN30 + mã người dùng theo dõi → đủ 9 lượt. Nhóm còn lại → 3 lượt
gộp. Mã thanh khoản chết (1.081 mã, xem §2.3) → 0 lượt, chỉ vẽ biểu đồ trần.

---

## D4 · Thư viện vẽ

Hiện trạng lẫn lộn: gateway dùng **Chart.js 4.4.1 tải từ CDN** + **lightweight-charts**
(đã tải về máy); còn `/app/` của Crawl Data **không có thư viện nào** — 5 biểu đồ ở
đó là SVG viết tay.

Với 34 biểu đồ gồm waterfall, radar, heatmap, box-plot, scatter, nến — Chart.js
phải cắm thêm plugin cho từng loại. Đề xuất **thống nhất về ECharts**, tải về
`gateway/static/vendor/` (không phụ thuộc CDN, chạy được cả khi mất mạng):

- 1 thư viện phủ hết 34 loại, kể cả waterfall/radar/heatmap/boxplot
- có sẵn `markPoint`/`markLine` — đúng thứ cần cho `annotations[]` và F2
- `dataZoom` cho chuỗi 497 phiên
- giữ lightweight-charts cho riêng chart nến chính (đang chạy tốt, không đụng)

Cần một lớp bọc `chart_render.js` nhận `{chart_id, data, spec}` rồi tự chọn kiểu
vẽ — để thêm biểu đồ thứ 35 chỉ là thêm 1 entry trong danh mục, không phải viết
thêm code vẽ.

---

## D5 · Pháp lý

Biểu đồ có sức thuyết phục mạnh hơn chữ, nên rào phải chặt hơn chứ không lỏng hơn:

1. Mọi `title` / `read_this` / `history_note` chạy qua `check_payload()` như văn xuôi.
2. **Cấm mọi đường dự báo tương lai** — không kéo dài đường ra phía trước, không
   đường mục tiêu giá, không vùng "kỳ vọng". Trục thời gian dừng ở kỳ gần nhất.
3. Không tô màu theo kiểu ngụ ý hành động (xanh = mua). Màu chỉ mã hoá **chiều
   thay đổi**, kèm chú thích rõ.
4. Mọi biểu đồ định giá dùng **ngôn ngữ percentile** ("vùng thấp nhất dải 3 năm"),
   không dùng "rẻ/đắt".
5. Mỗi biểu đồ mang một nhãn nguồn (`market.db · financials · 2026-Q1`) và **ngày
   dữ liệu** — người xem luôn biết mình đang nhìn số của lúc nào.

---

## D6 · Lộ trình

| Bước | Nội dung | Kết quả nhìn thấy được |
|---|---|---|
| **D-1** | `chart_data.py`: danh mục ID + hàm dựng chuỗi thuần Python cho 21 biểu đồ dựng ngay. Không AI. | API trả về dữ liệu 21 biểu đồ |
| **D-2** | `chart_render.js` + ECharts về vendor; render 21 biểu đồ với tiêu đề tĩnh | Trang cổ phiếu có 21 biểu đồ thật |
| **D-3** | Lượt AI theo nhóm (9 lượt) sinh `title` / `read_this` / `history_note` / `annotations`; validator chặn ID lạ và `check_payload` | Mỗi biểu đồ có lời dẫn đọc được |
| **D-4** | Làm các mục C1–C7 + lỗi B4 → mở khoá 13 biểu đồ còn lại | Đủ 34 biểu đồ |
| **D-5** | Cache theo kỳ BCTC + phân tầng VN30/còn lại; backfill | Phủ toàn thị trường |

Thứ tự này có chủ đích: **D-1 và D-2 không cần AI**, nên sau 2 bước đầu đã có 21
biểu đồ chạy thật — nếu phần AI có trục trặc thì trang vẫn dùng được.

**Nghiệm thu cuối:** mở trang một mã bất kỳ, cuộn từ trên xuống, mỗi phần đều có
hình; dưới mỗi hình có 1 câu nói hình đó cho thấy gì và 1 câu so với quá khứ
chính mã; không phần nào chỉ còn số trần hoặc chữ trần.

**Chưa thi công** — dừng ở kế hoạch theo yêu cầu.
