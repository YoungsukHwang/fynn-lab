import { SectionShell } from "@/components/evals/SectionShell";

export default function SkillEditsLayout({ children }: LayoutProps<"/skill-edits">) {
  return (
    <SectionShell
      base="/skill-edits"
      name="Skill edits"
      question="When one skill file changes on the After bot, which cases need rerunning, and is the edit safe to ship?"
    >
      {children}
    </SectionShell>
  );
}
