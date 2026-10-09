# SDD — Orus Quant (System Design Document)

## 1. Visão geral da arquitetura

```
Fonte de dados externa (Binance via ccxt na v1, CoinGecko como backup)
        ↓
Camada de coleta de dados (Data Provider)
        ↓
Persistência local SQLite + cache TTL por horizonte
        ↓
Indicadores técnicos
        ↓
Motor de regras (score por horizonte)
        ↓
Backtesting engine
        ↓
API (FastAPI)
        ↓
Frontend (React)
        ↓
Usuário (decisão)
```

Escopo: análise e decisão assistida. Sem execução automática de ordens.

## 2. Camadas

### 2.1 Data Provider (coleta de dados)
Camada de abstração responsável por buscar preços e normalizar em candles OHLCV. Definida como uma interface, para permitir trocar a fonte de dados sem afetar as camadas acima.

```python
class PriceDataProvider(ABC):
    def get_current_price(self, symbol: str) -> PriceSnapshot: ...
    def get_ohlc(self, symbol: str, interval: str, limit: int) -> list[Candle]: ...
    def get_volume(self, symbol: str, interval: str) -> VolumeData: ...
```

- **v1**: `BinanceProvider` (via `ccxt`, `arquitetura.md §2.1`) implementa essa interface; `CoinGeckoProvider` é o backup e `StubProvider` serve dev/testes.
- Timeframes por horizonte: day trade `1h`, swing trade `1d`, hold `1w` (ver `spec.md §5`).

### 2.2 Cache + persistência
Cache local com TTL diferenciado por horizonte + persistência SQLite, para reduzir chamadas à API externa e servir dado stale em falha (`arquitetura.md §2.1`).

| Horizonte | TTL | Timeframe `ccxt` |
|---|---|---|
| Day trade | 1–2 minutos | `1h` |
| Swing trade | 15–60 minutos | `1d` |
| Hold | 6–24 horas | `1w` |

Implementação v1: quente in-memory com TTL (`cachetools`) + fria em SQLite via SQLAlchemy (`backend/data/orus_quant.db`, tabela `candles`). Redis fica como evolução natural caso o projeto cresça (ex: múltiplos usuários, múltiplas instâncias).

### 2.3 Indicadores técnicos
Transformam candles em variáveis analisáveis, agrupadas por horizonte:

| Horizonte | Indicadores típicos |
|---|---|
| Day trade | RSI curto (5m/15m), distância do VWAP, spikes de volume |
| Swing trade | MACD, médias móveis (50/200), RSI diário, suporte/resistência |
| Hold | Posição no ciclo de mercado, tendência de longo prazo, indicadores agregados de dominância |

### 2.4 Motor de regras (score)
Modelo proprietário que combina indicadores normalizados em um score de 0 a 100 por ativo e por horizonte:

```
score = Σ (peso_i × indicador_normalizado_i)
```

Cada horizonte tem seu próprio conjunto de pesos e indicadores. O motor é Python puro, sem dependência direta de rede, para ser testável isoladamente.

### 2.5 Mapeamento score → cor
```
0–20   → vermelho       (fraco)
21–40  → laranja
41–60  → amarelo         (neutro)
61–80  → verde-claro
81–100 → verde            (forte)
```

### 2.6 Backtesting engine
Roda as regras contra dados históricos e mede performance (taxa de acerto, retorno acumulado, Sharpe ratio, drawdown máximo), incluindo walk-forward validation para reduzir risco de overfitting.

### 2.7 API (FastAPI)
Expõe dados calculados (preços, indicadores, sinais, resultados de backtest). Detalhes de endpoints e schemas ficam no `spec.md`.

### 2.8 Frontend (React)
Dashboard com:
- Tabela de sinais (ativo x horizonte), com células coloridas pela escala de score.
- Gráfico de preço com indicadores sobrepostos (`lightweight-charts`).
- Relatório de backtest.
- Tema visual escuro (`#0A0A0A` como base, verde para força/ganho, vermelho reservado a alertas).

## 3. Fluxo de dados (exemplo: atualização de sinal de swing trade)

1. Scheduler dispara a cada N minutos (conforme TTL do horizonte).
2. Backend verifica cache; se expirado, chama `PriceDataProvider.get_ohlc()`.
3. Indicadores são recalculados a partir dos candles atualizados.
4. Motor de regras recalcula o score do ativo para aquele horizonte.
5. Resultado é armazenado (cache + persistência) com timestamp de atualização.
6. Frontend consulta a API, que retorna o score, cor e `data_age_seconds`.

## 4. Estrutura de pastas

```
orus-quant/
├── backend/
│   ├── data/          # coleta e cache de dados (providers)
│   ├── indicators/    # cálculo de indicadores técnicos
│   ├── strategy/       # motor de regras (modelo proprietário)
│   ├── backtest/       # engine de backtesting e métricas
│   ├── api/             # endpoints FastAPI
│   ├── models/          # modelos SQLAlchemy / schemas Pydantic
│   └── main.py
└── frontend/
    └── src/
        ├── components/  # gráficos, cards, tabela de sinais
        ├── pages/        # dashboard, backtest, configurações
        └── services/     # chamadas à API
```

## 5. Persistência

- **v1**: SQLite — sem necessidade de servidor, adequado para prototipagem e uso pessoal.
- **v2**: PostgreSQL, caso o projeto evolua para múltiplos usuários ou volume maior de dados históricos.

## 6. Decisões de design e trade-offs

| Decisão | Alternativa considerada | Motivo da escolha |
|---|---|---|
| Binance/`ccxt` na v1 | Só CoinGecko | Granularidade intraday real p/ day trade; CoinGecko fica como backup (arquitetura.md §5) |
| Interface `PriceDataProvider` | Acoplar direto à Binance | Permite trocar fonte de dados sem reescrever motor de regras/backtesting |
| SQLite na v1 | PostgreSQL desde o início | Menor fricção para projeto pessoal; migração é direta quando necessário |
| Cache in-memory com TTL | Redis desde a v1 | Complexidade desnecessária para uso de um único usuário |
| Score contínuo (0–100) mapeado em 5 cores | Categorias discretas direto do modelo | Mais flexível para recalibrar limiares sem mudar o modelo |

## 7. Riscos técnicos

- Rate limit da Binance mitigado com `enableRateLimit` + SQLite stale; se a Binance falhar, o fallback CoinGecko free/demo pode limitar a frequência do day trade.
- Ausência de WebSocket na v1 limita o tempo real verdadeiro no intraday (REST `1h` no day trade).
- Necessidade de revalidar pesos do motor de regras periodicamente para evitar overfitting aos dados históricos.