import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "/api",
  timeout: 15000,
});

export async function fetchSignals() {
  const { data } = await api.get("/signals");
  return data;
}

export async function fetchSignalsBySymbol(symbol) {
  const { data } = await api.get(`/signals/${symbol}`);
  return data;
}

export async function fetchAssets() {
  const { data } = await api.get("/assets");
  return data;
}

export async function fetchPrice(symbol) {
  const { data } = await api.get(`/assets/${symbol}/price`);
  return data;
}

export async function fetchOhlc(symbol, interval = "1d", limit = 365) {
  const { data } = await api.get(`/assets/${symbol}/ohlc`, {
    params: { interval, limit },
  });
  return data;
}

// Backtest (endpoints ainda não implementados no backend —
// a página exibe estado "em breve" até lá; spec.md §3).
export async function runBacktest(payload) {
  const { data } = await api.post("/backtest/run", payload);
  return data;
}

export async function fetchBacktest(id) {
  const { data } = await api.get(`/backtest/${id}`);
  return data;
}
