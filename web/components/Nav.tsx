"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

// Short labels on phones keep the nav on one line; the full label shows from the sm breakpoint.
// The two eval sections have Framework and Results tabs (the nav opens Results); Models and Online evaluation are one page each.
const LINKS = [
  { href: "/", section: "/", label: "Demo", short: "Demo" },
  { href: "/before-after/results", section: "/before-after", label: "Before vs After", short: "B vs A" },
  { href: "/skill-edits/results", section: "/skill-edits", label: "Skill edits", short: "Edits" },
  { href: "/models", section: "/models", label: "Models", short: "Models" },
  { href: "/online-evaluation", section: "/online-evaluation", label: "Online evaluation", short: "Online" },
];

export function Nav() {
  // The static site ends paths with a slash (trailingSlash), so compare without it.
  const pathname = usePathname().replace(/(.)\/+$/, "$1");
  return (
    <nav aria-label="Main" className="flex max-w-full gap-1 overflow-x-auto rounded-full bg-mist p-1">
      {LINKS.map((link) => {
        const active = link.section === "/" ? pathname === "/" : pathname.startsWith(link.section);
        // "page" only on the exact page; inside a section the link marks where the reader is.
        const current = pathname === link.href ? "page" : active ? "location" : undefined;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={current}
            className={`whitespace-nowrap rounded-full px-2.5 py-1.5 text-sm font-medium transition-colors sm:px-3.5 ${
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
