import type { Metadata } from "next";
import { DM_Mono, DM_Sans } from "next/font/google";
import Link from "next/link";

import { Nav } from "@/components/Nav";

import "./globals.css";

const dmSans = DM_Sans({
  variable: "--font-dm-sans",
  subsets: ["latin"],
});

const dmMono = DM_Mono({
  variable: "--font-dm-mono",
  subsets: ["latin"],
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  // Distinct titles per page also let Next's route announcer tell screen readers about navigation.
  title: { default: "Fynn Lab", template: "%s | Fynn Lab" },
  description:
    "Before/after re-implementation of a skill-based credit coach. Regression evals for each skill change are in progress.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${dmSans.variable} ${dmMono.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col bg-canvas font-sans text-ink">
        <header className="border-b border-line bg-white">
          <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
            <Link href="/" className="flex items-center gap-2.5">
              <span
                aria-hidden="true"
                className="grid h-8 w-8 place-items-center rounded-lg bg-ink text-sm font-bold text-lime"
              >
                F
              </span>
              <span className="flex flex-col leading-tight">
                <span className="text-base font-semibold tracking-tight">Fynn Lab</span>
                <span className="hidden text-xs text-slate sm:block">A study of skill-based routing</span>
              </span>
            </Link>
            <Nav />
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:py-8">{children}</main>
        <footer className="border-t border-line bg-white">
          <p className="mx-auto max-w-7xl px-4 py-5 text-xs leading-5 text-slate">
            An independent study of the architecture described in Kikoff&apos;s{" "}
            <a className="font-medium text-ink underline underline-offset-2" href="https://about.kikoff.com/build/fynn-at-100-scale">
              &ldquo;Fynn at 100% scale&rdquo;
            </a>{" "}
            post. Not affiliated with Kikoff. The products, personas and credit data are fictional.
          </p>
        </footer>
      </body>
    </html>
  );
}
