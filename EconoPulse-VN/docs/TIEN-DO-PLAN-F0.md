# Tiến độ thi công PLAN-F0-TRUC-QUAN

> Rà soát trên mã nguồn + `market.db`, cập nhật **2026-07-27, 22:0x**.
> Mọi ô ✅ đều đã kiểm bằng cách chạy code, truy vấn dữ liệu thật, hoặc mở trang
> trên trình duyệt — không dựa vào báo cáo của agent nào.
>
> Để riêng, KHÔNG sửa `PLAN-F0-TRUC-QUAN.md`, vì nhiều agent cùng đọc tệp đó.

## Tổng quan

| Nhóm | Xong | Còn |
|---|---|---|
| §1 Lỗi phá vỡ niềm tin | 3/4 | §1.4 phủ sóng AI |
| §2 Khoảng trống hiểu | 5/5 | — |
| §3 Dữ liệu chưa dùng | 2/2 | — |
| Phụ lục A · chất lượng AI | 3/3 | — |
| Phụ lục B · độ phủ dữ liệu | 2/2 | — |
| Phụ lục C · đào thêm từ DB | 8/8 | — |
| Phụ lục D · biểu đồ | 2/5 | D-3 → D-5 |
| Phát sinh khi rà soát | 2/2 | — |

**27/31 hạng mục.** Tầng dữ liệu, prompt và biểu đồ đã chạy được đầu-cuối. Còn
lại là phủ sóng AI (chạy nền) và lớp AI viết lời dẫn cho biểu đồ.

---

## §1 · Lỗi phá vỡ niềm tin

- [x] **1.1** Một điểm sức khỏe duy nhất — `M.svgGauge`
- [x] **1.2** Ngày `01/01/1970`
- [x] **1.3** Badge tuổi dữ liệu — `f0.css`, 5 chỗ dùng trong `stock.js`
- [ ] **1.4** Phủ sóng AI — **576/1.531 = 38%**. Chặn bởi thông lượng: ~2 phút/mã ⇒ ~32 giờ chạy nền cho 955 mã còn lại

## §2 · Khoảng trống hiểu

- [x] **2.2** Câu kết luận thị trường — `renderVerdict()` trong `home-v3.js`: *"Phiên gần nhất, thị trường …: cứ 10 mã thì N mã giảm, M mã tăng"* + so thanh khoản với bình quân 20 phiên
- [x] **2.3** Lọc cổ phiếu thanh khoản chết — `liquidity.py`, ≥500 triệu + ≤2 phiên KL=0, mặc định bật + nút "hiện tất cả"
- [x] **2.4** Timeline sự kiện thay card cổ tức rỗng
- [x] **2.5** Khối "Bước tiếp theo" — **hoàn tất trong đợt này**: component đã có sẵn ở `common.js` nhưng chưa trang nào gọi. Đã thêm `#next-steps` vào `stock.html` + lời gọi trong `stock.js`. Kiểm trên trình duyệt: HPG hiện đủ 3 bước, tên ngành dịch đúng ("Tài nguyên cơ bản"), không tràn ngang ở 375px

## §3 · Dữ liệu đã crawl nhưng UI chưa dùng

- [x] **3.1** "Doanh nghiệp này làm gì?" — `company_profile` vào whitelist `stock_page/api.py:183`, front-end render. Cả hai đầu đã nối
- [x] **3.2** Card cổ tức — `_dividend_block` + timeline

## Phụ lục A · Chất lượng phân tích AI

- [x] **A5/A6** Đủ dữ kiện — prompt 11.808 → **19.643 ký tự/mã**
- [x] **A7** Dọn khuyến nghị — xoá `investment_rating` ở **25 bản ghi** `market.db` + **25 file** `ai_analysis.json`. Thêm `tests/test_no_investment_rating.py` quét toàn DB

## Phụ lục B · Độ phủ dữ liệu

- [x] **B4** Vốn điều lệ — loại kỳ `date = NaT`. FPT: **20 tỷ → 17.413 tỷ**
- [x] **B5** Mở rộng khối dữ liệu — mô tả doanh nghiệp, bảng cân đối riêng cho ngân hàng, tin kèm ngày

## Phụ lục C · Moi thêm từ market.db — **8/8**

- [x] **C1** YoY cùng quý (suy ra `FY − 3 quý`, gắn nhãn, kèm cảnh báo mùa vụ) · **17 → 1.069 mã**
- [x] **C2** Chuỗi 4 năm + 3 quý · [x] **C3** TTM + EPS/P-E TTM
- [x] **C4** So VNINDEX: sức mạnh tương đối, beta, sụt sâu nhất
- [x] **C5** Lịch sử cổ tức · [x] **C6** Sự kiện pha loãng · [x] **C7** Xếp hạng ngành
- [x] **C9** Gỡ trần prompt 10.000 ký tự; 4xx là lỗi cứng; `PROMPT_BUDGET = 9.200`

| Kiểm chứng | Kết quả |
|---|---|
| Lượt prompt lớn nhất | 6.421 ký tự — dưới ngưỡng 9.200 |
| So VNINDEX (FPT 1 năm) | FPT −47,3% vs VNINDEX +21,6% → **−68,8 điểm** |
| Bảng nhiều kỳ cho ngân hàng | ACB/VCB đủ 4 năm + 3 quý |

## Phụ lục D · Tầng biểu đồ

- [x] **D-1** `modules/stock_page/chart_data.py` — **hoàn tất**
- [x] **D-2** Vẽ ra màn hình — **hoàn tất**: `js/chart-render.js` + `css/charts.css` + tab "Biểu đồ" trên trang cổ phiếu
- [ ] **D-3** Lượt AI theo nhóm sinh lời dẫn + validator chặn ID lạ
- [ ] **D-4** 13 biểu đồ còn lại · [ ] **D-5** Cache + phân tầng

### D-2 · Quyết định kỹ thuật: tự vẽ SVG, không thêm thư viện

Kế hoạch ban đầu ghi "tải ECharts về vendor". Khi thi công thì bỏ, vì:

- repo **không có sẵn** ECharts, mà tải mã thực thi của bên thứ ba về rồi chạy
  là việc nên do người quyết định, không phải tiện tay thêm vào;
- dự án vốn đã đi hướng này — `user.html` tự vẽ SVG, `lightweight-charts` để sẵn
  trong `vendor/`, không phụ thuộc CDN;
- chạy được cả khi máy không có mạng.

`chart-render.js` (≈330 dòng, không phụ thuộc gì) vẽ đủ 8 kiểu: cột nhóm, cột
chồng, đường, cột+đường, thác nước, dải percentile, phân bố, dòng thời gian.
Màu lấy từ token nên tự đúng ở nền sáng lẫn nền tối.

**Đổi lại:** không có zoom/pan. Nếu sau này cần, thay đúng file này là xong —
`chart_data.py` phát ra định dạng trung lập, không dính tới thư viện nào.

### Kiểm chứng D-2 trên trình duyệt

Chạy một gateway thứ hai ở cổng 9977 (`MP_NO_SPAWN=1`) để kiểm mà không làm gián
đoạn dịch vụ đang chạy; xong thì tắt.

| Kiểm | Kết quả |
|---|---|
| Thẻ biểu đồ | **20**, chia 8 nhóm |
| SVG vẽ ra hình | 19 (+1 dòng thời gian) — không thẻ nào rỗng |
| Lỗi console | **0** |
| Thác nước | cột doanh thu từ 0 lên, 3 cột chi phí nối tiếp đi xuống, cột LNST về 0 — đúng bậc thang |
| Dải định giá | 1 vùng tô P20–P80 + 1 đường trung vị nét đứt |
| Chấm sự kiện trên giá | 29 chấm, mỗi chấm có tooltip nội dung công bố |

Tab nạp lười — chỉ gọi API ở lần mở đầu tiên.

### D-1 đã có gì

**20 biểu đồ/mã**, 8 nhóm, không gọi AI một lần nào:

| Nhóm | Biểu đồ |
|---|---|
| A Kết quả KD | doanh thu & LNST theo năm · doanh thu quý + TTM · biên lãi · EPS · thác nước lợi nhuận |
| B Tài sản & nguồn vốn | cơ cấu tài sản · nợ vs vốn chủ · đòn bẩy & thanh toán |
| C Dòng tiền | ba dòng tiền · tiền thật vs lợi nhuận sổ · dòng tiền tự do |
| D Hiệu quả | ROE/ROA · phân rã DuPont |
| E Định giá | dải P/E · dải P/B (percentile lịch sử chính mã) |
| F Giá | giá & khối lượng · so VNINDEX mốc 100 · chấm sự kiện lên giá · phân bố mật độ giá |
| G Cổ tức | cổ tức tiền mặt theo năm |
| I Tổng hợp | dòng thời gian sự kiện |

Endpoint: **`GET /api/stock/<mã>/charts`** (`gateway/app.py`). Không phụ thuộc AI
nên trả về được cả khi Local API tắt.

Độ phủ: FPT 20 · VNM 20 · HPG 19 · **ACB 18 (ngân hàng)** · DDM 18 (mã yếu).

**Hai lỗi tự phát hiện khi soi số, đã sửa:**
- Thác nước hiện chi phí thành cột **dương** — vnstock đã lưu chi phí là số âm, đảo dấu lần nữa thành ra cộng. Ép `−abs()`, có test chặn
- DuPont và biểu đồ Biên lãi cùng gọi "biên lãi ròng" nhưng một bên tính trên lợi nhuận công ty mẹ (13,4%), một bên toàn phần (16,0%) — đúng lỗi "hai con số cùng tên" của §1.1. Đã đổi nhãn thành "biên lãi ròng — cổ đông công ty mẹ"

**Chốt chặn tính đúng** (`tests/test_chart_data.py`, 7 test): tổng 4 quý 2025 phải
đúng bằng doanh thu năm 2025; không kỳ nào trên trục x vượt quá hiện tại (legal).

---

## Phát sinh khi rà soát — cả hai đã xử lý

### ✅ P0-1 · Sự cố AI tạm thời từng xoá mất bản phân tích tốt

Phát hiện khi Local API tắt giữa lúc chạy ACB: `analyze_one` nuốt lỗi, rơi về
`_quant_only` rồi **ghi đè** bản 5 lượt đầy đủ bằng bản báo lỗi.

Đã thêm `_keep_previous()`: khi AI hỏng mà bản cũ còn dùng được (có ít nhất 1
lượt khía cạnh), giữ nguyên phần nhận định, chỉ làm mới số liệu định lượng và
gắn cờ `stale` + `last_error`.

Kiểm chứng bằng đúng kịch bản đó — chĩa client vào cổng chết, chạy trên FPT:

```
[!]  FPT AI (local_api) lỗi → chỉ giữ số liệu định lượng
[giữ] FPT: giữ lại bản phân tích cũ (5 lượt, 2026-07-26) — chỉ cập nhật số liệu
SAU: mode=local_api n_passes=5 aspects=4 stale=True health=68
```

Trước khi sửa, cùng kịch bản này để lại `mode=ai_error, aspects=0`.
Có `tests/test_keep_previous.py` (4 test).

### ✅ P0-2 · Local API từng tắt

Đã bật lại, `/health` trả 200.

---

## Bài học rút ra cho lần sau

**Rà soát bằng từ khoá đoán là không đủ.** Đợt kiểm đầu tôi kết luận §2.2 và §2.5
"chưa làm" vì tìm `marketSentence` / `next-step` không ra. Thực tế §2.2 đã xong
hẳn (`renderVerdict`), còn §2.5 đã có component nhưng chưa ai gọi. Muốn biết một
việc xong chưa thì phải **mở trang xem**, không phải grep tên hàm mình tự nghĩ ra.

**Biến `M` bị che tên.** `stock.js`, `home-v3.js`, `stock-analysis.js`,
`chat-blocks.js` đều khai `const M = window.MPChart` ở đầu file. Gọi
`M.renderNextSteps(...)` trong mấy file đó sẽ **im lặng không chạy** vì guard
`typeof … === "function"` trả false — không lỗi, không log, chỉ là không hiện gì.
Trong các file này phải viết `window.M.` đầy đủ.

---

## Việc tiếp theo

1. **Khởi động lại gateway :9999** — route `/api/stock/<mã>/charts` và tab "Biểu đồ" đã kiểm xong ở cổng 9977 nhưng tiến trình :9999 đang chạy chưa nạp code mới. Đây là việc duy nhất chặn người dùng thấy được thành quả
2. **§1.4** — chạy nền phủ nốt 955 mã (~32 giờ). Giờ an toàn hơn trước vì P0-1 đã chặn mất dữ liệu khi AI chớp tắt
3. **D-3** — lượt AI theo nhóm sinh lời dẫn cho từng biểu đồ, validator chặn ID lạ
4. **D-4/D-5** — 13 biểu đồ còn lại, cache theo kỳ BCTC, phân tầng VN30

## Trạng thái test

| Dự án | Test |
|---|---|
| Crawl Data | **112** xanh |
| EconoPulse-VN | **159** xanh |

## Tệp đã thêm/sửa trong đợt này

| Tệp | Việc |
|---|---|
| `Crawl Data/src/analyzer.py` | P0-1 `_keep_previous` + `_finish` |
| `Crawl Data/tests/test_keep_previous.py` | 4 test P0-1 |
| `Crawl Data/tests/test_no_investment_rating.py` | 2 test A7 |
| `modules/stock_page/chart_data.py` | D-1 · 20 biểu đồ |
| `gateway/static/js/chart-render.js` | D-2 · renderer SVG |
| `gateway/static/css/charts.css` | D-2 · giao diện khối biểu đồ |
| `gateway/app.py` | route `/api/stock/<mã>/charts` |
| `gateway/templates/pages/stock.html` | tab "Biểu đồ" + `#next-steps` |
| `gateway/static/js/stock.js` | nạp lười tab biểu đồ + gọi §2.5 |
| `EconoPulse-VN/tests/test_chart_data.py` | 7 test D-1 |
