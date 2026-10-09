# Orus Quant

Sistema de análise quantitativa para criptomoedas, focado em **análise e decisão assistida** — não executa ordens. Coleta preços, calcula indicadores, combina tudo num **score único por ativo e por horizonte** (day trade, swing trade, hold), valida via backtesting e exibe num dashboard escuro estilo terminal financeiro.

## O que faz (v1)

- Preços e candles OHLC via Binance (`ccxt`), com persistência SQLite + cache TTL e fallback CoinGecko — fonte: `docs/arquitetura.md §5`.
- Indicadores em Python puro: RSI, MACD, médias 50/200, VWAP, volume, suporte/resistência.
- Score 0–100 por ativo × horizonte, mapeado em 5 cores (vermelho → verde).
- Backtest long-only exploratório por score (walk-forward com custos estimados e split desenvolvimento/avaliação OOS; walk-forward sozinho não é validação estatística nem garantia de lucro futuro).
- Dashboard React: tabela de sinais, gráfico de preço e painel de backtest.

## Stack

| Camada | Tech (v1, implementado) |
|---|---|
| API | FastAPI + Uvicorn + Pydantic |
| Dados | `ccxt` (Binance primário), `httpx` (CoinGecko backup), `sqlalchemy` (SQLite `backend/data/orus_quant.db`), `cachetools` (TTL) |
| Indicadores/backtest | Python puro, sem `pandas`/`ta`/`vectorbt` (planejados, não instalados — ver `docs/arquitetura.md §4`) |
| Frontend | React 18, Vite, lightweight-charts, TanStack Query, Tailwind |
| Testes | pytest, sem rede (`python -m pytest tests -q`) |

## Estrutura

```
backend/
├── api/          # assets, signals, backtest (routers FastAPI)
├── data/         # BinanceProvider (ccxt), CoinGeckoProvider (backup), StubProvider, cache TTL, orus_quant.db
├── indicators/   # RSI, MACD, MAs, VWAP, volume, range em Python puro (pandas/ta só se adotados — §4.2)
├── strategy/     # scoring + pesos por horizonte (config.py)
├── backtest/     # engine long-only próprio com walk-forward (vectorbt/backtrader só se adotados — §4.2)
├── models/       # schemas Pydantic + SQLite SQLAlchemy (db.py)
└── main.py
frontend/src/
├── components/   # SignalTable, PriceChart, BacktestPanel
├── pages/        # Dashboard
└── services/     # api.js (axios)
docs/             # arquitetura.md (canônico), prd.md, spec.md, sdd.md, como_rodar.md
```

## Como rodar

Pré-requisitos: Python 3.12+ e Node.js 22+.

Terminal 1 — backend:

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --port 8000
```

Terminal 2 — frontend:

```powershell
cd frontend
npm install
npm run dev
```

Abra http://127.0.0.1:5173. Detalhes e problemas comuns em [docs/como_rodar.md](docs/como_rodar.md).

### Variáveis de ambiente (opcional)

Copie os `.env.example` para `.env` se precisar:

- `backend`: `COINGECKO_API_KEY=` (só p/ fallback, funciona sem) · `ORUS_USE_STUB=1` usa dados locais, sem rede · `ORUS_USE_COINGECKO_ONLY=1` força CoinGecko · `ORUS_DB_PATH=` caminho do SQLite (default `backend/data/orus_quant.db`).
- `frontend`: `VITE_API_URL=/api` (dev usa o proxy do Vite).

## API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/health` | Status |
| `GET` | `/assets` | Ativos configurados |
| `GET` | `/assets/{symbol}/price` | Preço atual |
| `GET` | `/assets/{symbol}/ohlc?interval=&limit=` | Candles |
| `GET` | `/signals` | Todos os sinais |
| `GET` | `/signals/{symbol}[/{horizon}]` | Sinais de um ativo |
| `POST` | `/backtest/run` | Roda backtest (retorna `{id, result}`) |
| `GET` | `/backtest/{id}` | Resultado guardado |

Exemplo:

```powershell
curl http://127.0.0.1:8000/signals/BTC/swing_trade
curl -X POST http://127.0.0.1:8000/backtest/run -H "Content-Type: application/json" -d '{"symbol":"BTC","horizon":"swing_trade"}'
```

## Testes

```powershell
cd backend
python -m pytest tests -q
```

## Frequência de atualização

| Horizonte | TTL | Timeframe `ccxt` |
|---|---|---|
| Day trade | 2 min | `1h` |
| Swing trade | 15 min | `1d` |
| Hold | 6 h | `1w` |

Toda resposta de sinal traz `data_age_seconds` + `last_updated`.

## Fora do escopo (v1)

Execução automática de ordens, autenticação, WebSocket tempo real, alertas push/e-mail. Ver `docs/` para PRD, spec técnica, SDD e `docs/arquitetura.md` (fonte canônica do stack).
