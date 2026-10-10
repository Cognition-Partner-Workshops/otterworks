export function LineNumberedText({ text }: { text: string }) {
  const lines = text.split("\n");
  if (text.endsWith("\n")) lines.pop();

  return (
    <div
      data-testid="line-numbered-text"
      className="max-h-[70vh] overflow-auto rounded bg-gray-950 p-4 font-mono text-xs leading-5 text-gray-100"
    >
      {lines.map((line, index) => (
        <div key={index} className="flex min-w-0">
          <span
            data-testid="line-number"
            className="mr-4 inline-block w-8 shrink-0 select-none text-right text-gray-500"
          >
            {index + 1}
          </span>
          <span className="whitespace-pre-wrap break-all">{line || " "}</span>
        </div>
      ))}
    </div>
  );
}
