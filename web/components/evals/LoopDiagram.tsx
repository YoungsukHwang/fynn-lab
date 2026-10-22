// The regression loop, drawn with HTML and CSS: a row of steps on wide screens, a column on phones.
// The steps are an ordered list, so screen readers get the same sequence; arrows are decorative.

const STEPS = [
  {
    title: "Edit a skill",
    detail: "Change one skill file: a topic skill's body or description, or an always-on skill.",
  },
  {
    title: "Add test cases",
    detail: "When the change covers something no case tests yet, add cases for it first.",
    optional: true,
  },
  {
    title: "Run the test cases that depend on the change",
    detail: "Selection picks only the cases the edit can affect (rules below) and reruns them.",
  },
  {
    title: "Regression report",
    detail: "Compares the rerun with the last run: Passed or Not passed, improved and regressed cases, and a failures overview.",
  },
] as const;

function StepArrow() {
  return (
    <span
      aria-hidden="true"
      className="absolute -bottom-5 left-1/2 -translate-x-1/2 text-sm leading-none text-dim lg:-right-[1.15rem] lg:bottom-auto lg:left-auto lg:top-1/2 lg:translate-x-0 lg:-translate-y-1/2"
    >
      <span className="lg:hidden">▼</span>
      <span className="hidden lg:inline">▶</span>
    </span>
  );
}

function StepNumber({ n, dark = false }: { n: number; dark?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`grid h-6 w-6 shrink-0 place-items-center rounded-full text-xs font-semibold ${
        dark ? "bg-lime text-ink" : "bg-lime-soft text-forest"
      }`}
    >
      {n}
    </span>
  );
}

export function LoopDiagram() {
  return (
    <figure className="rounded-2xl border border-line bg-white p-4 sm:p-6">
      <ol className="grid gap-7 lg:grid-cols-5 lg:gap-6">
        {STEPS.map((step, index) => (
          <li
            key={step.title}
            className={`relative flex flex-col rounded-xl border bg-white px-3.5 py-3 ${
              "optional" in step ? "border-dashed border-field" : "border-line"
            }`}
          >
            <div className="flex items-center gap-2">
              <StepNumber n={index + 1} />
              {"optional" in step && (
                <span className="rounded-full bg-mist px-2 py-0.5 text-[11px] font-medium text-slate">Optional</span>
              )}
            </div>
            <p className="mt-2 text-sm font-semibold leading-5 text-ink">{step.title}</p>
            <p className="mt-1 text-xs leading-5 text-slate">{step.detail}</p>
            <StepArrow />
          </li>
        ))}
        <li className="flex flex-col rounded-xl border border-ink bg-ink px-3.5 py-3 text-white">
          <div className="flex items-center gap-2">
            <StepNumber n={5} dark />
            <span className="text-[11px] font-medium uppercase tracking-[0.12em] text-lime">Decision</span>
          </div>
          <p className="mt-2 text-sm font-semibold leading-5">Safe to ship?</p>
          <ul className="mt-2 space-y-1.5 text-xs leading-5">
            <li className="rounded-lg bg-lime px-2 py-1 font-medium text-ink">
              Yes: the report says Passed (no case regressed). Ship the edit.
            </li>
            <li className="rounded-lg border border-dashed border-white/50 px-2 py-1 text-white/90">
              No: iterate on the skill and go back to step 1.
            </li>
          </ul>
        </li>
      </ol>

      {/* The "No" path back to step 1, drawn as a dashed U under the row (wide screens only). */}
      <div
        aria-hidden="true"
        className="relative mx-[10%] hidden h-9 rounded-b-2xl border-x-2 border-b-2 border-dashed border-field lg:block"
      >
        <span className="absolute -left-[0.4rem] -top-1.5 text-xs leading-none text-field">▲</span>
        <span className="absolute -bottom-2.5 left-1/2 -translate-x-1/2 bg-white px-2 text-xs leading-5 text-slate">
          Not safe: iterate, then run the loop again
        </span>
      </div>

      <figcaption className="mt-5 border-t border-line pt-3 text-xs leading-5 text-slate lg:mt-7">
        The steps follow the regression-testing loop diagram in Kikoff&apos;s &ldquo;Fynn at 100% scale&rdquo; post,
        including its two-part report (Passed or Not passed, then a failures overview). The eval set, the selection
        rules, the rule that Passed means no case regressed, and the rest of the report are Fynn Lab&apos;s own.
      </figcaption>
    </figure>
  );
}
