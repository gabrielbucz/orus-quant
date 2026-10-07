import { IconArrowRight, IconCoin, IconCurrencyBitcoin, IconCurrencyEthereum } from "@tabler/icons-react";

// Cores da escala de sinal — mesmas do mock orus_quant_signal_heatmap_table.html
const COLORS = {
  red: { bg: "#E24B4A", fg: "#4A1010" },
  orange: { bg: "#EF9F27", fg: "#4A2E0A" },
  yellow: { bg: "#F5D93B", fg: "#4A3F0A" },
  light_green: { bg: "#97C459", fg: "#1D330E" },
  green: { bg: "#3B9E44", fg: "#0D2E10" },
};

// Ícones por ativo — mesmos do mock (ti-currency-bitcoin, ti-currency-ethereum, ti-coin)
const ASSET_ICONS = {
  BTC: { Icon: IconCurrencyBitcoin, color: "#EF9F27" },
  ETH: { Icon: IconCurrencyEthereum, color: "#8A8A8A" },
  SOL: { Icon: IconCoin, color: "#7F77DD" },
};

const HORIZONS = [
  { key: "day_trade", title: "Day trade" },
  { key: "swing_trade", title: "Swing trade" },
  { key: "hold", title: "Hold" },
];

function formatAge(seconds) {
  if (seconds < 60) return `há ${seconds}s`;
  if (seconds < 3600) return `há ${Math.floor(seconds / 60)}min`;
  return `há ${Math.floor(seconds / 3600)}h`;
}

function SignalCell({ signal }) {
  if (!signal) return <td style={{ padding: "8px 6px", textAlign: "center", color: "#8A8A8A" }}>—</td>;
  const c = COLORS[signal.color] ?? COLORS.yellow;
  return (
    <td style={{ padding: "8px 6px", textAlign: "center" }}>
      <div
        title={`Score ${signal.score} · atualizado ${signal.last_updated}`}
        style={{
          margin: "0 auto",
          width: "60px",
          height: "26px",
          borderRadius: "6px",
          background: c.bg,
          color: c.fg,
          fontSize: "12px",
          fontWeight: 500,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {signal.label}
      </div>
      <div style={{ fontSize: "10px", color: "#8A8A8A", marginTop: "2px" }}>
        {signal.score} · {formatAge(signal.data_age_seconds)}
      </div>
    </td>
  );
}

export default function SignalTable({ signals }) {
  const bySymbol = {};
  for (const s of signals ?? []) {
    (bySymbol[s.symbol] ??= {})[s.horizon] = s;
  }
  const symbols = Object.keys(bySymbol).sort();

  return (
    <div style={{ background: "#0A0A0A", padding: "1.5rem", borderRadius: "12px" }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "14px",
          marginBottom: "1.25rem",
          fontSize: "11px",
          color: "#8A8A8A",
        }}
      >
        <span>Escala:</span>
        <div style={{ display: "flex", alignItems: "center", gap: "2px" }}>
          {Object.values(COLORS).map((c) => (
            <div key={c.bg} style={{ width: "20px", height: "10px", background: c.bg }} />
          ))}
        </div>
        <span>fraco</span>
        <IconArrowRight size={12} aria-hidden />
        <span>forte</span>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse", tableLayout: "fixed" }}>
        <thead>
          <tr>
            <th style={{ textAlign: "left", fontSize: "12px", fontWeight: 500, color: "#8A8A8A", padding: "8px 6px", width: "22%" }}>
              Ativo
            </th>
            {HORIZONS.map((h) => (
              <th key={h.key} style={{ textAlign: "center", fontSize: "12px", fontWeight: 500, color: "#8A8A8A", padding: "8px 6px" }}>
                {h.title}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((symbol) => {
            const { Icon, color } = ASSET_ICONS[symbol] ?? { Icon: IconCoin, color: "#8A8A8A" };
            return (
              <tr key={symbol} style={{ borderTop: "0.5px solid #222" }}>
                <td style={{ padding: "10px 6px", fontSize: "13px", color: "#F2F2F2", fontWeight: 500 }}>
                  <Icon size={14} color={color} style={{ marginRight: "6px", verticalAlign: "-2px" }} aria-hidden />
                  {symbol}
                </td>
                {HORIZONS.map((h) => (
                  <SignalCell key={h.key} signal={bySymbol[symbol][h.key]} />
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
