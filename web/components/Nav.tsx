"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Demo" },
  { href: "/framework", label: "Monitoring framework" },
  { href: "/results", label: "Monitoring results" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main" className="flex flex-wrap gap-1">
      {LINKS.map((link) => {
        const active = pathname === link.href;
        return (
          <Link
            key={link.href}
            href={link.href}
            aria-current={active ? "page" : undefined}
            className={`rounded-md px-3 py-1.5 text-sm ${active ? "bg-zinc-900 text-white" : "text-zinc-700 hover:bg-zinc-100"}`}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
