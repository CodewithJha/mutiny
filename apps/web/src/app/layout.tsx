import type { Metadata } from "next";
import { Rubik, IBM_Plex_Mono } from "next/font/google";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

const rubik = Rubik({
  variable: "--font-rubik",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

export const metadata: Metadata = {
  title: "Mutiny — Behavioral fuzz testing for AI agents",
  description:
    "Find policy violations with deterministic tool-call verification. Policy → evolution → proof → regression.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body
        className={`${rubik.variable} ${plexMono.variable} min-h-screen bg-bg text-text antialiased`}
      >
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
