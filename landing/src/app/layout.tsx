import type { Metadata, Viewport } from "next";
import { Archivo, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const archivo = Archivo({
  subsets: ["latin"],
  axes: ["wdth"],
  display: "swap",
  variable: "--font-archivo",
});

const mono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jbmono",
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
  themeColor: "#0f1418",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${archivo.variable} ${mono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
