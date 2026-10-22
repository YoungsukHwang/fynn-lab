// Small building blocks shared by the framework and results pages.

export function PageHero({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <section className="overflow-hidden rounded-2xl bg-ink px-5 py-7 text-white sm:px-8 sm:py-9">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-lime">{eyebrow}</p>
      <h1 className="mt-2 max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
      <div className="mt-3 max-w-3xl space-y-2 text-sm leading-6 text-white/80 sm:text-base">{children}</div>
    </section>
  );
}

export function OnThisPage({ links }: { links: { href: string; label: string }[] }) {
  return (
    <nav aria-label="On this page" className="flex flex-wrap items-center gap-2">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-slate">On this page</span>
      <ul className="flex flex-wrap gap-2">
        {links.map((link) => (
          <li key={link.href}>
            <a
              href={link.href}
              className="block rounded-full border border-line bg-white px-3 py-1 text-sm font-medium text-ink hover:border-ink"
            >
              {link.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

export function SectionHeader({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow: string;
  title: string;
  children?: React.ReactNode;
}) {
  return (
    <header className="max-w-3xl">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-forest">{eyebrow}</p>
      <h2 id={id} className="mt-1.5 scroll-mt-6 text-2xl font-semibold tracking-tight text-ink">
        {title}
      </h2>
      {children && <div className="mt-2 space-y-2 text-sm leading-6 text-slate">{children}</div>}
    </header>
  );
}

export function NotGenerated({ title = "Results not generated yet", children }: { title?: string; children?: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-dashed border-field bg-white px-4 py-4 sm:px-5">
      <p className="text-sm font-semibold text-ink">{title}</p>
      {children && <div className="mt-1 text-sm leading-6 text-slate">{children}</div>}
    </div>
  );
}

const CHIP_TONES = {
  neutral: "border-line bg-mist text-ink",
  lime: "border-lime-soft bg-lime-soft text-forest",
  fynn: "border-fynn-soft bg-fynn-soft text-cobalt",
  peach: "border-peach-soft bg-peach-soft text-ember",
  bad: "border-red-200 bg-red-50 text-red-800",
  dark: "border-ink bg-ink text-white",
} as const;

export type ChipTone = keyof typeof CHIP_TONES;

export function Chip({ tone = "neutral", children, mono = false }: { tone?: ChipTone; children: React.ReactNode; mono?: boolean }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${CHIP_TONES[tone]} ${
        mono ? "font-mono text-[11px]" : ""
      }`}
    >
      {children}
    </span>
  );
}

/**
 * A <details> whose summary has its own chevron (the native marker disappears with display:flex).
 * The chevron rotates via a child selector rather than group-open, so nested expanders stay independent.
 */
const EXPANDER_TONES = {
  white: { box: "bg-white", hover: "hover:bg-canvas" },
  canvas: { box: "bg-canvas", hover: "hover:bg-mist" },
} as const;

export function Expander({
  summary,
  children,
  tone = "white",
  open = false,
}: {
  summary: React.ReactNode;
  children: React.ReactNode;
  tone?: keyof typeof EXPANDER_TONES;
  open?: boolean;
}) {
  const colors = EXPANDER_TONES[tone];
  return (
    <details
      className={`rounded-xl border border-line [&[open]>summary>span:first-child]:rotate-90 ${colors.box}`}
      open={open}
    >
      <summary
        className={`flex cursor-pointer list-none items-start gap-2.5 rounded-xl px-3 py-2.5 [&::-webkit-details-marker]:hidden ${colors.hover}`}
      >
        <span
          aria-hidden="true"
          className="mt-0.5 inline-block text-xs leading-5 text-slate motion-safe:transition-transform"
        >
          ▶
        </span>
        <span className="min-w-0 flex-1">{summary}</span>
      </summary>
      <div className="border-t border-line px-3 py-3 sm:px-4">{children}</div>
    </details>
  );
}
