# Market Pulse — Thuật toán & kiến trúc xử lý (tri thức nội bộ cho AI)

> Nguồn: tài liệu "Thuật toán - góp ý" của nhóm dự án. Dùng để trả lời khi người
> dùng hỏi **hệ thống tính toán thế nào / dùng thuật toán gì / hướng phát triển**.
> Khi trích, nói rõ đây là phương pháp luận của Market Pulse, KHÔNG phải khuyến
> nghị đầu tư.

## 1. Ma trận thuật toán đang dùng

| Thuật toán / Công nghệ | Phân nhóm | Bản chất cốt lõi | Dữ liệu phù hợp |
|---|---|---|---|
| Random Forest | Machine Learning (Ensemble) | Học máy kết hợp theo phương pháp Bagging | Dữ liệu dạng bảng |
| XGBoost | Machine Learning (Ensemble) | Gradient Boosting tối ưu | Dữ liệu bảng, cần hiệu năng cao |
| LSTM | Deep Learning (RNN) | Mạng hồi quy kiểm soát dòng thông tin qua các cổng | Dữ liệu chuỗi thời gian |
| RAG | Kiến trúc GenAI | Kết hợp tra cứu tri thức động + mô hình ngôn ngữ | Văn bản không cấu trúc |
| Qiskit | Framework lượng tử (IBM) | Lập trình & mô phỏng mạch lượng tử | Trạng thái qubit, xác suất |
| PennyLane | Học máy lượng tử | Tối ưu vi phân trên phần cứng lượng tử | Mô hình lai lượng tử–cổ điển |

## 2. Pipeline 3 lớp — thuật toán gắn với tính năng nào

**Lớp RAW DATA & ANOMALY** → tính năng *Radar cảnh báo bất thường* (khối lượng đột
biến, khối ngoại đảo chiều).
- LSTM: học chuỗi thời gian để dự báo xu hướng nền.
- XGBoost: phân loại và phát hiện điểm lệch chuẩn.

**Lớp SCORING & OPTIMIZATION** → *Chấm điểm 360 & Dự báo vĩ mô*.
- Random Forest + mô hình định lượng: dự báo khả năng suy giảm sức khỏe tài chính
  dựa trên dữ liệu BCTC lịch sử.
- *Quantum Lab*: chuyển bài toán Markowitz sang dạng QUBO; PennyLane chạy QAOA
  (mô phỏng), Qiskit mô phỏng phân phối xác suất trạng thái qubit.

**Lớp INSIGHT & EXPLANATION** → *Soi Tin* và *Hỏi đáp phản biện*.
- RAG: tra cứu ngữ nghĩa trong kho tin tức + BCTC, trích dữ kiện gốc có mã dẫn chứng.

## 3. Xử lý lỗi dữ liệu chia tách (case mã VNX giảm 96,8%)

Giá thô từ API miễn phí **chưa hiệu chỉnh** — khi doanh nghiệp chia tách hoặc trả
cổ tức bằng cổ phiếu sẽ tạo "cú sụt giá ảo".

Giải pháp: module Data Cleaner đối chiếu lịch sử sự kiện doanh nghiệp. Khi phát
hiện biến động giá vượt 3 lần độ lệch chuẩn (3σ) trong phiên có sự kiện quyền, hệ
thống tính **giá điều chỉnh**:

```
P_adj = ( P_raw − D + (P_right × V_right) ) / ( 1 + α + β )
```

trong đó: `D` = cổ tức tiền mặt · `α` = tỷ lệ cổ phiếu thưởng/chia tách ·
`β` = tỷ lệ quyền mua cổ phiếu phát hành thêm với giá `P_right`.
Dữ liệu sạch này mới được nạp vào mô hình LSTM để quét dị biệt.

## 4. Luồng RAG của Soi Tin + màn lọc pháp lý

```
[Tin đồn từ người dùng]
   → [Tách nhận định bằng LLM] → [Tìm kiếm vector (RAG) trong kho tin + BCTC]
   → [Trích dữ kiện gốc có mã Audit Trail: [N..][E..]]
   → [LLM tổng hợp so sánh — chỉ nêu factual, KHÔNG kết luận]
   → [MÀN LỌC PHÁP LÝ (regex/classifier): quét 17 cụm từ cấm như "nên mua", "cắt lỗ"]
        ├─ phát hiện từ cấm → chặn tự động & báo lỗi schema
        └─ hợp lệ → hiển thị lên giao diện One Bar / Hỏi đáp
```

Cơ chế Audit Trail: RAG bắt buộc trả về siêu dữ liệu. Ví dụ: "Biên lợi nhuận gộp
quý 1/2026 giảm còn 12%", trái với tin đồn tăng trưởng mạnh trên mạng xã hội.

## 5. Chuẩn hoá "One Bar" và khắc phục Look-ahead Bias

Vấn đề: điểm sức khỏe tài chính cao nhưng giá vẫn giảm (danh mục thử nghiệm thua
VN-Index), do dòng tiền ngắn hạn chọn nhóm vốn hóa lớn và điểm số bị trễ vì lấy từ
BCTC đã công bố.

- **Giáo dục nhận thức F0**: thanh One Bar chia 2 phần rõ rệt — *Điểm Nội tại Biến
  động Chậm* (Altman Z'', Piotroski F) và *Điểm Dòng tiền Biến động Nhanh*.
- **Chuẩn hóa một chiều**: đưa các chỉ số ngược chiều về cùng thang 0–100 bằng hàm
  percentile lịch sử động (ví dụ P/E: thấp là tốt → đảo chiều percentile).
- **Khắc phục Look-ahead Bias**: khi backtest point-in-time, ngày đưa cổ phiếu vào
  danh mục chấm điểm phải là **T+90** sau khi kết thúc quý tài chính, để đảm bảo
  BCTC đã thực sự công bố tại thời điểm đó.

## 6. Quy trình Quantum Lab (PennyLane + Qiskit)

Giới hạn: máy/simulator lượng tử bị hạn chế số qubit và dễ nhiễu khi N mã lớn.

1. **Lọc cổ điển**: dùng Random Forest / bộ lọc sức khỏe rút 1.506 mã xuống N = 10–15.
2. **Xây dựng QUBO**: chuyển bài toán tối ưu Markowitz thành ma trận QUBO thông qua
   khẩu vị rủi ro λ thu từ quiz người dùng.
3. **Giải kết hợp**: PennyLane thiết lập mạch biến phân QAOA, tối ưu tham số góc
   quay Gamma/Beta bằng thuật toán cổ điển (COBYLA); Qiskit mô phỏng phân phối xác
   suất trạng thái qubit để tìm trạng thái năng lượng thấp nhất.
4. **Công bố công khai**: so sánh kết quả với Simulated Annealing để xuất **Optimality
   Gap** ngay trên giao diện.

## 7. Hướng phát triển giai đoạn tiếp theo

Nhóm đang ở Giai đoạn 1 — hoàn thiện trải nghiệm F0 và tính pháp lý:

1. **Đóng gói bộ lọc pháp lý**: hoàn thiện mã nguồn quét 17 cụm từ cấm cho mọi câu
   trả lời sinh ra từ module RAG.
2. **Xử lý dứt điểm dữ liệu rác**: áp dụng thuật toán hiệu chỉnh giá chia tách cho
   725 mã giá lịch sử, tránh hiểu lầm như case VNX.
3. **Kiểm thử UX/UI "3 giây"**: thử trên 10–20 F0 thật, đo xem họ có hiểu khu vực
   màu đỏ trên thanh One Bar nghĩa là "bất lợi" hay không, rồi tinh chỉnh độ tương
   phản trực quan thay vì giải thích bằng chữ.
