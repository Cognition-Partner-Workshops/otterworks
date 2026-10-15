import type { ReactNode } from "react";

const inlinePattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\(https?:\/\/[^)]+\)|https?:\/\/[^\s<]+|@[a-zA-Z0-9_-]+)/g;

function inlineContent(text: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let previousEnd = 0;
  let index = 0;

  for (const match of text.matchAll(inlinePattern)) {
    const value = match[0];
    const start = match.index ?? 0;
    if (start > previousEnd) nodes.push(text.slice(previousEnd, start));

    if (value.startsWith("**")) {
      nodes.push(<strong key={index}>{value.slice(2, -2)}</strong>);
    } else if (value.startsWith("`")) {
      nodes.push(<code key={index} className="rounded bg-otter-100 px-1 py-0.5 text-sm">{value.slice(1, -1)}</code>);
    } else if (value.startsWith("[")) {
      const link = value.match(/^\[([^\]]+)\]\((https?:\/\/[^)]+)\)$/);
      if (link) {
        nodes.push(<a key={index} href={link[2]} target="_blank" rel="noreferrer">{link[1]}</a>);
      }
    } else if (value.startsWith("http")) {
      const url = value.replace(/[),.!?;:]+$/, "");
      const trailing = value.slice(url.length);
      nodes.push(<a key={index} href={url} target="_blank" rel="noreferrer">{url}</a>);
      if (trailing) nodes.push(trailing);
    } else {
      nodes.push(<span key={index} className="font-medium text-otter-700">{value}</span>);
    }
    previousEnd = start + value.length;
    index += 1;
  }

  if (previousEnd < text.length) nodes.push(text.slice(previousEnd));
  return nodes;
}

export function MarkdownText({ text }: { text: string }) {
  const paragraphs = text.split(/\n{2,}/).filter(Boolean);

  return (
    <div className="space-y-3">
      {paragraphs.map((paragraph, paragraphIndex) => {
        const lines = paragraph.split("\n");
        const isList = lines.every((line) => line.startsWith("- "));
        if (isList) {
          return (
            <ul className="list-disc space-y-1 pl-5" key={paragraphIndex}>
              {lines.map((line, lineIndex) => <li key={lineIndex}>{inlineContent(line.slice(2))}</li>)}
            </ul>
          );
        }
        return (
          <p className="whitespace-pre-wrap" key={paragraphIndex}>
            {lines.map((line, lineIndex) => (
              <span key={lineIndex}>
                {lineIndex > 0 && <br />}
                {inlineContent(line)}
              </span>
            ))}
          </p>
        );
      })}
    </div>
  );
}
