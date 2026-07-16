"""Ảnh 17 · AI so sánh 2 mã — diễn giải khác biệt theo từng mặt, có dẫn chứng số.

Trang So sánh trước đây chỉ có thanh đếm tiêu chí + chart hiệu suất: người dùng
thấy "VNM nhỉnh 7/9" nhưng không hiểu NHỈNH Ở CHỖ NÀO và vì sao. Module này nạp
số liệu 2 mã (đã có sẵn trong market.db / health_scores) rồi hỏi AI diễn giải.

RÀNG BUỘC PHÁP LÝ (Luật CK 2019 Điều 71): TUYỆT ĐỐI không kết luận "nên chọn mã
nào" — mọi output đi qua check_payload trước khi trả về.
"""
from .engine import compare_ai   # noqa: F401
