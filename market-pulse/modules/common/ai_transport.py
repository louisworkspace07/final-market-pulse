# -*- coding: utf-8 -*-
"""AI Transport — façade dùng chung cho mọi module cần gọi AI.

Điểm vào chuẩn (thay vì import sâu vào modules.market_overview.gemini_transport):

    from modules.common.ai_transport import ask_gemini, open_session, parse_json_answer

Bên dưới là transport 3 kênh: LOCAL API (mặc định — server AI local tự phát
triển ở :4000, xem modules/common/local_api.py) → CDP (Chrome/Playwright, dự
phòng) → Gemini API key (dự phòng cuối). Kênh CDP có CIRCUIT BREAKER: lỗi >=
AI_BREAKER_FAIL_MAX lần trong AI_BREAKER_WINDOW_S giây → khóa CDP
AI_BREAKER_COOLDOWN_S giây. Trạng thái xem qua GET /api/gemini/cdp/status
(field "breaker" và "local_api").

Env điều phối:
- LOCAL_API_URL / LOCAL_API_MODEL / LOCAL_API_KEY / LOCAL_API_TIMEOUT — server local.
- AI_TRANSPORT_REALTIME=local|api|cdp|auto (mặc định auto → local trước) — ghi đè
  prefer="auto" của các luồng người-dùng-thấy (overview, factcheck, macro_ai...).
- AI_BREAKER_FAIL_MAX / AI_BREAKER_WINDOW_S / AI_BREAKER_COOLDOWN_S — ngưỡng breaker.

Lưu ý legal: transport chỉ chuyển prompt/response; việc chèn LEGAL_PROMPT_RULE và
check_payload là trách nhiệm của TỪNG engine gọi nó (giữ nguyên như hiện tại).
"""
from modules.market_overview.gemini_transport import (  # noqa: F401
    GeminiSession,
    ask_gemini,
    breaker_status,
    cdp_status,
    local_api_status,
    open_session,
    parse_json_answer,
    start_cdp_worker,
)

__all__ = [
    "GeminiSession", "ask_gemini", "breaker_status", "cdp_status",
    "local_api_status", "open_session", "parse_json_answer", "start_cdp_worker",
]
