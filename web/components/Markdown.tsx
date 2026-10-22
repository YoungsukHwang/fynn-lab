import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

// Coach replies use bold headers, bullets and numbered lists; style them without a typography plugin.
// remark-breaks keeps single newlines (e.g. a bold header line followed by its text) as line breaks.
export function Markdown({ text }: { text: string }) {
  return (
    <div className="space-y-2 text-sm leading-6 text-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkBreaks]}
        components={{
          p: ({ children }) => <p>{children}</p>,
          strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
          ul: ({ children }) => <ul className="list-disc space-y-1 pl-5 marker:text-dim">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal space-y-1 pl-5 marker:text-dim">{children}</ol>,
          h1: ({ children }) => <p className="font-semibold text-ink">{children}</p>,
          h2: ({ children }) => <p className="font-semibold text-ink">{children}</p>,
          h3: ({ children }) => <p className="font-semibold text-ink">{children}</p>,
          a: ({ children, href }) => (
            <a href={href} className="font-medium underline underline-offset-2" target="_blank" rel="noreferrer">
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
