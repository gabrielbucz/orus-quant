Orus Quant — Documento de Arquitetura
1. Visão geral
Orus Quant é um sistema de análise quantitativa para o mercado de criptomoedas. A v1 tem como objetivo coletar dados históricos de preço, calcular indicadores técnicos, aplicar regras de decisão baseadas em modelos estatísticos próprios, validar essas regras via backtesting, e apresentar tudo em um dashboard web.
Escopo da v1: análise e decisão assistida, não execução automática de ordens.
---
2. Camadas da arquitetura
```
Exchange (dados externos)
        ↓
Backend Python
   ├── Coleta de dados
   ├── Indicadores técnicos
   ├── Motor de regras (modelo quantitativo próprio)
   └── Backtesting engine
        ↓
API (FastAPI)
        ↓
Frontend (React)
        ↓
Usuário (decisão)
```
2.1 Coleta de dados
Responsável por buscar preços históricos e em tempo real, normalizar os dados (candles OHLCV) e persistir/cachear localmente para evitar bater na API externa repetidamente.
2.2 Indicadores técnicos
Transforma preço bruto em variáveis analisáveis: médias móveis, RSI, MACD, volatilidade, z-score de desvio da média.
2.3 Motor de regras (modelo quantitativo próprio)
Onde a lógica proprietária mora — combinação de indicadores em regras de decisão (ex: cruzamento de médias + filtro de RSI). Código Python puro, testável e versionado.
2.4 Backtesting engine
Roda as regras contra dados históricos, mede performance (taxa de acerto, Sharpe ratio, drawdown máximo) e valida significância estatística — incluindo walk-forward validation para evitar overfitting.
2.5 API
Expõe os dados calculados (preços, indicadores, sinais, resultados de backtest) via endpoints REST para o frontend consumir.
2.6 Frontend
Dashboard interativo com gráficos de preço, indicadores sobrepostos, sinais marcados no gráfico e relatório de backtest.
---
3. Tecnologias por camada
Camada	Tecnologia	Motivo
Coleta de dados	Python	Ecossistema maduro para dados financeiros
Indicadores e modelo	Python	Facilidade com bibliotecas de análise numérica
Backtesting	Python	Integração direta com o resto do backend
API	FastAPI	Leve, tipado, rápido de aprender vindo de JS, gera documentação automática (Swagger)
Frontend	React	Ecossistema mais forte em bibliotecas de gráficos financeiros
Gráficos	lightweight-charts (TradingView)	Biblioteca gratuita e feita especificamente para candlestick/indicadores
Persistência local	SQLite (v1) → PostgreSQL (v2)	SQLite não exige servidor, ótimo para prototipagem; migração natural depois
---
4. Bibliotecas
4.1 Implementado — v1 (verificado no código e no `backend/requirements.txt`)
Decisão consciente: indicadores (`backend/indicators/core.py`) e backtest
(`backend/backtest/engine.py`) são **Python puro** — mais fáceis de
compreender, auditar e testar que uma dependência pesada. Nada abaixo é
instalado além do listado; `pandas`/`numpy`/`ta`/`scipy`/`statsmodels`/
`vectorbt`/`backtrader` **não** são importados em nenhum módulo do backend.
Backend (Python)
Biblioteca	Função
`ccxt`	Conexão unificada com exchanges (Binance, Coinbase, etc.) para dados históricos e em tempo real
`fastapi`	Framework da API
`uvicorn`	Servidor ASGI para rodar a API
`pydantic`	Validação de dados de entrada/saída da API (já vem com FastAPI)
`sqlalchemy`	ORM para persistência (SQLite/PostgreSQL)
`cachetools`	Cache in-memory com TTL por horizonte (camada quente; SQLite é a camada persistente)
`httpx`	Fallback CoinGecko (`CoinGeckoProvider`) quando a Binance falha
`python-dotenv`	Gerenciamento de variáveis de ambiente (chaves de API)
Frontend (React)
Biblioteca	Função
`react`	Base do frontend
`axios` ou `fetch` nativo	Consumo da API
`lightweight-charts`	Gráficos de candlestick e indicadores
`react-query` (`@tanstack/react-query`)	Cache e sincronização de dados da API
`tailwindcss`	Estilização rápida e consistente
4.2 Planejado — NÃO instalado (requisitos comentados no `requirements.txt`)
Só descomentar/instalar ao adotar de fato, atualizando o §4.1 junto.
Biblioteca	Uso previsto	Condição de adoção
`pandas` / `numpy`	Manipulação de séries temporais e cálculo numérico vetorizado	Quando o volume de candles justificar sair das listas Python (hoje suficiente)
`ta` ou `pandas-ta`	Indicadores técnicos prontos (RSI, MACD, médias)	Se decidir trocar os indicadores próprios (`indicators/core.py`) por implementação de prateleira
`scipy`	Testes estatísticos de significância	Na fase de validação estatística formal (hoje o backtest é exploratório)
`statsmodels`	Análise de séries temporais (estacionariedade, autocorrelação)	Idem acima
`vectorbt` ou `backtrader`	Motor de backtesting alternativo	Se decidir trocar o engine próprio (`backtest/engine.py`) por framework pronto
---
5. APIs externas necessárias
API	Uso	Observação
Binance API (via `ccxt`)	Dados históricos e em tempo real de preço (OHLCV)	Gratuita para dados públicos, sem necessidade de conta para leitura
CoinGecko API	Backup de preços e dados de mercado gerais	Já usada no CryptoTracker; útil como fallback
Não há necessidade de API paga na v1. Chaves de API só serão necessárias futuramente se o projeto evoluir para execução de ordens.
---
6. Estrutura de pastas sugerida
```
orus-quant/
├── backend/
│   ├── data/          # coleta e cache de dados (ccxt)
│   ├── indicators/    # cálculo de indicadores técnicos
│   ├── strategy/       # motor de regras (modelo proprietário)
│   ├── backtest/       # engine de backtesting e métricas
│   ├── api/             # endpoints FastAPI
│   ├── models/          # modelos SQLAlchemy
│   └── main.py
└── frontend/
    └── src/
        ├── components/  # gráficos, cards, tabelas
        ├── pages/        # dashboard, backtest, configurações
        └── services/     # chamadas à API
```
---
7. Roadmap de implementação
Coleta de dados históricos via `ccxt` + persistência em SQLite
Cálculo de indicadores básicos (médias móveis, RSI)
Primeira regra de decisão simples (cruzamento de médias)
Backtesting da regra com métricas básicas (taxa de acerto, retorno acumulado)
API FastAPI expondo dados e resultados
Dashboard React consumindo a API
Iteração do modelo com mais indicadores e validação estatística (walk-forward)