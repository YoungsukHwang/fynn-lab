// The same section header as SectionShell, without the Framework / Results tabs: this section is one page.
export default function OnlineEvaluationLayout({ children }: LayoutProps<"/online-evaluation">) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-forest">Online evaluation</p>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate">
          If Coach answered real members, how would a change be shown to help them, and not only to pass the offline
          eval set?
        </p>
      </div>
      {children}
    </div>
  );
}
