import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { createChart } from "lightweight-charts";
import { fetchOhlc } from "../services/api.js";

export default function PriceChart({ symbol }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);

  const { data: candles, isLoading, isError } = useQuery({
    queryKey: ["ohlc", symbol],
    queryFn: () => fetchOhlc(symbol, "1d", 365),
  });

  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: { background: { color: "#0A0A0A" }, textColor: "#8A8A8A" },
      grid: { vertLines: { color: "#1a1a1a" }, horzLines: { color: "#1a1a1a" } },
      width: containerRef.current.clientWidth,
      height: 320,
    });
    const series = chart.addCandlestickSeries({
      upColor: "#3B9E44",
      downColor: "#E24B4A",
      wickUpColor: "#3B9E44",
      wickDownColor: "#E24B4A",
    });
    chartRef.current = chart;
    seriesRef.current = series;
    const onResize = () => chart.applyOptions({ width: containerRef.current.clientWidth });
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || !candles) return;
    // O gráfico exige tempos únicos e crescentes; o StubProvider do
    // backend pode repetir o timestamp — mantém só o último por data.
    const seen = new Set();
    const data = [];
    for (const c of candles) {
      const time = c.timestamp.slice(0, 10);
      if (seen.has(time)) continue;
      seen.add(time);
      data.push({ time, open: c.open, high: c.high, low: c.low, close: c.close });
    }
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().scrollToRealTime();
  }, [candles]);

  return (
    <div style={{ background: "#0A0A0A", padding: "1.5rem", borderRadius: "12px" }}>
      <h2 style={{ fontSize: "14px", fontWeight: 500, color: "#F2F2F2", marginBottom: "1rem" }}>
        Preço — {symbol}
      </h2>
      {isLoading && <p style={{ color: "#8A8A8A", fontSize: "12px" }}>Carregando candles…</p>}
      {isError && <p style={{ color: "#E24B4A", fontSize: "12px" }}>Falha ao carregar candles.</p>}
      <div ref={containerRef} />
    </div>
  );
}
