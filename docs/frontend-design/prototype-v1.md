# Frontend Prototype V1 (Trader Terminal)

## 1. Scope

This prototype covers:
- A trader-style landing page with a clear login entry.
- Login/register flow.
- Authenticated watchlist management.
- Stock list and detail interaction.
- Up to 5 opened stock detail tabs with quick switching.
- Candlestick + baseline indicators in detail view: MA, MACD, BOLL, RSI, VOL.

This prototype intentionally does not include IV monitoring UI yet.

## 2. Information Architecture

Routes:
- `/` landing page (public)
- `/login` login/register page (public)
- `/demo` demo terminal (public, local synthetic data)
- `/terminal` trader terminal (authenticated)

Core modules:
- `entities/session`: auth token, current user session state
- `entities/watchlist`: add/list/delete watchlist tickers
- `entities/market`: fetch bars + compute indicators
- `pages/home`: marketing + CTA
- `pages/login`: auth entry
- `pages/demo-terminal`: design/prototype route decoupled from real backend pages
- `pages/terminal`: watchlist, opened tabs, detail charts and indicators
- `widgets/topbar`: global navigation + auth actions
- `widgets/stock-chart`: SVG candlestick and indicator charts

## 3. UX Flow

1. User enters `/` and sees market-style hero and CTA.
2. User clicks `Login` to `/login`.
3. User can alternatively click `Try Demo` to `/demo`.
4. On login success, redirect to `/terminal`.
5. User adds ticker to watchlist.
6. User clicks a ticker in watchlist to open detail tab.
7. Terminal keeps at most 5 opened tabs; user switches between tabs quickly.
8. Detail panel displays K-line and indicators for selected ticker.

## 4. Backend API Mapping

Existing APIs are enough for this prototype:
- `POST /api/v1/auth/register`
- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/watchlist`
- `POST /api/v1/watchlist`
- `DELETE /api/v1/watchlist/{ticker}`
- `GET /api/v1/market-data/bars`

Demo route (`/demo`) is intentionally backend-independent for faster design iteration.

Auth mode:
- Use Bearer token from login response.
- Include `Authorization: Bearer <token>` for watchlist and market-data requests.

## 5. Indicator Strategy

No new backend endpoint is required in V1.
Indicators are computed client-side from OHLCV bars:
- MA(20), MA(50)
- MACD(12,26,9)
- BOLL(20,2)
- RSI(14)
- VOL (raw volume bars)

## 6. Known Gaps for V2

Potential backend additions for next phase:
- Server-computed indicator endpoint to keep formulas consistent across clients.
- Multi-timeframe bars endpoint with normalized payload for charting.
- IV-specific endpoint (rank/percentile by ticker and contract buckets).

## 7. Acceptance for this prototype

- User can login and stay authenticated after refresh.
- Watchlist CRUD works under auth.
- Clicking ticker opens detail, max 5 tabs, and supports tab switching.
- Detail view shows candlestick + MA/MACD/BOLL/RSI/VOL.
