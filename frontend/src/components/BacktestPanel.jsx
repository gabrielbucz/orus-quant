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

  const run = () => mutation.mutate({ symbol, horizon, limit: 365, n_windows: 3 });

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
        Backtest — {symbol}
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
            <Metric label="Taxa de acerto" value={pct(result.win_rate)} />
            <Metric label="Retorno acumulado" value={pct(result.cumulative_return)} />
            <Metric label="Sharpe" value={result.sharpe_ratio.toFixed(2)} />
            <Metric label="Drawdown máx." value={pct(result.max_drawdown)} />
          </div>
          <p style={{ fontSize: "11px", color: "#8A8A8A" }}>
            {result.strategy_name} · {result.period_start} → {result.period_end} · walk-forward em
            3 janelas · long-only, sem custos (v1).
          </p>
        </div>
      )}
      {!result && !mutation.isPending && (
        <p style={{ fontSize: "12px", color: "#8A8A8A" }}>
          Roda a regra de score ({symbols?.join(", ") ?? symbol}) sobre o histórico e mede taxa de
          acerto, retorno, Sharpe e drawdown com validação walk-forward.
        </p>
      )}
    </div>
  );
}
