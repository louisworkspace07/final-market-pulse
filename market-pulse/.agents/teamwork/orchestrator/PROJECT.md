# Project: Market Pulse Vercel & Real-Data Integrity Remediation

## Architecture
- **Vercel Cloud**: Serverless Express proxy (`vercel-full-deployment/api/index.js`) rewriting all traffic to ngrok tunnel.
- **ngrok Tunnel**: `https://crease-unlined-cardinal.ngrok-free.dev` forwarding to `http://localhost:9999`.
- **Gateway (Port 9999)**: Flask application (`market-pulse/gateway/app.py`) providing main pages, stock analytics, and reverse-proxying:
  - `/embed_banggia/` -> `http://127.0.0.1:5555`
  - `/embed_econolens/` -> `http://127.0.0.1:3333`
  - `/embed_crawl/` -> `http://127.0.0.1:5000`
- **Microservices**:
  - `price-board` (Port 5555): Real-time price board with 1,430 tickers.
  - `econolens-chat` (Port 3333): AI-assisted market chat interface.
  - `data-crawler` (Port 5000): Ingestion and SQLite database management.
  - `HyperGravity-Core` (Port 59999): Local AI API compatible with OpenAI protocol.
- **Database**: `data-crawler/database/market.db` (987.8 MB SQLite, 3.46M records, 1,531 companies, 2.55M financials, 780k price bars up to 2026-11-13).

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Vercel & Tunnel Connectivity | Seamless HTTPS access to all pages and APIs via `vercel-full-deployment.vercel.app` | M2 | Explorer 1 |
| 2 | Reverse Proxy Embeds | `/embed_banggia/`, `/embed_econolens/`, `/embed_crawl/` load without 404 or Mixed Content | M2 | Explorer 1 |
| 3 | Remove Mock Fallback in Price Board | Eliminate hardcoded prices `[22.40..22.75]` and `random.randint` in `price-board/server.py` | M1 | Explorers 2 & 3 |
| 4 | Real VBP Calculation | Calculate Volume-by-Price using genuine OHLC bars without mock fallbacks | M1 | Explorers 2 & 3 |
| 5 | Real Scoring Engine (Altman Z'' & Piotroski F) | Mathematical scoring from `market.db` balance sheets and income statements | M3 | Explorer 2 |
| 6 | Real Valuation & Technical Ratios | P/E, P/B, EV/EBITDA, RSI-14, fractal pivots, regime calculated dynamically | M3 | Explorer 2 |
| 7 | Full Stock Universe Clickability (1,531 tickers) | All tickers clickable, loading real company details and analytics | M3 | Explorer 3 |
| 8 | Graceful Handling of Active Board Tickers | Handle 6 board tickers not in DB ('DMX', 'LPS', etc.) without crashing or 404 | M3 | Explorer 3 |
| 9 | Gateway CORS & Board Caching | Add CORS headers and 15s in-memory caching to prevent Vercel 502 timeouts | M2 | Explorer 1 |
| 10 | Forensic Integrity Audit & E2E Tests | Automated E2E verification and zero-mock audit by `teamwork_auditor` | M4 | All |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Clean Mock Data & Integrity Fixes | Remove mock fallback in `price-board/server.py` lines 298-310; wire real calculation; fix vnstock import | none | PLANNED |
| M2 | Vercel Proxy, Mixed Content & Gateway Hardening | Remove hardcoded `http://127.0.0.1:5555` in `app.js`; fix relative CSS in `index.html`; fix EconoLens API prefix; add Gateway CORS & board caching | M1 | PLANNED |
| M3 | Stock Universe Clickability & Non-DB Graceful Handling | Verify 1,531 tickers in `market.db`; add graceful live-data fallback for non-DB board tickers in Gateway | M2 | PLANNED |
| M4 | E2E Adversarial Testing & Forensic Audit | Run automated suite across Vercel & Gateway; full audit by `teamwork_auditor` (binary veto) | M3 | PLANNED |

## Interface Contracts
- **Gateway ↔ Price Board**: `/embed_banggia/` proxies HTML/JS/CSS; API calls within price board iframe must use relative paths or proxy via Gateway.
- **Gateway ↔ EconoLens Chat**: `/embed_econolens/` proxies chat UI; API calls must use `/embed_econolens/api/...` or Gateway `/api/pchat/...`.
- **Gateway ↔ Data Crawler**: `/embed_crawl/` proxies crawler dashboard; database access uses shared SQLite WAL file `data-crawler/database/market.db`.

## Code Layout
- `price-board/server.py`, `price-board/static/app.js`, `price-board/static/index.html`: owned by M1 & M2.
- `market-pulse/gateway/app.py`: owned by M2 & M3.
- `econolens-chat/public/app.js`: owned by M2.
- `data-crawler/`: owned by M1.
