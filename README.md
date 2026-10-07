# Orus Quant

Sistema de análise quantitativa para criptomoedas, focado em **análise e decisão assistida** — não executa ordens. Coleta preços, calcula indicadores, combina tudo num **score único por ativo e por horizonte** (day trade, swing trade, hold), valida via backtesting e exibe num dashboard escuro estilo terminal financeiro.

## O que faz (v1)

- Preços e candles OHLC via CoinGecko, com cache local e fallback em rate limit.
- Indicadores em Python puro: RSI, MACD, médias 50/200, VWAP, volume, suporte/resistência.
- Score 0–100 por ativo × horizonte, mapeado em 5 cores (vermelho → verde).
- Backtest long-only por score com validação walk-forward (win rate, retorno, Sharpe, drawdown).
- Dashboard React: tabela de sinais, gráfico de preço e painel de backtest.

## Stack

| Camada | Tech |
|---|---|
| API | FastAPI + Uvicorn + Pydantic |
| Dados | `httpx` (CoinGecko), `cachetools` (TTL por horizonte) |
| Frontend | React 18, Vite, lightweight-charts, TanStack Query, Tailwind |
| Testes | pytest (44 testes, sem rede) |

## Estrutura

```
backend/
├── api/          # assets, signals, backtest (routers FastAPI)
├── data/         # PriceDataProvider, CoinGeckoProvider, StubProvider, cache
├── indicators/   # RSI, MACD, MAs, VWAP, volume, range (Python puro)
├── strategy/     # scoring + pesos por horizonte (config.py)
├── backtest/     # engine long-only com walk-forward
├── models/       # schemas Pydantic
└── main.py
frontend/src/
├── components/   # SignalTable, PriceChart, BacktestPanel
├── pages/        # Dashboard
└── services/     # api.js (axios)
docs/             # prd.md, spec.md, sdd.md
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

Abra http://127.0.0.1:5173. Detalhes e problemas comuns em [COMO_RODAR.md](COMO_RODAR.md).

### Variáveis de ambiente (opcional)

Copie os `.env.example` para `.env` se precisar:

- `backend`: `COINGECKO_API_KEY=` (funciona sem, no plano free) · `ORUS_USE_STUB=1` usa dados locais determinísticos, sem rede.
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

| Horizonte | TTL do cache |
|---|---|
| Day trade | 2 min |
| Swing trade | 15 min |
| Hold | 6 h |

Toda resposta de sinal traz `data_age_seconds` + `last_updated`.

## Fora do escopo (v1)

Execução automática de ordens, autenticação, WebSocket/exchanges diretas, alertas push/e-mail. Ver `docs/` para PRD, spec técnica e SDD.
