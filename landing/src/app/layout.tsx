import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Open-Dispatch — One API to dispatch your content anywhere",
  description:
    "Self-hostable, API-first content distribution. Post to Twitter/X, Instagram, Bluesky, LinkedIn, Telegram, Threads, and YouTube Shorts with a single HTTP call. MIT licensed.",
  openGraph: {
    title: "Open-Dispatch",
    description: "One API to dispatch your content anywhere.",
    url: "https://open-dispatch.dev",
    siteName: "Open-Dispatch",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Open-Dispatch",
    description: "One API to dispatch your content anywhere.",
  },
  metadataBase: new URL("https://open-dispatch.dev"),
};

export const viewport: Viewport = {
  themeColor: "#080c0f",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={inter.variable}>
      <body>{children}</body>
    </html>
  );
}
