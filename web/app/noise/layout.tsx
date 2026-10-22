import { SectionShell } from "@/components/evals/SectionShell";

export default function NoiseLayout({ children }: LayoutProps<"/noise">) {
  return (
    <SectionShell
      base="/noise"
      name="Noise & A/A"
      question="LLM replies vary from run to run. How much of a difference between two runs is a real change?"
    >
      {children}
    </SectionShell>
  );
}
