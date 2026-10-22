import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";

import { Nav } from "@/components/Nav";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  // Distinct titles per page also let Next's route announcer tell screen readers about navigation.
  title: { default: "Fynn Lab", template: "%s | Fynn Lab" },
  description:
    "Before/after re-implementation of a skill-based credit coach. Regression evals for each skill change are in progress.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-zinc-100 font-sans text-zinc-900">
        <header className="border-b border-zinc-200 bg-white">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="text-base font-semibold tracking-tight">
              Fynn Lab
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6">{children}</main>
        <footer className="border-t border-zinc-200 bg-white">
          <p className="mx-auto max-w-7xl px-4 py-4 text-xs text-zinc-500">
            An independent study of the architecture described in Kikoff&apos;s{" "}
            <a className="underline" href="https://about.kikoff.com/build/fynn-at-100-scale">
              &ldquo;Fynn at 100% scale&rdquo;
            </a>{" "}
            post. Not affiliated with Kikoff. The products, personas and credit data are fictional.
          </p>
        </footer>
      </body>
    </html>
  );
}
