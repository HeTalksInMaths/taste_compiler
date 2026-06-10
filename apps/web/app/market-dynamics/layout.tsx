import Link from "next/link";

export default function MarketDynamicsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="font-sans antialiased" style={{ minHeight: "100vh", backgroundColor: "#050505", color: "rgba(255,255,255,0.87)" }}>
      {/* Sub-nav */}
      <div style={{ borderBottom: "1px solid rgba(255,255,255,0.06)", backgroundColor: "rgba(0,0,0,0.5)" }}>
        <div style={{ maxWidth: "1280px", margin: "0 auto", display: "flex", height: "40px", alignItems: "center", gap: "24px", padding: "0 24px" }}>
          <span className="text-xs font-medium" style={{ color: "rgba(255,255,255,0.25)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
            Market Dynamics
          </span>
          <Link href="/market-dynamics/marketplace" className="text-xs transition" style={{ color: "rgba(255,255,255,0.45)" }}>
            Marketplace
          </Link>
          <Link href="/market-dynamics/simulations" className="text-xs transition" style={{ color: "rgba(255,255,255,0.45)" }}>
            Simulations
          </Link>
          <Link href="/market-dynamics/methodology" className="text-xs transition" style={{ color: "rgba(255,255,255,0.45)" }}>
            Methodology
          </Link>
          <Link href="/market-dynamics/dashboard" className="text-xs transition" style={{ color: "rgba(255,255,255,0.45)" }}>
            Dashboard
          </Link>
          <Link href="/market-dynamics/live-sim" className="text-xs transition ml-auto" style={{ color: "rgba(251,191,36,0.7)" }}>
            Market Test
          </Link>
        </div>
      </div>
      {children}
    </div>
  );
}
