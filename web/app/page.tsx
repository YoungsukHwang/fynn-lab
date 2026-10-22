import type { Metadata } from "next";

import { Demo } from "@/components/Demo";

// The layout's title template only applies to child segments, so the root page sets its full title.
export const metadata: Metadata = { title: { absolute: "Demo | Fynn Lab" } };

export default function DemoPage() {
  return (
    <div className="flex flex-col gap-5">
      <div className="max-w-3xl">
        <h1 className="text-2xl font-semibold tracking-tight">Single agent vs composable skills</h1>
        <p className="mt-2 text-sm text-zinc-600">
          Both bots read the same skill files, see the same member profile and use the same answer model. They differ in
          how each message is routed and how the prompt is put together. The After bot also keeps some of the
          previous turn&apos;s skills for one more turn, which is a Fynn Lab addition. Ask both the same question to see which
          guidance each one loads, and how that changes the answer.
        </p>
      </div>
      <Demo />
    </div>
  );
}
