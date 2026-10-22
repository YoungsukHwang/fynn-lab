"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Short labels on phones keep the nav on one line; the full label shows from the sm breakpoint.
const LINKS = [
  { href: "/", label: "Demo", short: "Demo" },
  { href: "/framework", label: "Monitoring framework", short: "Framework" },
  { href: "/results", label: "Monitoring results", short: "Results" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex gap-1 rounded-full bg-mist p-1">
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`whitespace-nowrap rounded-full px-3 py-1.5 text-sm font-medium transition-colors sm:px-3.5 ${
              active ? "bg-ink text-white" : "text-slate hover:bg-white hover:text-ink"
            }`}
          >
            <span className="sm:hidden">{link.short}</span>
            <span className="hidden sm:inline">{link.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
