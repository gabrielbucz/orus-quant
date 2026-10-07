import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchAssets, fetchSignals } from "../services/api.js";
import SignalTable from "../components/SignalTable.jsx";
import PriceChart from "../components/PriceChart.jsx";
import BacktestPanel from "../components/BacktestPanel.jsx";

// Day trade tem o TTL mais curto (60–120s, spec §5) — base do refetch.
const REFETCH_MS = 60_000;

export default function Dashboard() {
  const [symbol, setSymbol] = useState("BTC");

  const signals = useQuery({
    queryKey: ["signals"],
    queryFn: fetchSignals,
    refetchInterval: REFETCH_MS,
  });
  const assets = useQuery({ queryKey: ["assets"], queryFn: fetchAssets });

  return (
    <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "2rem 1rem" }}>
      <header style={{ marginBottom: "1.5rem" }}>
        <h1 style={{ fontSize: "20px", fontWeight: 600 }}>Orus Quant</h1>
        <p style={{ fontSize: "12px", color: "#8A8A8A" }}>
          Sinais por ativo × horizonte ·{" "}
          {signals.dataUpdatedAt
            ? `atualizado às ${new Date(signals.dataUpdatedAt).toLocaleTimeString()}`
            : "carregando…"}
        </p>
      </header>

      {signals.isLoading && <p style={{ color: "#8A8A8A" }}>Carregando sinais…</p>}
      {signals.isError && (
        <p style={{ color: "#E24B4A" }}>
          Falha ao carregar sinais. Verifique se o backend está rodando.
        </p>
      )}
      {signals.data && <SignalTable signals={signals.data} />}

      <div style={{ marginTop: "1.5rem" }}>
        <div style={{ display: "flex", gap: "8px", marginBottom: "1rem" }}>
          {(assets.data ?? ["BTC"]).map((a) => (
            <button
              key={a}
              onClick={() => setSymbol(a)}
              style={{
                padding: "6px 14px",
                borderRadius: "6px",
                border: "1px solid #222",
                background: a === symbol ? "#1c1c1c" : "#0A0A0A",
                color: a === symbol ? "#F2F2F2" : "#8A8A8A",
                cursor: "pointer",
                fontSize: "13px",
              }}
            >
              {a}
            </button>
          ))}
        </div>
        <PriceChart symbol={symbol} />
      </div>

      <BacktestPanel symbol={symbol} symbols={assets.data} />
    </div>
  );
}
