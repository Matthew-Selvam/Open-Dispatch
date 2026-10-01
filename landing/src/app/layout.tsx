import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
});

const DESCRIPTION =
  "Self-hostable content distribution over plain HTTP. Post to X, Bluesky, Instagram, LinkedIn, Telegram, Threads, YouTube Shorts, TikTok, Discord, and Facebook with a single request. MIT licensed.";

export const metadata: Metadata = {
  title: "Open-Dispatch: one HTTP call, ten platforms",
  description: DESCRIPTION,
  openGraph: {
    title: "Open-Dispatch",
    description: DESCRIPTION,
    url: "https://open-dispatch-landing.vercel.app",
    siteName: "Open-Dispatch",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Open-Dispatch",
    description: DESCRIPTION,
  },
  metadataBase: new URL("https://open-dispatch-landing.vercel.app"),
};

export const viewport: Viewport = {
  themeColor: "#0f1318",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
