# PRD — Orus Quant

## 1. Visão geral

Orus Quant é um sistema de análise quantitativa para o mercado de criptomoedas, focado em **análise e decisão assistida** — não em execução automática de ordens. O sistema coleta dados de preço, calcula indicadores técnicos, aplica um modelo de regras próprio, valida esse modelo via backtesting e apresenta os resultados em um dashboard web.

## 2. Problema

Analisar cripto manualmente exige acompanhar múltiplos indicadores, em múltiplos horizontes de tempo (curtíssimo, médio, longo prazo), para múltiplos ativos ao mesmo tempo. Isso é demorado, propenso a viés emocional e difícil de validar estatisticamente sem ferramentas.

## 3. Objetivo do produto

Dar suporte à decisão de mercado, consolidando indicadores técnicos em um **sinal único por ativo e por horizonte de investimento**, validado por backtesting, e apresentado de forma visual e rápida de interpretar.

## 4. Público-alvo

- **v1**: uso pessoal do próprio desenvolvedor, para apoiar decisões próprias de mercado.
- **Visão futura**: estruturado desde já para eventual lançamento a outros usuários (arquitetura, autenticação e API pensadas para múltiplos usuários no futuro, ainda que não implementadas na v1).

## 5. Escopo da v1

### Incluído
- Coleta de dados históricos e recentes de preço (OHLCV) via Binance (`ccxt`), com CoinGecko como backup — fonte: `arquitetura.md §5`.
- Cálculo de indicadores técnicos (médias móveis, RSI, MACD, volatilidade).
- Motor de regras próprio, combinando indicadores em um score de sinal.
- Três horizontes de análise: **day trade**, **swing trade** e **hold**, cada um com indicadores e frequência de atualização próprios.
- Backtesting das regras contra dados históricos, com métricas de performance.
- Dashboard web (React) com:
  - Tabela de sinais por ativo x horizonte, com escala de cores (vermelho → verde) indicando força do sinal.
  - Gráfico de preço com indicadores sobrepostos.
  - Relatório de resultados de backtest.
- Indicação de "idade do dado" (quando foi atualizado pela última vez) em cada sinal.

### Fora de escopo (v1)
- Execução automática de ordens (trading automatizado).
- Múltiplos usuários / autenticação (arquitetura permite, mas não é implementado agora).
- Dados via WebSocket em tempo real (fica para uma v2; v1 usa REST via `ccxt` + persistência SQLite).
- Alertas via notificação push/e-mail.

## 6. Requisitos funcionais

| ID | Requisito |
|---|---|
| RF01 | O sistema deve coletar candles OHLCV de ativos configurados via Binance (`ccxt`), com fallback para CoinGecko e SQLite local. |
| RF02 | O sistema deve calcular indicadores técnicos (médias móveis, RSI, MACD, volatilidade) a partir dos dados coletados. |
| RF03 | O sistema deve gerar um score de 0 a 100 por ativo, por horizonte (day trade, swing trade, hold). |
| RF04 | O sistema deve mapear o score para uma escala visual de 5 cores (vermelho, laranja, amarelo, verde-claro, verde). |
| RF05 | O sistema deve exibir os sinais em formato de tabela (ativo x horizonte) no dashboard. |
| RF06 | O sistema deve rodar backtesting das regras de decisão sobre dados históricos. |
| RF07 | O sistema deve exibir métricas de backtest (taxa de acerto, retorno acumulado, drawdown máximo, Sharpe ratio). |
| RF08 | O sistema deve atualizar os sinais em frequências diferentes por horizonte (day trade mais frequente, hold menos frequente). |
| RF09 | O sistema deve exibir a idade do dado (última atualização) junto a cada sinal. |
| RF10 | O sistema deve persistir/cachear localmente (SQLite + TTL por horizonte) os dados coletados para reduzir chamadas à API externa. |

## 7. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF01 | O sistema deve respeitar os limites de rate limit da exchange (Binance via `ccxt` com `enableRateLimit`) e do fallback CoinGecko (plano demo/free). |
| RNF02 | A camada de coleta de dados deve ser trocável (ex: migrar de Binance/`ccxt` para outra fonte) sem alterar o motor de regras, backtesting ou frontend. |
| RNF03 | O tempo de resposta da API interna (FastAPI) para consultas já cacheadas deve ser inferior a 500ms. |
| RNF04 | A interface deve seguir uma identidade visual escura (tema "terminal financeiro"), com verde para ganho/força e vermelho reservado a alertas e sinais fracos. |
| RNF05 | O código do motor de regras deve ser testável isoladamente (sem dependência direta de chamadas de rede). |

## 8. Métricas de sucesso (v1)

- O modelo de decisão apresenta taxa de acerto e Sharpe ratio superiores a uma estratégia de referência simples (ex: buy and hold) no backtest.
- O sistema opera dentro do rate limit da exchange sem falhas de coleta (serve SQLite stale + fallback em caso de falha).
- O dashboard permite, em poucos segundos, identificar quais ativos têm sinal favorável em qual horizonte.

## 9. Riscos conhecidos

- O fallback CoinGecko free/demo tem granularidade e rate limit limitados — se a Binance falhar, o horizonte "day trade" pode degradar temporariamente.
- Overfitting do modelo de regras aos dados históricos, caso o backtesting não inclua validação walk-forward.