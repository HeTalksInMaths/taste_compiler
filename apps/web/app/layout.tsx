import type { Metadata } from "next";
import Link from "next/link";
import { ViewModeProvider } from "@/providers/ViewModeProvider";
import { ChatWidget } from "@/components/chat-widget";
import "./globals.css";

export const metadata: Metadata = {
  title: "Taste Compiler",
  description: "Turn subjective taste into executable scorers",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <Nav />
        <ViewModeProvider>{children}</ViewModeProvider>
        <ChatWidget />
      </body>
    </html>
  );
}

function Nav() {
  return (
    <nav
      className="sticky top-0 z-50 backdrop-blur-xl font-sans"
      style={{
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        backgroundColor: "rgba(0,0,0,0.85)",
      }}
    >
      <div
        style={{
          maxWidth: "1280px",
          margin: "0 auto",
          display: "flex",
          height: "56px",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 24px",
        }}
      >
        <Link
          href="/"
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            textDecoration: "none",
          }}
        >
          <div
            style={{
              height: "28px",
              width: "28px",
              borderRadius: "6px",
              backgroundColor: "#4c6ef5",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "13px",
              fontWeight: 700,
              color: "white",
            }}
          >
            T
          </div>
          <span className="text-sm font-semibold tracking-tight text-white">
            Taste Compiler
          </span>
        </Link>

        <div className="flex items-center gap-6">
          <Link
            href="/create"
            className="text-sm font-sans transition"
            style={{ color: "rgb(145,167,255)" }}
          >
            Create Scorer
          </Link>
          <Link
            href="/stages"
            className="text-sm font-sans transition"
            style={{ color: "rgba(255,255,255,0.55)" }}
          >
            Live Pipeline
          </Link>
          <Link
            href="/market-dynamics"
            className="text-sm font-sans transition"
            style={{ color: "rgba(255,255,255,0.55)" }}
          >
            Market
          </Link>
        </div>
      </div>
    </nav>
  );
}
