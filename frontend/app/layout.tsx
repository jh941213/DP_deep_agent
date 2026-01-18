import type { Metadata } from "next";
import { IBM_Plex_Mono, IBM_Plex_Sans } from "next/font/google";
import localFont from "next/font/local";
import "./globals.css";

const plexSans = IBM_Plex_Sans({
  variable: "--font-plex-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
});

const plexMono = IBM_Plex_Mono({
  variable: "--font-plex-mono",
  subsets: ["latin"],
  weight: ["400", "500", "600"],
});

const spotlight = localFont({
  src: "./fonts/Y_Spotlight.ttf",
  variable: "--font-spotlight",
});

const yPairing = localFont({
  src: [
    {
      path: "../public/fonts/YPairingFont-Regular.ttf",
      weight: "400",
      style: "normal",
    },
    {
      path: "../public/fonts/YPairingFont-Bold.ttf",
      weight: "700",
      style: "normal",
    },
  ],
  variable: "--font-ypairing",
});

export const metadata: Metadata = {
  title: "Direct Purchase Agent",
  description: "Multi-store direct purchase assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${plexSans.variable} ${plexMono.variable} ${spotlight.variable} ${yPairing.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}

