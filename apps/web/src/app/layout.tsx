import type { Metadata } from "next";
import localFont from "next/font/local";
import { AppShell } from "@/components/AppShell";
import "./globals.css";

const rubik = localFont({
  src: "./fonts/rubik-latin-wght-normal.woff2",
  variable: "--font-rubik",
  weight: "400 800",
  display: "swap",
});

const plexMono = localFont({
  src: [
    { path: "./fonts/ibm-plex-mono-latin-400-normal.woff2", weight: "400" },
    { path: "./fonts/ibm-plex-mono-latin-500-normal.woff2", weight: "500" },
    { path: "./fonts/ibm-plex-mono-latin-600-normal.woff2", weight: "600" },
  ],
  variable: "--font-plex-mono",
  display: "swap",
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
