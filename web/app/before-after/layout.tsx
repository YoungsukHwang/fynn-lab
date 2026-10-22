import { SectionShell } from "@/components/evals/SectionShell";

export default function BeforeAfterLayout({ children }: LayoutProps<"/before-after">) {
  return (
    <SectionShell
      base="/before-after"
      name="Before vs After"
      question="Does routing each message to composable skills answer members better than routing it to one domain agent?"
    >
      {children}
    </SectionShell>
  );
}
