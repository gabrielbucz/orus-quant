import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { runBacktest } from "../services/api.js";

const HORIZONS = [
  { key: "day_trade", title: "Day trade" },
  { key: "swing_trade", title: "Swing trade" },
  { key: "hold", title: "Hold" },
];

function Metric({ label, value }) {
  return (
    <div style={{ flex: "1 1 120px" }}>
      <div style={{ fontSize: "11px", color: "#8A8A8A" }}>{label}</div>
      <div style={{ fontSize: "16px", fontWeight: 600, color: "#F2F2F2" }}>{value}</div>
    </div>
  );
}

const pct = (v) => `${(v * 100).toFixed(1)}%`;

export default function BacktestPanel({ symbol, symbols }) {
  const [horizon, setHorizon] = useState("swing_trade");
  const mutation = useMutation({ mutationFn: runBacktest });
  const result = mutation.data?.result;

  const run = () =>
    mutation.mutate({ symbol, horizon, limit: 365, n_windows: 3, test_windows: 1, cost_bps: 10 });

  const perWindow = result?.per_window_returns ?? [];
  const nWindows = perWindow.length || 3;

  return (
    <div
      style={{
        marginTop: "1.5rem",
        background: "#0A0A0A",
        padding: "1.5rem",
        borderRadius: "12px",
        border: "1px solid #222",
      }}
    >
      <h2 style={{ fontSize: "14px", fontWeight: 500, marginBottom: "1rem", color: "#F2F2F2" }}>
        Backtest exploratório — {symbol}
      </h2>

      <div style={{ display: "flex", gap: "8px", marginBottom: "1rem", flexWrap: "wrap" }}>
        {HORIZONS.map((h) => (
          <button
            key={h.key}
            onClick={() => setHorizon(h.key)}
            style={{
              padding: "6px 14px",
              borderRadius: "6px",
              border: "1px solid #222",
              background: h.key === horizon ? "#1c1c1c" : "#0A0A0A",
              color: h.key === horizon ? "#F2F2F2" : "#8A8A8A",
              cursor: "pointer",
              fontSize: "13px",
            }}
          >
            {h.title}
          </button>
        ))}
        <button
          onClick={run}
          disabled={mutation.isPending}
          style={{
            padding: "6px 18px",
            borderRadius: "6px",
            border: "1px solid #3B9E44",
            background: "#3B9E44",
            color: "#0D2E10",
            cursor: mutation.isPending ? "wait" : "pointer",
            fontSize: "13px",
            fontWeight: 600,
          }}
        >
          {mutation.isPending ? "Rodando…" : "Rodar backtest"}
        </button>
      </div>

      {mutation.isError && (
        <p style={{ color: "#E24B4A", fontSize: "12px" }}>
          Falha ao rodar backtest. Verifique se o backend está rodando.
        </p>
      )}
      {result && (
        <div>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
            <Metric
              label="Retorno OOS (avaliação)"
              value={pct(result.out_of_sample_return ?? result.cumulative_return)}
            />
            <Metric label="Retorno IS (desenvolvimento)" value={pct(result.in_sample_return ?? 0)} />
            <Metric
              label="Sharpe OOS"
              value={(result.out_of_sample_sharpe ?? 0).toFixed(2)}
            />
            <Metric label="Drawdown máx. OOS" value={pct(result.out_of_sample_max_drawdown ?? 0)} />
          </div>
          <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap", marginBottom: "0.75rem" }}>
            <Metric label="Retorno acumulado (full)" value={pct(result.cumulative_return)} />
            <Metric
              label={`Janelas positivas`}
              value={`${result.windows_positive ?? 0}/${perWindow.length || nWindows}`}
            />
            <Metric label="Custo por lado" value={`${result.cost_bps ?? 10} bps`} />
            <Metric label="Trades OOS" value={`${result.out_of_sample_trades ?? 0}`} />
          </div>
          {perWindow.length > 0 && (
            <p style={{ fontSize: "11px", color: "#8A8A8A" }}>
              Por janela (líquido): {perWindow.map((r) => pct(r)).join(" · ")}
              {result.oos_period_start && result.oos_period_end
                ? ` · OOS: ${result.oos_period_start} → ${result.oos_period_end}`
                : ""}
            </p>
          )}
          <p style={{ fontSize: "11px", color: "#8A8A8A" }}>
            {result.strategy_name} · {result.period_start} → {result.period_end} · walk-forward em{" "}
            {nWindows} janelas ({nWindows - (result.test_windows ?? 1)} IS + {result.test_windows ?? 1}{" "}
            OOS) · long-only, líquido de custos.
          </p>
          <p style={{ fontSize: "11px", color: "#C9A227", marginTop: "0.5rem" }}>
            Backtest exploratório, não prova estatística: ajuste parâmetros só no período IS e
            julgue pelo OOS reservado. Não garante lucro futuro — cheque estabilidade entre janelas
            e regimes de mercado.
          </p>
        </div>
      )}
      {!result && !mutation.isPending && (
        <p style={{ fontSize: "12px", color: "#8A8A8A" }}>
          Roda a regra de score ({symbols?.join(", ") ?? symbol}) sobre o histórico com custos
          estimados, separa desenvolvimento (IS) de avaliação reservada (OOS) e expõe estabilidade
          por janela. Não interpreta como garantia de lucro futuro.
        </p>
      )}
    </div>
  );
}
