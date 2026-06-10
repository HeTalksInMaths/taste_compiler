import type { Metadata } from "next";
import { ViewModeProvider } from "@/providers/ViewModeProvider";
import { ChatWidget } from "@/components/chat-widget";
import "./globals.css";

export const metadata: Metadata = {
  title: "Taste Compiler",
  description: "Agents that learn what 'good' means",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ViewModeProvider>{children}</ViewModeProvider>
        <ChatWidget />
      </body>
    </html>
  );
}
