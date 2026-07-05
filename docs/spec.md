# Spec técnica — Orus Quant

## 1. Stack e bibliotecas

### Backend (Python)

| Biblioteca | Função |
|---|---|
| `fastapi` | Framework da API |
| `uvicorn` | Servidor ASGI |
| `pydantic` | Validação de schemas de entrada/saída |
| `sqlalchemy` | ORM (SQLite v1 → PostgreSQL v2) |
| `pandas` / `numpy` | Manipulação de séries temporais e cálculo numérico |
| `ta` / `pandas-ta` | Indicadores técnicos prontos |
| `scipy` / `statsmodels` | Testes estatísticos e análise de séries temporais |
| `vectorbt` / `backtrader` | Motor de backtesting |
| `cachetools` | Cache in-memory com TTL |
| `python-dotenv` | Variáveis de ambiente |
| `ccxt` | Reservado para v2 (integração direta com exchanges) |

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

## 5. Frequência de atualização e cache

| Horizonte | TTL do cache | Observação |
|---|---|---|
| Day trade | 60–120s | Limitado pelo rate limit do CoinGecko free/demo; não é tempo real verdadeiro na v1 |
| Swing trade | 15–60 min | |
| Hold | 6–24h | |

Toda resposta de sinal deve incluir `data_age_seconds` e `last_updated`, para transparência com o usuário sobre a "frescura" do dado.

## 6. Tratamento de rate limit (CoinGecko)

- Respeitar o limite de requisições por minuto do plano demo/free.
- Fila/throttling de requisições no backend, para nunca disparar mais chamadas simultâneas do que o permitido.
- Fallback: se uma chamada falhar por rate limit, servir o último dado em cache (mesmo expirado) e sinalizar isso no `data_age_seconds`, em vez de quebrar a resposta da API.

## 7. Testes

- Motor de regras: testes unitários com indicadores mockados (sem chamar API externa), cobrindo casos de score alto, baixo e neutro por horizonte.
- Backtesting: validação walk-forward, não apenas backtest sobre uma única janela histórica, para reduzir risco de overfitting.
- Data Provider: testes de contrato garantindo que qualquer implementação (`CoinGeckoProvider`, futura `BinanceProvider`) responde na mesma interface/schema.

## 8. Evoluções futuras (fora da v1, mas já contempladas na arquitetura)

- Troca de `CoinGeckoProvider` por integração direta com exchange (`ccxt` ou WebSocket) para o horizonte day trade.
- Migração de SQLite para PostgreSQL.
- Cache distribuído (Redis) caso o sistema passe a atender múltiplos usuários.
- Autenticação e contas de usuário.