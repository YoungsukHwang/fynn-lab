import type { Architecture, Routing } from "@/lib/api";

// Static class strings (Tailwind can't see classes assembled at runtime).
const ACCENT = {
  before: {
    picked: "border-amber-500 bg-amber-50 text-amber-900 ring-2 ring-amber-200",
    badge: "bg-amber-100 text-amber-900",
  },
  after: {
    picked: "border-teal-600 bg-teal-50 text-teal-900 ring-2 ring-teal-200",
    carried: "border-dashed border-teal-500 bg-white text-teal-900",
    badge: "bg-teal-100 text-teal-900",
  },
} as const;

const IDLE = "border-zinc-200 bg-white text-zinc-700";
// De-emphasis comes from the border and background; text stays readable (zinc-500 on zinc-50).
const DIMMED = "border-zinc-200 bg-zinc-50 text-zinc-500";

function Node({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-md border border-zinc-300 bg-white px-3 py-2 text-center text-xs">
      <div className="font-medium text-zinc-900">{title}</div>
      {detail && <div className="mt-0.5 font-mono text-[11px] text-zinc-500">{detail}</div>}
    </div>
  );
}

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2 py-1 text-[11px] text-zinc-500" aria-hidden="true">
      <span>↓</span>
      {label && <span>{label}</span>}
    </div>
  );
}

function SharedBox({ title, skills }: { title: string; skills: string[] }) {
  return (
    <div className="mt-2 rounded-md border border-zinc-300 bg-zinc-100 px-3 py-2 text-xs text-zinc-700">
      <span className="font-medium text-zinc-900">+ {title}:</span> {skills.join(", ")}
    </div>
  );
}

interface DiagramProps {
  architecture: Architecture;
  routing: Routing | null;
  pending: boolean;
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
          const state = !routing ? IDLE : isPicked ? ACCENT.before.picked : DIMMED;
          return (
            <div key={domain.id} className={`rounded-md border px-2 py-1.5 text-xs ${state}`}>
              <div className="font-medium">
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
      <Node title="Expert agent answers" detail={architecture.models.agent} />
    </figure>
  );
}

export function AfterDiagram({ architecture, routing, pending }: DiagramProps) {
  const picked = new Set(routing?.selected ?? []);
  const carried = new Set(routing?.carried ?? []);
  const budget = `picks up to ${architecture.max_new_skills_per_turn} skills, keeps up to ${architecture.max_carried_skills} from the last turn`;
  return (
    <figure aria-label="After architecture: composable skills, one agent">
      <Node title="Member message" />
      <Arrow />
      <Node title="Skill router (small LLM)" detail={architecture.models.router} />
      <Arrow label={pending ? "routing..." : budget} />
      <ul className="flex flex-wrap gap-1.5">
        {architecture.topics.map((topic) => {
          const state = picked.has(topic.name)
            ? ACCENT.after.picked
            : carried.has(topic.name)
              ? ACCENT.after.carried
              : routing
                ? DIMMED
                : IDLE;
          const tag = picked.has(topic.name) ? "picked" : carried.has(topic.name) ? "carried" : null;
          return (
            <li key={topic.name} className={`rounded-full border px-2 py-0.5 text-[11px] ${state}`} title={topic.description}>
              {topic.name}
              {tag && <span className="sr-only"> ({tag})</span>}
            </li>
          );
        })}
      </ul>
      <div className="mt-1.5 flex gap-3 text-[11px] text-zinc-500" aria-hidden="true">
        <span className="flex items-center gap-1">
          <span className={`inline-block h-2.5 w-4 rounded-full border ${ACCENT.after.picked}`} /> picked now
        </span>
        <span className="flex items-center gap-1">
          <span className={`inline-block h-2.5 w-4 rounded-full border ${ACCENT.after.carried}`} /> carried
        </span>
      </div>
      <details className="mt-2 text-xs text-zinc-700">
        <summary className="cursor-pointer text-zinc-600 hover:text-zinc-900">What each skill covers</summary>
        <dl className="mt-2 space-y-1.5">
          {architecture.topics.map((topic) => (
            <div key={topic.name}>
              <dt className="font-mono text-[11px] text-zinc-900">{topic.name}</dt>
              <dd className="text-[11px] leading-4 text-zinc-600">{topic.description}</dd>
            </div>
          ))}
        </dl>
      </details>
      <SharedBox title="Always-on skills" skills={architecture.always_on} />
      <Arrow />
      <Node title="One agent answers with the loaded skills" detail={architecture.models.agent} />
    </figure>
  );
}
