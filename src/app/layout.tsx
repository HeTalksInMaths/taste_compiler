import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'EvalWeaver — AI Quality Scorer Marketplace',
  description:
    'Discover, validate, and monetize AI quality scorers for subjective text improvement goals.',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen font-sans">
        <Nav />
        <main>{children}</main>
      </body>
    </html>
  );
}

function Nav() {
  return (
    <nav className="sticky top-0 z-50 border-b border-white/[0.06] bg-black/80 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <a href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-purple-500">
            <span className="text-sm font-bold text-white">E</span>
          </div>
          <span className="text-lg font-semibold tracking-tight">EvalWeaver</span>
        </a>
        <div className="flex items-center gap-8">
          <a href="/marketplace" className="text-sm text-white/60 transition hover:text-white">
            Marketplace
          </a>
          <a href="/create" className="text-sm text-purple-400/80 transition hover:text-purple-300">
            Create Scorer ✨
          </a>
          <a href="/methodology" className="text-sm text-white/60 transition hover:text-white">
            Methodology
          </a>
          <a href="/live-sim" className="text-sm text-amber-400/80 transition hover:text-amber-300">
            Live Sim ⚡
          </a>
          <a href="/dashboard" className="text-sm text-white/60 transition hover:text-white">
            Dashboard
          </a>
        </div>
      </div>
    </nav>
  );
}
