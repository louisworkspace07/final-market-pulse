# Plan hoàn thiện — phần còn thiếu

> Viết ngày **2026-07-27** sau khi đã thi công xong 27/31 hạng mục của
> `PLAN-F0-TRUC-QUAN.md`. Tài liệu này CHỈ nói phần còn lại; mọi con số dưới đây
> đo trực tiếp trên `market.db` và mã nguồn hiện tại, không phải ước lượng.
>
> Trạng thái tổng: xem `TIEN-DO-PLAN-F0.md`.

## Bảng ưu tiên

| # | Việc | Trạng thái |
|---|---|---|
| **P0** | Sửa tên trường sai | ✅ **xong** — hoá ra là **5** lỗi, không phải 3 |
| **P1** | Khối "Vòng quay vốn & an toàn nợ" vào prompt | ✅ **xong** |
| **P2** | Biểu đồ còn lại | ✅ **xong** — 20 → **28** biểu đồ/mã |
| **P3** | AI viết lời dẫn cho biểu đồ (D-3) | ✅ **xong** — 5 → **13 lượt/mã** |
| — | Đưa nốt dữ liệu Crawl Data lên :9999 | ✅ **xong** — 18 nguồn, 4.045 bản ghi |
| — | Thu nhỏ biểu đồ, xếp lưới đọc nhiều cùng lúc | ✅ **xong** — 3 cột |
| **P4** | Cache + phân tầng (D-5) | ⬜ còn |
| **P5** | Phủ sóng AI 0% → 100% (§1.4) | ⬜ còn — DB phân tích đã xoá sạch để chạy lại |

> Cập nhật 2026-07-27 22:5x. Phần dưới giữ nguyên phân tích ban đầu; các mục đã
> làm có ghi chú kết quả thực tế.

---

## P0 · Ba tên trường sai — im lặng trả về `None`

Cùng một loại lỗi với vốn điều lệ B4: không ném lỗi, không log, chỉ ra `None`,
rồi hệ thống báo "không đủ dữ liệu" cho thứ đang nằm sẵn trong bảng.

| Chỗ sai | Đang đọc | Tên thật trong DB | Bản ghi có |
|---|---|---|---|
| `fundamentals.py:329` | `ev_to_ebitda` | `ev_ebitda` | **9.891** |
| `fundamentals.py:325` | `roic` | `return_on_capital_employed_roce` | **9.525** |
| `chart_data.py` | `purchase_of_fixed_assets` | `purchases_of_fixed_assets_and_other_long_term_assets` | có |
| `chart_data.py` | `net_cash_flows_from_investing_activities` | `net_cash_inflows_outflows_from_investing_activities` | **1.496 mã** |
| `chart_data.py` | `net_cash_flows_from_financing_activities` | `net_cash_inflows_outflows_from_financing_activities` | **1.496 mã** |

**Hai lỗi cuối do chính test bắt được ngay lần chạy đầu**, không phải người đọc
ra. Hậu quả: biểu đồ "Ba dòng tiền" chỉ vẽ được **một** đường (kinh doanh) —
đầu tư và tài chính lặng lẽ rỗng, nhưng biểu đồ vẫn hiện nên trông như bình
thường. Sau khi sửa: đủ 3 chuỗi, và `fcf_year` dựng được.

### Kết quả sau khi sửa (đo thật)

| | Trước | Sau |
|---|---|---|
| FPT EV/EBITDA | `n/a` | **29,69** |
| FPT EV/EBIT | không có | **48,85** |
| FPT ROCE | `n/a` (nhãn ROIC) | **33,07%** |
| Biểu đồ dòng tiền | 1 chuỗi | **3 chuỗi** |
| Số biểu đồ/mã (FPT) | 20 | **21** |

Ngân hàng (ACB) vẫn ra `None` cho EV/EBITDA và ROCE — đúng, vì mô hình ngân hàng
không dùng Enterprise Value.

**Bằng chứng đây là lỗi thật, không phải thiếu dữ liệu:** prompt gửi cho AI dòng
`EV/EBITDA n/a`, và AI viết lại vào bản phân tích FPT đang lưu trong DB:

> *"Không đủ dữ liệu về EV/EBITDA và ROIC để tiến hành so sánh toàn diện"*

Trong khi EV/EBITDA của FPT năm 2025 = **10,8**, nằm ngay trong bảng `ratio`.
Có **7 mã** đã ghi câu phàn nàn tương tự vào kết quả.

**Lưu ý khi sửa `roic`:** ROCE và ROIC **không phải một chỉ tiêu**. ROCE tính
trên vốn dài hạn bình quân. Phải đổi luôn nhãn hiển thị thành "ROCE", không
được để nhãn ROIC rồi nhét số ROCE vào — đó lại đúng lỗi "hai con số cùng tên"
của §1.1.

**Nghiệm thu:** dựng prompt cho FPT, dòng Định giá hiện `EV/EBITDA 10.8`; biểu
đồ `fcf_year` dựng được; thêm test chặn tên trường không tồn tại.

### Chặn tái diễn — ✅ đã làm

`Crawl Data/tests/test_item_ids.py` quét mọi chuỗi trông như `item_id` trong 4
tệp có hỏi bảng `financials`, đối chiếu với `SELECT DISTINCT item_id`. Tên nào
không tồn tại **mà tiền tố của nó lại có** trong DB thì fail — dấu hiệu gõ đúng
họ chỉ tiêu nhưng sai đuôi.

Chỉ quét phần **code**, bỏ chú thích và docstring: chính lời chú thích giải
thích lỗi lại chứa cái tên sai, quét cả chú thích thì test tự báo động vì lời
cảnh báo của mình.

---

## P1 · Bảng `ratio` có 58 chỉ tiêu, prompt dùng 2

Đây là mỏ dữ liệu lớn nhất còn nguyên. Tất cả **đã tính sẵn**, phủ gần hết thị
trường, không cần crawl thêm.

### Khối mới đề xuất — thêm vào lượt `financial`

```
### VÒNG QUAY VỐN & AN TOÀN NỢ
- Chu kỳ tiền mặt: 43,2 ngày (tồn kho 16,7 + thu tiền 60,6 − trả tiền 34,1)
- Vòng quay: tổng tài sản 0,88 | tồn kho 21,8 | phải thu 6,0 lần
- Trả lãi vay: 17,1 lần | Trả nợ từ dòng tiền HĐKD: 22,8 lần
- Thanh toán nhanh 1,35 | bằng tiền mặt 0,71
- Dòng tiền HĐKD/VCSH 23,2% | /Tổng tài sản 11,4%
- Tỷ lệ dồn tích: 0,0% (cân đối kế toán) · 0,0% (dòng tiền)
```

Chi phí thực tế: lượt `financial` **5.220 → 5.790 ký tự**, trần 9.200 — còn dư.

### ✅ Đã làm — và suýt gửi số sai

Lần dựng đầu ra **chu kỳ tiền mặt 182,1 ngày** cho FPT thay vì 43,2. Nguyên nhân:
dùng `rget` (ưu tiên kỳ QUÝ) trong khi KBS trả giá trị quý là đóng góp riêng
quý, **chưa niên hoá** — vòng quay bị chia 4, số ngày bị nhân ~4. Đây đúng là cái
bẫy `fundamentals.py` đã ghi chú sẵn cho roe/roa mà tôi vẫn dẫm vào. Sửa sang
`rget_y`:

| | Theo quý (sai) | Theo năm (đúng) |
|---|---|---|
| Chu kỳ tiền mặt | 182,1 ngày | **43,2 ngày** |
| Vòng quay tổng tài sản | 0,24 lần | **0,88 lần** |
| Dòng tiền HĐKD/VCSH | 0,00% | **23,17%** |

Đối chiếu chéo giữa các ngành cho thấy số hợp lý: HPG (thép) tồn kho **137 ngày**
→ chu kỳ 106,2; VNM 50,3; FPT 43,2.

**Đã BỎ tỷ lệ dồn tích khỏi khối này.** Đo trên 6.367 bản ghi từ 2024: chỉ
**3,3% khác 0** — cột gần như rỗng. Gửi "dồn tích 0,00%" cho AI còn tệ hơn không
gửi, vì nó đọc thành "lợi nhuận hoàn toàn là tiền thật". Chỉ tiêu dồn tích thật
đã có ở khối `earnings_quality` (tính từ dữ liệu thô).

**Ngân hàng được bỏ qua hoàn toàn** — vòng quay hàng tồn kho vô nghĩa với mô hình
huy động–cho vay; nhóm này đã có `sector_model` (NIM/CIR/LDR).

### Độ phủ đo thật

| Chỉ tiêu | Số mã có | FPT 2025 |
|---|---|---|
| Thời gian tồn kho / thu tiền / trả tiền | 1.420 / 1.473 / 1.432 | 16,7 / 60,6 / 34,1 ngày |
| Khả năng trả lãi vay | 1.420 | 17,1 lần |
| Khả năng trả nợ từ dòng tiền | 1.472 | 22,8 lần |
| Thanh toán nhanh | 1.432 | 1,35 |
| Dòng tiền HĐKD / VCSH | 1.472 | 23,2% |
| Tỷ lệ dồn tích (2 phương pháp) | 1.472 | 0,0% |
| EV/EBITDA · EV/EBIT · P/S | 1.472 | 10,8 · — · 2,33 |
| ROCE | 1.420 | 33,1% |
| Beta (tính sẵn) | 1.502 | 0,64 |
| EPS 4 quý · BVPS | 1.502 | 6.021đ · 25.680đ |

### Bốn câu hỏi hệ thống hiện KHÔNG trả lời được

1. **"Doanh nghiệp bị chôn vốn bao lâu trong một vòng bán hàng?"** — chu kỳ tiền
   mặt. FPT 43,2 ngày. Chưa có ở đâu trong hệ thống.
2. **"Lãi có phải là tiền thật không?"** — hiện chỉ có CFO/LNST. Bảng có tỷ lệ
   dồn tích theo **hai phương pháp độc lập** để đối chiếu chéo.
3. **"Nếu lãi suất tăng thì doanh nghiệp có trả nổi lãi vay không?"** — khả năng
   trả lãi vay, khả năng trả nợ từ dòng tiền. Hiện chỉ có Nợ/VCSH.
4. **"Đắt hay rẻ theo thước đo nào khác P/E, P/B?"** — EV/EBITDA, EV/EBIT, P/S.

**Nghiệm thu:** prompt FPT có đủ khối trên; ngân hàng KHÔNG hiện khối này (chỉ
tiêu vòng quay hàng tồn kho vô nghĩa với ngân hàng — dùng `is_bank` để ẩn).

---

## P2 · Biểu đồ còn lại (D-4) — ✅ đã làm

**20 → 28 biểu đồ/mã.** Thêm 7 biểu đồ mới cùng 1 cái được cứu nhờ P0.

| Mã | Biểu đồ | Kiểu |
|---|---|---|
| `yoy_same_quarter` | Quý này so cùng quý năm trước (ghi rõ khi là số suy ra) | cột |
| `seasonality` | Doanh thu theo quý × năm | **bản đồ nhiệt** |
| `working_capital_days` | Tồn kho / thu tiền / trả tiền quy ra ngày | 3 đường |
| `cash_cycle` | Chu kỳ tiền mặt theo năm | cột |
| `roe_distribution` | ROE của mã trên phân phối toàn ngành | phân bố |
| `sector_scatter` | Ngành: P/E × ROE, tô đậm mã đang xem | **tán xạ** |
| `drawdown` | Khoảng cách so với đỉnh gần nhất | đường |
| `fcf_year` | Dòng tiền tự do (được cứu nhờ sửa tên capex ở P0) | cột |

Hai kiểu vẽ mới (**bản đồ nhiệt**, **tán xạ**) đã bổ sung vào `chart-render.js`.

**Độ phủ:** FPT 28 · VNM 27 · HPG 26 · DDM 25 · **ACB 23** (ngân hàng không có
vòng quay tồn kho — đúng như thiết kế).

**Kiểm trên trình duyệt:** 28 thẻ, 8 nhóm, **không thẻ nào rỗng**, 0 lỗi console.
Tán xạ vẽ 20 chấm với 1 chấm được tô đậm ghi tên; bản đồ nhiệt 8 ô đúng bằng số
quý FPT có dữ liệu.

**Bỏ hẳn F6 (khối ngoại lũy kế):** `foreign_history.jsonl` chỉ **4 dòng/mã**.

### Test bổ sung
- `groups` không trùng và đúng thứ tự A→I (một hàm dựng phát ra nhiều nhóm nên
  chỗ này từng sinh nhóm trùng)
- Chu kỳ tiền mặt phải bằng tồn kho + thu tiền − trả tiền ở **từng năm**
- Kiểu `scatter`/`heatmap` được miễn ràng buộc "độ dài chuỗi = độ dài trục x"

### Ghi chú lịch sử (phân tích ban đầu, giữ lại để đối chiếu)

Hiện **20/34**. Sau khi C1–C7 và B4 xong, phần lớn số còn lại **đã hết bị chặn**
— chỉ là chưa viết.

| Mã | Biểu đồ | Nguồn đã sẵn sàng |
|---|---|---|
| A5 | Cùng quý năm nay vs năm ngoái (cột đối chiếu) | C1 xong |
| A6 | Doanh thu theo quý × năm (heatmap mùa vụ) | C1 xong |
| B4 | Tồn kho / phải thu / phải trả quy ra ngày | `ratio`, 1.420–1.473 mã |
| B5 | Chu kỳ tiền mặt theo năm | cùng nguồn |
| D3 | ROE của mã trên phân phối toàn ngành | `peers.pct` xong |
| E3 | Ngành: P/E × ROE, tô đậm mã | `peers` xong |
| E4 | Giá so EPS 4 quý | C3 xong |
| F4 | Sụt sâu nhất theo thời gian | C4 xong |
| F5 | Beta trượt | `ratio.beta`, 1.502 mã |
| G3 | Cơ cấu cổ đông lớn | `shareholders.json`, 73 bản ghi |
| G4 | Lịch sử tăng vốn điều lệ | B4 xong, 26 bản ghi |
| H1 | Xếp hạng mã trong ngành theo từng chỉ tiêu | `peers.pct` xong |

**Bỏ F6 (khối ngoại lũy kế):** `foreign_history.jsonl` chỉ có **4 dòng**/mã —
không đủ dựng chuỗi. Muốn làm phải bổ sung crawler trước; ghi lại ở phần cuối.

**Nghiệm thu:** FPT ≥ 30 biểu đồ, ACB ≥ 26 (ngân hàng không có tồn kho); test
hợp đồng hiện có phải xanh với mọi biểu đồ mới.

---

## P3 · AI viết lời dẫn cho biểu đồ (D-3) — ✅ đã làm

**Kết quả chạy thật trên FPT:**

```
nhóm A (Kết quả kinh doanh) : 5/7 biểu đồ có lời
nhóm B (Tài sản & nguồn vốn): 4/5
nhóm C (Dòng tiền)          : 3/3
nhóm D (Hiệu quả sinh lời)  : 3/3
nhóm E (Định giá)           : 2/3
nhóm F (Giá & thị trường)   : 4/5
nhóm G (Cổ tức)             : 1/1
nhóm I (Tổng hợp)           : 1/1
TỔNG 23/28 biểu đồ · 8 lượt · 230 giây
```

**Lượt/mã: 5 → 13** (5 phân tích chữ + 8 nhóm biểu đồ). Kế hoạch gốc ghi 14 vì
tính 9 nhóm; FPT chỉ có 8 nhóm có biểu đồ nên là 8 lượt — số lượt bám theo dữ
liệu thật chứ không cố định.

**5 biểu đồ không có lời là CHỦ Ý**: prompt ghi rõ *"biểu đồ nào không có gì
đáng nói thì bỏ qua, đừng viết cho đủ"*.

**Validator không loại mục nào** trong lượt chạy này — mọi `chart_id` và nhãn kỳ
AI trả về đều có thật.

### Chất lượng — trích nguyên văn

> **Biên lãi qua các kỳ** → *"Tỷ lệ tiền lãi thực sự bỏ túi tăng lên kỷ lục dù
> chi phí gốc đắt đỏ hơn."*
> *"Đường biên lãi gộp đi xuống nghĩa là chi phí sản xuất mỗi món hàng đang đội
> lên. Nhưng đường biên lãi ròng (lãi thật sự cất đi sau mọi chi phí) lại vượt lên…"*

> **So với VNINDEX** → *"Biểu đồ dùng mốc 100 điểm để so sánh xuất phát điểm giữa
> hai bên. Đường FPT rơi xuống 52,92 điểm, trong khi VNINDEX đi lên…"*
> Ghim mốc: `2025-07-14` đỉnh 100,39 · `2026-05-18` VNINDEX cao nhất 132,25 ·
> `2026-07-15` FPT đáy 52,76.

### Kiến trúc

| Tệp | Việc |
|---|---|
| `modules/stock_page/chart_notes.py` | dựng prompt theo nhóm · validator · lưu/đọc · merge |
| `POST /api/stock/<mã>/charts/narrate` | sinh lời dẫn (bước DUY NHẤT gọi AI trong tầng biểu đồ) |
| `GET /api/stock/<mã>/charts` | tự gắn lời dẫn nếu đã có |
| `companies/<MÃ>/analysis/chart_notes.json` | nơi lưu |

Gửi cho AI **bản tóm tắt** (đầu/cuối/thấp nhất/cao nhất kèm nhãn kỳ), không gửi
toàn bộ chuỗi — AI cần biết xu hướng và điểm bất thường, mà cũng không được phép
đọc ra số.

**Validator loại chứ không sửa** (`tests/test_chart_notes.py`, 10 test):
`chart_id` không có thật → bỏ cả mục; nhãn kỳ không có trong chính biểu đồ đó →
bỏ chú thích nhưng giữ phần chữ đúng; dính `check_payload` → bỏ cả mục. Một nhóm
hỏng không làm hỏng nhóm khác.

### Ghi chú kế hoạch ban đầu

Hiện **20 biểu đồ có hình nhưng chưa có lời**. Đây là phần đưa số lượt gọi từ 5
lên 14 như kế hoạch gốc (`PLAN-F0-TRUC-QUAN.md:976`).

### Ràng buộc bất di bất dịch — AI không sinh số

Đã ghi ở D0 và phải giữ nguyên: AI **chọn** biểu đồ đáng nói và **viết lời**;
KHÔNG đọc ra con số, KHÔNG sinh mảng dữ liệu. Trả về spec tham chiếu `id`:

```json
{"chart_id": "margin_trend",
 "title": "Biên lãi gộp bào mòn 4 năm liên tiếp",
 "read_this": "Đường trên là biên gộp…",
 "history_note": "Mức 34,0% quý gần nhất là thấp nhất toàn chuỗi.",
 "annotations": [{"period": "2026-Q1", "note": "gộp thấp nhất, ròng cao nhất"}]}
```

Validator: `chart_id` và `period` không có trong dữ liệu thật → **loại bỏ mục
đó**, không render. Mọi câu chữ chạy qua `check_payload()`.

`history_note` **bắt buộc** với mọi biểu đồ có trục thời gian — đó chính là yêu
cầu "so được với quá khứ".

### Chia lượt

9 lượt theo nhóm A…I, mỗi lượt viết lời cho 3–7 biểu đồ cùng lúc. Lý do không
chia 1 lượt/1 biểu đồ (34 lượt): lời dẫn trong cùng nhóm phải nhất quán — đúng
chỗ 4 lượt chữ hiện tại đang nói ngược nhau về cùng con số tăng trưởng.

### Nhớ đo lại trần prompt

Lượt `risk` hiện đã 6.421 ký tự trên trần 9.200. Lượt biểu đồ mang theo dữ liệu
cả nhóm nên phải kiểm từng nhóm không vượt trần trước khi bật.

**Nghiệm thu:** mỗi biểu đồ có `title` + `read_this` + `history_note`; ID lạ bị
validator chặn; hỏng tầng AI thì biểu đồ vẫn hiện (chỉ mất lời).

---

## P4 · Cache + phân tầng (D-5)

Lời dẫn chỉ cần sinh lại khi có BCTC mới (mỗi quý), không phải mỗi ngày. Chart
giá cập nhật hằng ngày mà không tốn lượt AI nào.

| Nhóm | Lượt |
|---|---|
| VN30 + mã người dùng theo dõi | đủ 9 lượt biểu đồ |
| Còn lại | 3 lượt gộp |
| 1.081 mã thanh khoản chết (§2.3) | 0 — chỉ vẽ biểu đồ trần |

---

## P5 · Phủ sóng AI (§1.4) — sẵn sàng chạy

**Kho phân tích đã xoá sạch theo yêu cầu** (2026-07-27 23:0x) để chạy lại toàn bộ
bằng prompt mới:

| | |
|---|---|
| Bản ghi `ai_analysis` | 576 → **0** |
| Thư mục `companies/*/analysis` | xoá **1.531** |
| `web/data/detail/*.json` | xoá 576, dựng lại còn 1 (FPT) |
| Dữ liệu gốc | **còn nguyên** — 2.551.632 dòng BCTC, 753.225 phiên giá, 41.531 sự kiện |

**Sao lưu trước khi xoá** — `backup_ai_analysis_2026-07-27/`:
- `market.db` bản đầy đủ (840 MB)
- `companies_analysis.zip` — 3.065 tệp phân tích + debug (11,8 MB)

### Chạy mẫu FPT qua Local API — ✅ đạt

```
financial  40.8s  gửi 5,667  nhận 1,649  gọi 1 lần  → 85 điểm
valuation  15.8s  gửi 3,782  nhận 1,923  gọi 1 lần  → 75
growth     12.2s  gửi 4,304  nhận 1,683  gọi 1 lần  → 75
risk       30.6s  gửi 6,435  nhận 1,903  gọi 1 lần  → 30
overall    34.6s  gửi 4,495  nhận 2,122  gọi 1 lần
TỔNG 134,0s · 5/5 lượt · không lượt nào phải gọi lại
```

Prompt **19.646 → 24.683 ký tự/mã**, lượt lớn nhất 6.435 (trần 9.200).

**AI thực sự dùng dữ liệu vừa mở khoá** — không chỉ nhận thêm số:

> *"Tỷ lệ CFO/LNST đạt 0.88 cùng **chu kỳ tiền mặt ngắn (43.2 ngày)** cho thấy
> doanh thu ghi nhận được thu hồi hiệu quả bằng tiền thật."*
>
> *"Tỷ lệ nợ vay/VCSH chỉ 48.17% đi kèm **hệ số bao phủ lãi vay 17.11 lần**,
> cho thấy cấu trúc nợ rất an toàn."*

Và câu phàn nàn cũ **"Không đủ dữ liệu về EV/EBITDA và ROIC" đã biến mất**.

### Ước tính chạy toàn thị trường

1.531 mã × ~134 giây ⇒ **≈ 57 giờ** liên tục (trước đây ước 35 giờ cho 955 mã;
giờ chạy lại từ đầu nên nhiều hơn). Chạy được rồi vì P0-1 đã chặn việc AI chớp
tắt phá bản phân tích đang tốt.

---

## Đưa nốt dữ liệu Crawl Data lên :9999 — ✅ đã làm

Trước đây các tệp per-company chỉ xem được ở cổng 5000, nên người dùng cổng 9999
không biết hệ thống đang giữ những gì. Nay có tab **"Dữ liệu gốc"** trên trang cổ
phiếu — **18 nguồn, 4.045 bản ghi** cho FPT:

| Nhóm | Nguồn |
|---|---|
| Sở hữu & quản trị | ban lãnh đạo (9) · công ty con (14) · liên kết (5) · cổ đông lớn (73) · lịch sử tăng vốn (26) · giao dịch nội bộ |
| Tin | tin công bố (50) · **báo chí RSS (25)** · sự kiện & cổ tức (30) · tin đã chấm trọng số (105) |
| Báo cáo tài chính thô | cân đối (1.744) · KQKD (400) · lưu chuyển tiền (656) · chỉ số (406) |
| Thị trường | giá lịch sử (497) · khối ngoại phiên gần nhất · khối ngoại theo ngày |
| Khác | hồ sơ công ty |

- `GET /api/stock/<mã>/sources` — nguồn nào có thật, bao nhiêu bản ghi
- `GET /api/stock/<mã>/source/<khóa>?limit=N` — nội dung, mặc định cắt 400 dòng

**Đọc thẳng từ thư mục `companies/`**, không proxy qua cổng 5000 — trang cổ phiếu
không phụ thuộc việc dịch vụ crawl có đang chạy hay không.

**⚠ Rào pháp lý phải làm lại ở đây.** `profile.json` chứa `rating`,
`target_price`, `upside_to_target_percent` — khuyến nghị của công ty chứng khoán.
Trang cổ phiếu đã chặn bằng whitelist `_SAFE_PROFILE_KEYS`; endpoint mới đọc
thẳng tệp nên phải chặn LẠI, nếu không là mở đúng cái cửa vừa khoá. `_scrub()`
lọc đệ quy, có test riêng (`tests/test_raw_sources.py`, 7 test — gồm cả chặn
đường dẫn kiểu `../../`).

### Còn lại chưa dùng trong PROMPT (khác với "chưa lên web")

| Nguồn | Ghi chú |
|---|---|
| Lưu chuyển tiền tệ | 41 chỉ tiêu, prompt dùng 0 trực tiếp; P1 chạm vài cái qua `ratio` |
| Bảng cân đối | prompt dùng ~21/109 |
| Lãnh đạo · công ty con · liên kết | đã lên web, chưa vào prompt |
| Khối ngoại theo ngày | **4–5 dòng/mã** — quá mỏng, cần sửa crawler trước |

Độ phủ prompt hiện ~**2%** của 1,04 MB dữ liệu mỗi mã (từ 1,4% ban đầu).
Làm hết P0–P2 dự kiến lên khoảng **3–4%**.

---

## Thứ tự đề xuất

**P0 → P1 → P2 → P5 → P3 → P4.** Đã làm xong P0, P1, P2; P5 sẵn sàng chạy.

Lý do đặt P5 (phủ sóng) trước P3: chạy ~57 giờ với prompt đã đủ chỉ tiêu (sau
P1) thì không phải chạy lại; còn lời dẫn biểu đồ sinh sau được, không ràng buộc.

---

## Cấu hình Local API — đã cố định

Khoá nằm ở **một chỗ duy nhất**: `Crawl Data/.env` → `LOCAL_API_KEY`. Cả 4 dự án
đọc chung từ đó (đã kiểm từng cái):

```
Crawl Data      → src/local_api.py
EconoPulse-VN   → modules/common/local_api.py
Test tool dự án → local_api.py
AI Analyze      → lib/local_api.js
```

Thứ tự tìm khoá: biến môi trường → `Crawl Data/.env`. Đường dẫn tới `.env` tính
từ `__file__` nên chạy từ thư mục nào cũng thấy.

**Cố ý KHÔNG nhúng khoá vào mã nguồn.** `.env` đã nằm trong `.gitignore`
(`Crawl Data/.gitignore:2`); nhúng vào file `.py`/`.js` là đẩy khoá thẳng vào
lịch sử git, không gỡ ra được. Đổi khoá thì sửa đúng một dòng trong `.env`, hoặc
dùng ô nhập trên bảng điều khiển `:5000` (`POST /set_local_api_key`).

---

## Trạng thái cuối đợt

| | |
|---|---|
| Test | Crawl Data **122** · EconoPulse **171** — xanh hết |
| Biểu đồ/mã | 20 → **28** (FPT), ACB 23 · **23 cái có lời dẫn AI** |
| Bố cục biểu đồ | lưới **3 cột** trên desktop, 1 cột trên điện thoại |
| Prompt/mã | 19.646 → **24.683** ký tự |
| Lượt AI/mã | 5 → **13** (5 chữ + 8 nhóm biểu đồ) |
| Thời gian/mã | 134s (chữ) + 230s (lời dẫn biểu đồ) ≈ **6 phút** |
| Dữ liệu Crawl Data trên :9999 | **18 nguồn · 4.045 bản ghi** |
| Kho phân tích | FPT xong; 1.530 mã còn lại chờ chạy |
| Dịch vụ | 9999 / 5000 / 5555 / 3333 / 4000 đều sống |

### Ước tính lại thời gian chạy toàn thị trường

1.531 mã × ~6 phút ⇒ **≈ 153 giờ** nếu làm cả lời dẫn biểu đồ. Đây là lý do
**P4 (cache + phân tầng) giờ đáng làm trước khi chạy phủ**: lời dẫn chỉ cần sinh
lại khi có báo cáo tài chính mới (mỗi quý), còn nhóm mã thanh khoản thấp thì
không cần lời dẫn.
