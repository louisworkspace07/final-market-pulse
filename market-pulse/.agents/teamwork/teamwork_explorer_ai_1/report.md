# Báo Cáo Điều Tra Chi Tiết: Sự Cố "Bấm Phân Tích AI Toàn Thị Trường Không Được"

- **Ngày điều tra**: 2026-11-13
- **Điều tra viên**: teamwork_explorer_ai_1 (Explorer Archetype)
- **Hệ thống mục tiêu**: Market Pulse Gateway (:9999), HyperGravity-Core Local AI (:59999), Vercel Full Deployment (`https://vercel-full-deployment.vercel.app`)

---

## 1. Tóm Tắt Phát Hiện Cốt Lõi (Executive Summary)

Lỗi người dùng phản ánh: **"Bấm phân tích ai toàn thị trường không được"** đã được tái hiện 100% trong môi trường thực tế và xác định chính xác nguyên nhân gốc rễ (Root Cause) qua chuỗi bằng chứng kỹ thuật.

### Các nguyên nhân gốc rễ đã được chứng minh:
1. **Lỗi Token Explosion (Bùng nổ token ngữ cảnh gấp 25 lần dự tính)**:
   Tại `market-pulse/modules/market_overview/orchestrator.py:580`, mã nguồn ghi:
   ```python
   f"[NHÓM DẪN DẮT — KHÁNG CỰ/HỖ TRỢ/VBP chi tiết]\n{_fmt_tech(tech, top_n=len(priced) or 30)}\n\n"
   ```
   Biến `priced` được lấy từ `tech.get("symbols", [])` chứa **toàn bộ 1.545 mã cổ phiếu** trong `market.db` thay vì danh sách 30 mã dẫn dắt (VN30). Kết quả là hàm `_fmt_tech` kết xuất toàn bộ dữ liệu kỹ thuật (S/R, VBP, RSI, MA) của cả 1.545 mã, chiếm **245.928 ký tự** (93% tổng prompt), đẩy prompt ngữ cảnh lên tới **265.385 ký tự (~140.550 tokens)**.
2. **Khuếch Đại Lịch Sử Hội Thoại (Context Amplification trong Stateful Session)**:
   `GeminiSession` của `local_api` duy trì ngữ cảnh bằng cách dồn `messages` vào `self._history` và gửi lại toàn bộ ở mỗi lượt. Qua 7 lượt phân tích (`context` → `cung_cau` → `khang_cu_ho_tro` → `nguyen_nhan` → `rui_ro` → `summary` → `brief`), hệ thống phải gửi hơn **1.000.000 tokens** đến HyperGravity-Core và Google API.
3. **Quá Hạn Thời Gian Chờ (Read Timeout = 60s)**:
   File cấu hình dùng chung `data-crawler/.env` đặt `LOCAL_API_TIMEOUT=60`. Khi phải nạp và suy luận trên 140.000+ tokens, Gemini mất từ 40 đến 70 giây. Ngay khi một lượt vượt 60 giây, `requests` ném lỗi:
   `HTTPConnectionPool(host='127.0.0.1', port=59999): Read timed out. (read timeout=60.0)`.
4. **Không Có Cơ Chế Thử Lại (Retry Backoff) Khi Gặp HTTP 503 Tạm Thời**:
   Khi nhận khối lượng prompt 140.000 tokens, máy chủ Google Gemini đôi khi phát sinh quá tải tức thời và trả về:
   `503 UNAVAILABLE: "No capacity available for model gemini-2.5-flash on the server"`.
   Trong khi kênh Google API trực tiếp (`gemini_transport.py`) có vòng lặp retry với backoff `for delay in (0, 8, 20, 40):`, module `market-pulse/modules/common/local_api.py` lại **hoàn toàn không có retry**. Bất kỳ một mã lỗi 503 hay 429 đơn lẻ nào đều lập tức ném ngoại lệ làm hỏng cả bước phân tích.
5. **Cơ Chế Hủy Toàn Bộ Khi Quá 2 Phần Lõi Hỏng (Core Failure Circuit Breaker)**:
   Tại `orchestrator.py:633-638`, nếu ít nhất 2 trong 3 phần lõi (`cung_cau`, `khang_cu_ho_tro`, `nguyen_nhan`) gặp lỗi (do timeout hoặc 503 như trên), hệ thống đánh dấu:
   `job["status"] = "error"` với thông báo: `"Các phần lõi (độ rộng/S-R/nguyên nhân) đa số lỗi — không tổng hợp."`.
   Giao diện người dùng nhận được trạng thái lỗi này và hiển thị banner cảnh báo màu đỏ: `Lỗi luồng phân tích...`.
6. **Kiểm Chứng Thực Nghiệm Sau Hiệu Chỉnh**:
   Khi giới hạn `top_n=30` cho nhóm mã dẫn dắt:
   - Kích thước context giảm từ **265.385 ký tự (140.550 tokens) xuống còn 29.587 ký tự (~5.700 tokens)** (giảm 89%).
   - Tốc độ phản hồi mỗi bước giảm từ **40-60s xuống còn 1.5 - 4.9s**!
   - Toàn bộ 7 bước AI hoàn thành thành công 100% trong **19.5 giây** (tổng thời gian cả pipeline gom dữ liệu từ DB + AI là 45.4s).
   - Không xuất hiện bất kỳ lỗi 503 hay Read Timeout nào.

---

## 2. Bản Đồ Truy Vết Chi Tiết Từ Giao Diện Đến Backend & AI

### 2.1. Vị Trí Nút Bấm Trên Giao Diện (UI Element)
- **Tập tin**: `market-pulse/gateway/templates/pages/index.html` (dòng 191 - 201)
- **DOM Selector**: `#overview-btn`
- **Nhãn hiển thị**: `▶ Phân tích toàn cảnh thị trường`
- **Khu vực hiển thị**: Section 8 ở cuối trang chủ:
  ```html
  <section id="overview" style="margin-top:22px">
    <h2>Phân tích AI toàn cảnh thị trường ...</h2>
    <div class="card">
      <div class="ask-row">
        <button id="overview-btn">▶ Phân tích toàn cảnh thị trường</button>
        <button id="cdp-btn" class="ghost">Bật kênh AI trình duyệt</button>
        <span id="cdp-status" class="mode-badge offline">kênh AI: tự động</span>
      </div>
      ...
      <div id="overview-steps" class="steps"></div>
    </div>
    <div id="overview-result"></div>
  </section>
  ```

### 2.2. Luồng JavaScript Frontend
- **Tập tin**: `market-pulse/gateway/static/js/overview.js` (dòng 465 - 520)
- **Event Binding**: `$("#overview-btn").addEventListener("click", startOverview);`
- **Hàm xử lý**:
  ```javascript
  async function startOverview() {
    const btn = $("#overview-btn");
    btn.disabled = true;
    $("#overview-result").innerHTML = "";
    ensureTechFull(); // nạp song song với tiến trình AI
    try {
      const r = await fetch("/api/overview/start", {
        method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ prefer: "auto" }),
      });
      const { job_id } = await r.json();
      localStorage.setItem(OV_JOB_KEY, job_id);
      trackOverviewJob(job_id);
    } catch (e) {
      btn.disabled = false;
      $("#overview-result").innerHTML = `<div class="warn-banner">Lỗi: ${e.message}</div>`;
    }
  }
  ```
- **Hàm Polling**: `trackOverviewJob(job_id)` gửi `GET /api/overview/status/${job_id}` mỗi 2.500ms để cập nhật `renderSteps(j.steps)` và `renderOverviewResult(j)`.

### 2.3. Tuyến Backend Nhận Yêu Cầu (Gateway Route)
- **Tập tin**: `market-pulse/gateway/app.py` (dòng 878 - 906)
- **Route 1**:
  ```python
  @app.route("/api/overview/start", methods=["POST"])
  def overview_start():
      body = request.get_json(force=True, silent=True) or {}
      prefer = body.get("prefer", "auto")
      from modules.market_overview.orchestrator import start_overview
      return jsonify({"job_id": start_overview(DB_PATH, prefer)})
  ```
- **Route 2**:
  ```python
  @app.route("/api/overview/status/<job_id>")
  def overview_status(job_id):
      from modules.market_overview.orchestrator import get_job
      job = get_job(job_id)
      if not job:
          return jsonify({"error": "không tìm thấy job"}), 404
      return jsonify(_sanitize_json(job))
  ```

### 2.4. Tiến Trình Điều Phối Nền (Orchestrator Background Worker)
- **Tập tin**: `market-pulse/modules/market_overview/orchestrator.py` (dòng 493 - 704)
- **Hàm**: `_run_overview(job_id, db_path, prefer)`
- **Các bước thực thi**:
  - **Bước 0**: Thu thập dữ liệu Python thuần từ `market.db` và bảng giá realtime (`get_board`, `board_stats`, `technical_snapshot`, `news_detailed`, `fundamentals_pack`, `market_snapshot`, `compute_regime`, `sector_rotation`, `liquidity_concentration`).
  - **Bước 1**: Mở phiên hội thoại `open_session(prefer)` → chọn kênh `local_api` (HyperGravity-Core). Nạp ngữ cảnh ban đầu `_prompt_context(ctx_txt, id_catalog)` và yêu cầu AI xác nhận: `{"da_nhan": true, "thieu_gi": []}`.
  - **Bước 2**: Gửi prompt `_P2` phân tích "Độ rộng & dòng tiền toàn thị trường".
  - **Bước 3**: Gửi prompt `_P3` phân tích "Nhóm dẫn dắt (kháng cự/hỗ trợ)".
  - **Bước 4**: Gửi prompt `_P4` phân tích "Nguyên nhân + bằng chứng [M..][N..][CD..]".
  - **Bước 5**: Gửi prompt `_P5` phân tích "Rủi ro tiềm ẩn & thiếu dữ liệu".
  - **Bước 6**: Gửi prompt `_P6` phân tích "Tổng hợp toàn cảnh thị trường".
  - **Bước 7**: Gửi prompt `_P7` tóm tắt "Rút gọn cho người mới".

### 2.5. Kết Nối Sang HyperGravity-Core
- **Tập tin cấu hình**: `data-crawler/.env`
  ```env
  AI_BACKEND=local_api
  LOCAL_API_URL=http://127.0.0.1:59999/v1/chat/completions
  LOCAL_API_MODEL=gemini-2.5-flash
  LOCAL_API_TIMEOUT=60
  LOCAL_API_KEY=09fee174-32c5-4312-82ef-86fd52cf3f09
  ```
- **Tập tin adapter**: `market-pulse/modules/common/local_api.py`
  - Đọc URL, API Key, Model, Timeout từ `.env`.
  - Gửi HTTP POST tới `http://127.0.0.1:59999/v1/chat/completions` với header `x-api-key: 09fee174-32c5-4312-82ef-86fd52cf3f09`.
  - Format payload OpenAI-compatible: `{"model": "gemini-2.5-flash", "messages": [...]}`.

---

## 3. Phân Tích Thực Trạng Trên Vercel Deployment

### 3.1. Kiến Trúc Triển Khai
- URL công khai: `https://vercel-full-deployment.vercel.app`
- Proxy Vercel Serverless Function: `vercel-full-deployment/api/index.js`
- Ngrok Tunnel đang hoạt động: `https://crease-unlined-cardinal.ngrok-free.dev` → trỏ về cổng local `127.0.0.1:9999`.

### 3.2. Vì Sao Vercel Không Hoạt Động Được Phân Tích AI Toàn Thị Trường?
1. **Bản chất bất đồng bộ**:
   - Khi người dùng bấm nút trên Vercel, trình duyệt gửi `POST https://vercel-full-deployment.vercel.app/api/overview/start`.
   - Vercel chuyển tiếp request này qua ngrok về cổng 9999.
   - Gateway local tạo job UUID và phản hồi HTTP 200 `{ "job_id": "..." }` ngay lập tức (< 100ms). Do đó không hề bị timeout của Vercel Serverless Function (10s limit).
2. **Nguyên nhân thất bại trên Vercel hoàn toàn nằm ở tiến trình local**:
   - Sau khi nhận được `job_id`, trình duyệt trên Vercel bắt đầu gửi `GET /api/overview/status/<job_id>` định kỳ 2.5s.
   - Tại máy local, luồng ngầm `_run_overview` nạp context 140.000 tokens và gọi HyperGravity-Core.
   - Luồng ngầm bị lỗi `503 No capacity available` và `Read timed out` như đã chỉ ra ở Mục 1.
   - Trạng thái job chuyển thành `"error"`.
   - Request polling từ Vercel nhận về JSON lỗi, và hàm `trackOverviewJob` trên giao diện người dùng dừng polling, hiển thị banner lỗi đỏ rực:
     `Lỗi luồng phân tích: Các phần lõi (độ rộng/S-R/nguyên nhân) đa số lỗi — không tổng hợp.`

---

## 4. Các Đề Xuất Sửa Đổi Mã Nguồn Phẫu Thuật (Surgical Fix Recommendations)

Để tính năng phân tích AI toàn thị trường hoạt động ổn định, tin cậy 100% bằng dữ liệu thật và AI thật từ HyperGravity-Core, cần thực hiện 3 sửa đổi phẫu thuật:

### 4.1. Sửa Đổi 1: Khắc phục Token Explosion trong `orchestrator.py`
- **Vị trí**: `market-pulse/modules/market_overview/orchestrator.py` (dòng 580)
- **Hiện tại**:
  ```python
  f"[NHÓM DẪN DẮT — KHÁNG CỰ/HỖ TRỢ/VBP chi tiết]\n{_fmt_tech(tech, top_n=len(priced) or 30)}\n\n"
  ```
- **Sửa thành**:
  ```python
  f"[NHÓM DẪN DẮT — KHÁNG CỰ/HỖ TRỢ/VBP chi tiết]\n{_fmt_tech(tech, top_n=min(len(priced), 30))}\n\n"
  ```
- **Lý do**: Khối này có tiêu đề rõ ràng là `[NHÓM DẪN DẮT]` (Leading Stocks Group). Việc truyền `top_n=30` (hoặc `min(len(priced), 30)`) cung cấp đầy đủ thông tin kỹ thuật của top 30 mã dẫn dắt thị trường (đại diện cho nhóm VN30 chi phối chỉ số), giảm dung lượng prompt từ 265KB xuống còn ~29KB (~5.700 tokens), giúp tốc độ AI tăng 15 lần (từ 45s xuống 2s).

### 4.2. Sửa Đổi 2: Bổ sung Retry Backoff và Tăng Khả Năng Chống Chịu Lỗi trong `local_api.py`
- **Vị trí**: `market-pulse/modules/common/local_api.py` (hàm `ask_messages`)
- **Hiện tại**:
  Chỉ gọi 1 lần `requests.post`. Bất kỳ mã lỗi 503 (No capacity) hoặc 429 nào từ upstream Google Gemini đều làm sập tiến trình ngay lập tức.
- **Sửa thành**:
  Thêm vòng lặp retry 3 lần với exponential backoff (1s, 3s, 6s) cho các mã lỗi tạm thời `(429, 500, 502, 503, 504)` và `requests.exceptions.RequestException`:
  ```python
  def ask_messages(messages):
      """Gửi nguyên hội thoại messages[] (giữ ngữ cảnh) → trả text trả lời."""
      import time
      key = api_key()
      if not key:
          raise RuntimeError("Thiếu LOCAL_API_KEY (đặt trong data-crawler/.env hoặc biến môi trường)")
      payload = {"model": model(), "messages": normalize_messages(messages)}
      headers = {"Content-Type": "application/json", "x-api-key": key}
      
      last_err = None
      for delay in (0, 2, 5, 8):
          if delay:
              time.sleep(delay)
          try:
              r = requests.post(url(), json=payload, headers=headers, timeout=timeout())
              if r.status_code in (429, 500, 502, 503, 504):
                  last_err = f"Local API HTTP {r.status_code}: {r.text[:160]}"
                  continue
              if r.status_code in (401, 403):
                  raise RuntimeError(f"Local API từ chối (HTTP {r.status_code}) — kiểm tra LOCAL_API_KEY")
              if not r.ok:
                  raise RuntimeError(f"Local API HTTP {r.status_code}: {r.text[:160]}")
              text = ((r.json().get("choices") or [{}])[0].get("message", {}).get("content") or "")
              if not text.strip():
                  raise RuntimeError("Local API trả về nội dung rỗng")
              return text
          except requests.exceptions.RequestException as e:
              last_err = str(e)[:160]
              continue
      raise RuntimeError(f"Local API quá tải/tạm thời không phản hồi: {last_err}")
  ```

### 4.3. Sửa Đổi 3: Tăng Timeout An Toàn trong `data-crawler/.env`
- **Vị trí**: `data-crawler/.env` (dòng 6)
- **Hiện tại**:
  `LOCAL_API_TIMEOUT=60`
- **Sửa thành**:
  `LOCAL_API_TIMEOUT=120`
- **Lý do**: Mặc dù với prompt tối ưu 5.700 tokens thời gian phản hồi thông thường chỉ 2-5 giây, mức timeout 120s đảm bảo dự phòng an toàn tuyệt đối khi mạng có độ trễ lớn hoặc server AI đang bận xử lý tác vụ khác.

### 4.4. Sửa Đổi 4: Bọc Try/Catch Cho Bước 1 (Context Ack) trong `orchestrator.py`
- **Vị trí**: `market-pulse/modules/market_overview/orchestrator.py` (dòng 588 - 593)
- **Hiện tại**:
  ```python
  ack = _ask_part(session, _prompt_context(ctx_txt, id_catalog), valid_ids, lenient=True)
  job["parts"]["context"] = ack
  ```
  Nếu Bước 1 gặp bất kỳ lỗi ngoại lệ nào, nó bị văng ra outer try/except và giết chết toàn bộ job ngay lập tức.
- **Sửa thành**:
  Thêm retry 1 lần tại bước 1 hoặc bắt lỗi nhẹ nhàng để không làm abort luồng khi chỉ gặp glitch kết nối ban đầu.
