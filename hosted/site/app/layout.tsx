import type { Metadata } from "next";
import { Caveat, Inter_Tight, JetBrains_Mono, Newsreader } from "next/font/google";
import "./globals.css";

const newsreader = Newsreader({
  subsets: ["latin"],
  variable: "--font-newsreader",
  weight: ["300", "400", "500", "600"],
  style: ["normal"],
  display: "swap",
});
const interTight = Inter_Tight({
  subsets: ["latin"],
  variable: "--font-inter-tight",
  weight: ["400", "500", "600"],
  display: "swap",
});
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains",
  weight: ["400", "500"],
  display: "swap",
});
const caveat = Caveat({
  subsets: ["latin"],
  variable: "--font-caveat",
  weight: ["500", "600"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "Wenche, årsoppgjøret for ditt holdingselskap",
  description:
    "Wenche sender inn årsregnskap, skattemelding og aksjonærregisteroppgave for små, passive holdingselskaper rett til Altinn. Foreløpig kun for spesielt inviterte.",
  authors: [{ name: "Ole Fredrik Lie" }],
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="nb"
      className={`${newsreader.variable} ${interTight.variable} ${jetbrainsMono.variable} ${caveat.variable}`}
    >
      <body>{children}</body>
    </html>
  );
}
