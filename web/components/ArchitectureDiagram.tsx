import type { Architecture, Routing } from "@/lib/api";

// Static class strings (Tailwind can't see classes assembled at runtime).
const PICKED = {
  before: "border-peach bg-peach-soft text-ember ring-2 ring-peach/40",
  after: "border-fynn bg-fynn-soft text-cobalt ring-2 ring-fynn/25",
} as const;

const IDLE = "border-line bg-white text-ink";
// De-emphasis comes from the border and background; text stays readable (dim is 4.9:1 on canvas).
const DIMMED = "border-line bg-canvas text-dim";

function Node({ title, detail, tone = "light" }: { title: string; detail?: string; tone?: "light" | "dark" }) {
  const dark = tone === "dark";
  return (
    <div
      className={`rounded-xl border px-3 py-2 text-center text-xs ${
        dark ? "border-ink bg-ink text-white" : "border-line bg-white text-ink"
      }`}
    >
      <div className="font-semibold">{title}</div>
      {detail && <div className={`mt-0.5 font-mono text-[11px] ${dark ? "text-lime" : "text-slate"}`}>{detail}</div>}
    </div>
  );
}

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center py-1 text-[11px] text-slate" aria-hidden="true">
      <span className="h-3 w-px bg-line" />
      {label && <span className="my-0.5 rounded-full bg-mist px-2 py-0.5">{label}</span>}
      <span className="leading-none text-dim">▾</span>
    </div>
  );
}

function SharedBox({ title, skills }: { title: string; skills: string[] }) {
  return (
    <div className="mt-2 rounded-xl bg-mist px-3 py-2 text-xs text-slate">
      <span className="font-semibold text-ink">+ {title}:</span> {skills.join(", ")}
    </div>
  );
}

interface DiagramProps {
  architecture: Architecture;
  routing: Routing | null;
  pending: boolean;
  // After only: the skills the app will send as carry_skills with the next message.
  carryNext?: string[];
}

export function BeforeDiagram({ architecture, routing, pending }: DiagramProps) {
  const picked = routing?.selected[0];
  return (
    <figure aria-label="Before architecture: one expert agent per message">
      <Node title="Member message" />
      <Arrow />
      <Node title="Agent router (small LLM)" detail={architecture.models.router} />
      <Arrow label={pending ? "routing..." : "picks exactly 1 agent"} />
      <div className="grid grid-cols-2 gap-2">
        {architecture.domains.map((domain) => {
          const isPicked = Boolean(routing) && domain.id === picked;
          const state = !routing ? IDLE : isPicked ? PICKED.before : DIMMED;
          return (
            <div key={domain.id} className={`rounded-xl border px-2.5 py-2 text-xs transition-colors ${state}`}>
              <div className="font-semibold">
                {domain.title}
                {isPicked && <span className="sr-only"> (picked)</span>}
              </div>
              <div className="mt-0.5 text-[11px] leading-4">{domain.skills.join(", ")}</div>
            </div>
          );
        })}
      </div>
      <SharedBox title="Shared instructions in every agent" skills={architecture.always_on} />
      <Arrow />
      <Node title="Expert agent answers" detail={architecture.models.agent} tone="dark" />
    </figure>
  );
}

export function AfterDiagram({ architecture, routing, pending, carryNext = [] }: DiagramProps) {
  // Router output only; carried skills are shown in their own app-side box below.
  const picked = new Set(routing?.selected ?? []);
  // After a reply: what the app actually kept. Before one: every candidate it sends; the backend
  // keeps up to max_carried_skills of those the router didn't pick again.
  const kept = routing ? routing.carried.join(", ") || "none" : null;
  const candidates = carryNext.length
    ? `${carryNext.join(", ")} (sent with ${pending ? "this" : "the next"} message; up to ${architecture.max_carried_skills} kept after routing)`
    : "none";
  return (
    <figure aria-label="After architecture: composable skills, one agent">
      <Node title="Member message" />
      <Arrow />
      <Node title="Skill router (small LLM)" detail={architecture.models.router} />
      <Arrow label={pending ? "routing..." : `picks the matching skills (up to ${architecture.max_new_skills_per_turn})`} />
      <ul className="flex flex-wrap justify-center gap-1.5">
        {architecture.topics.map((topic) => {
          const isPicked = picked.has(topic.name);
          const state = isPicked ? PICKED.after : routing ? DIMMED : IDLE;
          return (
            <li
              key={topic.name}
              className={`rounded-full border px-2.5 py-0.5 text-[11px] font-medium transition-colors ${state}`}
              title={topic.description}
            >
              {topic.name}
              {isPicked && <span className="sr-only"> (picked)</span>}
            </li>
          );
        })}
      </ul>
      <div className="mt-2 flex justify-center gap-3 text-[11px] text-slate" aria-hidden="true">
        <span className="flex items-center gap-1.5">
          <span className={`inline-block h-2.5 w-4 rounded-full border ${PICKED.after}`} /> picked by the router
        </span>
      </div>
      <details className="mt-2 rounded-xl border border-line bg-white px-3 py-2 text-xs text-slate">
        <summary className="cursor-pointer font-medium text-ink">What each skill covers</summary>
        <dl className="mt-2 space-y-2">
          {architecture.topics.map((topic) => (
            <div key={topic.name}>
              <dt className="font-mono text-[11px] font-medium text-ink">{topic.name}</dt>
              <dd className="text-[11px] leading-4">{topic.description}</dd>
            </div>
          ))}
        </dl>
      </details>
      <div className="mt-2 rounded-xl border border-dashed border-fynn bg-white px-3 py-2 text-xs text-slate">
        <span className="font-semibold text-ink">+ Kept from the previous turn:</span> {kept ?? candidates}
        <span className="block pt-0.5 text-[11px] text-dim">
          Fynn Lab addition, done by the app rather than the router; up to {architecture.max_carried_skills}.
        </span>
      </div>
      <SharedBox title="Always-on skills" skills={architecture.always_on} />
      <Arrow />
      <Node title="One agent answers with the loaded skills" detail={architecture.models.agent} tone="dark" />
    </figure>
  );
}
