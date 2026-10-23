// The same section header as the other single-page section (Online evaluation), without tabs.
export default function ModelsLayout({ children }: LayoutProps<"/models">) {
  return (
    <div className="flex flex-col gap-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-forest">Models</p>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-slate">
          Which answer model is worth its cost, and can the eval&apos;s judge be trusted?
        </p>
      </div>
      {children}
    </div>
  );
}
