import { SectionTabs } from "@/components/SectionTabs";

/** The frame of an eval section: its name, what it asks, and the Framework / Results tabs. */
export function SectionShell({
  base,
  name,
  question,
  children,
}: {
  base: string;
  name: string;
  question: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-forest">{name}</p>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate">{question}</p>
        <div className="mt-3">
          <SectionTabs base={base} label={name} />
        </div>
      </div>
      {children}
    </div>
  );
}
