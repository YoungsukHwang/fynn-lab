import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

// Coach replies use bold headers, bullets and numbered lists; style them without a typography plugin.
// remark-breaks keeps single newlines (e.g. a bold header line followed by its text) as line breaks.
export function Markdown({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-6 text-zinc-800">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-zinc-900">{children}</strong>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5">{children}</ol>,
          h1: ({ children }) => <p className="font-semibold text-zinc-900">{children}</p>,
          h2: ({ children }) => <p className="font-semibold text-zinc-900">{children}</p>,
          h3: ({ children }) => <p className="font-semibold text-zinc-900">{children}</p>,
          a: ({ children, href }) => (
            <a href={href} className="underline" target="_blank" rel="noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}
