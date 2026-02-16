import type { Metadata } from "next";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";

const displaySans = Space_Grotesk({
  variable: "--font-display-sans",
  subsets: ["latin"],
});

const uiMono = IBM_Plex_Mono({
  variable: "--font-ui-mono",
  weight: ["400", "500"],
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "DrugShield AI",
  description: "Medication risk intelligence for patients and caregivers",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${displaySans.variable} ${uiMono.variable} antialiased`}>
        {children}
      </body>
    </html>
  );
}
