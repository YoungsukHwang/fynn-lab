// Example messages for the demo. The first is the example message from the post's diagrams
// ("Chase card" swapped for a generic travel card, since the products here are fictional).
// It spans two of the Before bot's four agents; "Three domains" spans three of them.

export const EXAMPLE_QUESTIONS: { label: string; text: string }[] = [
  {
    label: "Blog's example question",
    text: "Why did my score drop last month? And why hasn't my secured card arrived? Should I get the travel card from your marketplace?",
  },
  {
    label: "Three domains",
    text: "My score dropped last month. Would rent reporting help? And if a bill ever went to collections, should I pay it first?",
  },
  {
    label: "Numbered list",
    text: "1. How does rent reporting work? 2. Will it help my score? 3. How much does it cost?",
  },
  {
    label: "Single topic",
    text: "Which card should I pay down first?",
  },
  {
    label: "Debt and taxes",
    text: "If I settle my charged-off card, will it come off my report? And do I owe taxes on the forgiven part?",
  },
];
