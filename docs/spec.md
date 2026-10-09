# Spec técnica — Orus Quant

## 1. Stack e bibliotecas

> Estado real: indicadores e backtest são **Python puro** (ver
> `arquitetura.md §4.1`). As libs abaixo marcadas **[planejado]** estão com
> requisitos comentados e **não** são instaladas nem importadas.

### Backend (Python) — implementado (v1)

| Biblioteca | Função |
|---|---|
| `fastapi` | Framework da API |
| `uvicorn` | Servidor ASGI |
| `pydantic` | Validação de schemas de entrada/saída |
| `ccxt` | Coleta primária via Binance (OHLCV + ticker) — `arquitetura.md §2.1/§5` |
| `sqlalchemy` | ORM — SQLite v1 (`backend/data/orus_quant.db`) → PostgreSQL v2 |
| `cachetools` | Cache in-memory com TTL por horizonte (camada quente; SQLite é a camada persistente) |
| `httpx` | Fallback CoinGecko (`CoinGeckoProvider`) quando a Binance falha |
| `python-dotenv` | Variáveis de ambiente |
| Python puro (`math`, listas) | Indicadores (`backend/indicators/core.py`) e backtest (`backend/backtest/engine.py`) — sem dependência numérica externa |

### Backend (Python) — planejado (não instalado)

| Biblioteca | Uso previsto |
|---|---|
| `pandas` / `numpy` **[planejado]** | Séries temporais em volume / numérico vetorizado (hoje: listas Python bastam) |
| `ta` **[planejado]** | Indicadores prontos, se trocar os próprios |
| `scipy` / `statsmodels` **[planejado]** | Testes estatísticos e séries temporais, na fase de validação formal |
| `vectorbt` / `backtrader` **[planejado]** | Motor de backtesting alternativo, se trocar o engine próprio |

### Frontend (React)

| Biblioteca | Função |
|---|---|
| `react` | Base do frontend |
| `axios` | Consumo da API |
| `lightweight-charts` | Gráfico de candlestick e indicadores |
| `@tanstack/react-query` | Cache e sincronização de dados da API |
| `tailwindcss` | Estilização |

## 2. Modelos de dados (Pydantic)

```python
class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

class PriceSnapshot(BaseModel):
    symbol: str
    price: float
    timestamp: datetime

class SignalScore(BaseModel):
    symbol: str
    horizon: Literal["day_trade", "swing_trade", "hold"]
    score: int              # 0–100
    color: Literal["red", "orange", "yellow", "light_green", "green"]
    label: str               # ex: "Fraco", "Neutro", "Forte"
    data_age_seconds: int
    last_updated: datetime

class BacktestResult(BaseModel):
    strategy_name: str
    win_rate: float
    cumulative_return: float
    sharpe_ratio: float
    max_drawdown: float
    period_start: date
    period_end: date
```

## 3. Endpoints da API

| Método | Rota | Descrição |
|---|---|---|
| `GET` | `/assets` | Lista os ativos configurados no sistema |
| `GET` | `/assets/{symbol}/price` | Preço atual do ativo |
| `GET` | `/assets/{symbol}/ohlc?interval=&limit=` | Candles históricos |
| `GET` | `/signals` | Tabela completa de sinais (todos os ativos x todos os horizontes) |
| `GET` | `/signals/{symbol}` | Sinais de um ativo específico, nos três horizontes |
| `GET` | `/signals/{symbol}/{horizon}` | Sinal de um ativo em um horizonte específico |
| `POST` | `/backtest/run` | Roda backtesting de uma estratégia sobre um período |
| `GET` | `/backtest/{id}` | Resultado de um backtest já executado |

### Exemplo de resposta — `GET /signals`

```json
[
  {
    "symbol": "BTC",
    "horizon": "day_trade",
    "score": 18,
    "color": "red",
    "label": "Fraco",
    "data_age_seconds": 47,
    "last_updated": "2026-07-05T14:32:10Z"
  },
  {
    "symbol": "BTC",
    "horizon": "hold",
    "score": 84,
    "color": "green",
    "label": "Forte",
    "data_age_seconds": 3600,
    "last_updated": "2026-07-05T12:00:00Z"
  }
]
```

## 4. Lógica de scoring

### 4.1 Fórmula geral

```
score = Σ (peso_i × indicador_normalizado_i)
```

Cada indicador é normalizado para uma escala 0–100 antes de entrar na soma ponderada. Os pesos são definidos por horizonte e devem ser calibráveis via backtesting (não hardcoded como constantes mágicas espalhadas pelo código — centralizar em arquivo de configuração por horizonte).

### 4.2 Indicadores e pesos por horizonte (ponto de partida, a validar via backtest)

**Day trade**
| Indicador | Peso sugerido |
|---|---|
| RSI curto (5m/15m) | 0.35 |
| Distância do VWAP | 0.35 |
| Spike de volume | 0.30 |

**Swing trade**
| Indicador | Peso sugerido |
|---|---|
| MACD | 0.30 |
| Cruzamento de médias (50/200) | 0.30 |
| RSI diário | 0.20 |
| Suporte/resistência | 0.20 |

**Hold**
| Indicador | Peso sugerido |
|---|---|
| Tendência de longo prazo | 0.50 |
| Posição no ciclo de mercado | 0.30 |
| Indicadores agregados (dominância, etc.) | 0.20 |

### 4.3 Mapeamento score → cor e label

| Faixa | Cor | Label |
|---|---|---|
| 0–20 | Vermelho | Fraco |
| 21–40 | Laranja | Fraco+ |
| 41–60 | Amarelo | Neutro |
| 61–80 | Verde-claro | Bom |
| 81–100 | Verde | Forte |

## 5. Frequência de atualização, cache e persistência

| Horizonte | TTL (cache quente) | Timeframe `ccxt` | Observação |
|---|---|---|---|
| Day trade | 60–120s | `1h` | Intraday via Binance REST; WebSocket fica p/ v2 |
| Swing trade | 15–60 min | `1d` | |
| Hold | 6–24h | `1w` | |

- Camada quente: `cachetools` TTL por horizonte.
- Camada persistente: SQLite via SQLAlchemy (`backend/data/orus_quant.db`, tabela `candles`) — `arquitetura.md §2.1`.
- Saneamento na entrada (`backend/data/validation.py`): ordenar por timestamp, deduplicar (último vence), descartar OHLC inválido (não-finito, preço ≤ 0, high/low inconsistentes) e **excluir o candle em formação** — só candles fechados alimentam indicadores.
- Toda resposta de sinal inclui `data_age_seconds`, `last_updated`, `stale` e `candles_n`: `last_updated` é o as-of do dado (timestamp do último candle **fechado** usado, não a hora do cálculo) e `data_age_seconds = now − last_updated`, recalculada a cada leitura — cache ou fallback nunca zeram a idade nem apresentam dado antigo como atual.

## 6. Tratamento de falhas e rate limit (Binance primário, CoinGecko backup)

- Binance via `ccxt` com `enableRateLimit=True`.
- Fallback CoinGecko: respeitar o limite de requisições por minuto do plano demo/free (throttling `~6s` entre chamadas).
- Ordem de fallback: `Binance → SQLite stale → CoinGeckoProvider → 502`. Se uma chamada falhar, servir o último dado persistido/em cache (mesmo expirado) e sinalizar isso com `stale: true` e `data_age_seconds` crescente (idade real desde o último candle fechado), em vez de quebrar a resposta da API — fallback jamais zera a idade nem finge dado atual.

## 7. Testes

- Motor de regras: testes unitários com indicadores mockados (sem chamar API externa), cobrindo casos de score alto, baixo e neutro por horizonte.
- Backtesting: backtest exploratório com walk-forward, custos estimados e split desenvolvimento (in-sample) vs avaliação reservada (out-of-sample), não apenas backtest sobre uma única janela histórica, para reduzir risco de overfitting. Walk-forward com os mesmos parâmetros, por si só, não é validação estatística completa nem prova de lucro futuro: declare desempenho pelo OOS intocado e avalie estabilidade entre janelas/regimes.
- Data Provider: testes de contrato garantindo que qualquer implementação (`BinanceProvider` primário, `CoinGeckoProvider` backup, `StubProvider` p/ testes) responde na mesma interface/schema.

## 8. Evoluções futuras (fora da v1, mas já contempladas na arquitetura)

- WebSocket da Binance para o horizonte day trade (tempo real verdadeiro).
- Migração de SQLite para PostgreSQL.
- Cache distribuído (Redis) caso o sistema passe a atender múltiplos usuários.
- Autenticação e contas de usuário.