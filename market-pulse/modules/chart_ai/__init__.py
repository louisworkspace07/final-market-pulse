"""§18 · "AI đọc chart" — mô tả cấu trúc kỹ thuật của 1 mã bằng lời.

Người mới nhìn biểu đồ nến + bảng chỉ báo vẫn không biết "vậy là sao". Module này
đưa CHÍNH các con số kỹ thuật (không gửi ảnh) cho AI và bắt mô tả lại thành lời:
xu hướng, vị trí trong vùng S/R, trạng thái khối lượng, mốc cần theo dõi.

Ranh giới pháp lý: chỉ MÔ TẢ trạng thái quan sát được — không dự báo giá, không
khuyến nghị. Output đi qua check_payload trước khi trả về.
"""
from .engine import read_chart   # noqa: F401
