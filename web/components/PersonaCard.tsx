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

export function PersonaCard({ persona }: { persona: Persona }) {
  const score = persona.credit.score;
  const util = persona.credit.utilization;
  // A member with no revolving credit has no utilization to show (not 0%).
  const utilization = util?.total_revolving_limit ? util.overall : null;
  const products = Object.entries(persona.products).filter(
    (entry): entry is [string, Record<string, unknown>] => entry[1] !== null,
  );

  return (
    <div className="rounded-lg border border-zinc-200 bg-white p-4">
      <p className="text-sm text-zinc-700">{persona.summary}</p>
      <dl className="mt-3 flex flex-wrap gap-x-6 gap-y-2 text-sm">
        {score?.current !== undefined && (
          <div>
            <dt className="text-xs uppercase tracking-wide text-zinc-500">Score ({score.model})</dt>
            <dd className="font-medium text-zinc-900">
              {score.current}
              {score.previous !== undefined && (
                <span className="ml-1 font-normal text-zinc-500">from {score.previous}</span>
              )}
            </dd>
          </div>
        )}
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Utilization</dt>
          <dd className="font-medium text-zinc-900">
            {typeof utilization === "number" ? `${Math.round(utilization * 100)}%` : "No credit cards"}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Products</dt>
          <dd className="text-zinc-900">
            {products.length ? products.map(([name, p]) => productSummary(name, p)).join(", ") : "None"}
          </dd>
        </div>
        <div>
          <dt className="text-xs uppercase tracking-wide text-zinc-500">Profile date</dt>
          <dd className="text-zinc-900">{persona.as_of}</dd>
        </div>
      </dl>
    </div>
  );
}
