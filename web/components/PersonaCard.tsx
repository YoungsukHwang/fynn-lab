import type { Persona } from "@/lib/api";

const PRODUCT_LABELS: Record<string, string> = {
  credit_builder: "Credit Builder",
  secured_card: "Secured Card",
  rent_reporting: "Rent Reporting",
  bill_reporting: "Bill Reporting",
  debt_settlement: "Debt Settlement",
};

function productSummary(name: string, product: Record<string, unknown>): string {
  const label = PRODUCT_LABELS[name] ?? name;
  return typeof product.status === "string" ? `${label} (${product.status})` : label;
}

function Stat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-canvas px-3 py-2">
      <dt className="text-[11px] font-medium uppercase tracking-wide text-slate">{label}</dt>
      <dd className="mt-0.5 text-sm font-semibold text-ink">{children}</dd>
    </div>
  );
}

export function PersonaCard({ persona }: { persona: Persona }) {
  const score = persona.credit.score;
  const util = persona.credit.utilization;
  // A member with no revolving credit has no utilization to show (not 0%).
  const utilization = util?.total_revolving_limit ? util.overall : null;
  const products = Object.entries(persona.products).filter(
    (entry): entry is [string, Record<string, unknown>] => entry[1] !== null,
  );

  return (
    <div className="rounded-2xl border border-line bg-white p-4 sm:p-5">
      <div className="flex items-start gap-3">
        <span
          aria-hidden="true"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-lime-soft text-sm font-semibold text-forest"
        >
          {persona.name.slice(0, 1)}
        </span>
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">{persona.name}</p>
          <p className="mt-0.5 text-sm leading-6 text-slate">{persona.summary}</p>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
        {score?.current !== undefined && (
          <Stat label={`Score (${score.model ?? "model n/a"})`}>
            {score.current}
            {score.previous !== undefined && <span className="ml-1 font-normal text-slate">from {score.previous}</span>}
          </Stat>
        )}
        <Stat label="Utilization">
          {typeof utilization === "number" ? `${Math.round(utilization * 100)}%` : "No credit cards"}
        </Stat>
        <Stat label="Products">
          <span className="font-medium">
            {products.length ? products.map(([name, p]) => productSummary(name, p)).join(", ") : "None"}
          </span>
        </Stat>
        <Stat label="Profile date">{persona.as_of}</Stat>
      </dl>
    </div>
  );
}
