"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// The Framework / Results tabs inside a section. Links, so each tab has its own URL.
export function SectionTabs({ base, label }: { base: string; label: string }) {
  // The static site ends paths with a slash (trailingSlash), so compare without it.
  const pathname = usePathname().replace(/(.)\/+$/, "$1");
  const tabs = [
    { href: `${base}/framework`, text: "Framework" },
    { href: `${base}/results`, text: "Results" },
  ];
  return (
    <nav aria-label={`${label} tabs`} className="flex gap-1 border-b border-line">
      {tabs.map((tab) => {
        // The section's own URL shows the Results tab.
        const active = pathname === tab.href || (pathname === base && tab.text === "Results");
        return (
          <Link
            key={tab.href}
            href={tab.href}
            aria-current={active ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-sm font-semibold transition-colors ${
              active ? "border-ink text-ink" : "border-transparent text-slate hover:border-line hover:text-ink"
            }`}
          >
            {tab.text}
          </Link>
        );
      })}
    </nav>
  );
}
