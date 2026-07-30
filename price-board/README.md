# Price Board — Bảng giá realtime

Bảng giá HOSE/HNX/UPCOM thời gian thực (qua `vnstock.Trading.price_board()`, không cần Playwright/Chrome cho luồng giá) + phiên Gemini Web dùng chung qua Chrome CDP để sinh phân tích kháng cự/hỗ trợ từng mã cho các module AI khác trong hệ thống.

## Cài đặt

```powershell
pip install -r requirements.txt
python -m playwright install chromium   # chỉ cần cho kênh phân tích Gemini/CDP
```

## Chạy

```powershell
python server.py            # → http://localhost:5555
```

## API chính

| Route | Mô tả |
|---|---|
| `GET /api/stocks` | Bảng giá realtime toàn thị trường |
| `GET /api/history/<symbol>` | Lịch sử giá theo mã |
| `GET /api/vbp/<symbol>` | Volume-by-Price theo mã |
| `POST /api/analyze` | Yêu cầu phân tích kháng cự/hỗ trợ qua Gemini |
| `GET /api/gemini/status` · `POST /api/gemini/reset_scan` · `POST /api/gemini/toggle_auto_scan` | Điều khiển luồng quét Gemini nền |
| `POST /api/login_gemini` | Đăng nhập phiên Gemini Web (một lần, dùng chung `gemini_profile`) |

## Ghi chú

- `LOCAL_API_KEY` đọc dùng chung từ `../data-crawler/.env` (xem `local_api.py`).
- Service này được `market-pulse/gateway/launcher.py` tự động khởi động khi chạy `START_ALL.bat` ở thư mục gốc.
