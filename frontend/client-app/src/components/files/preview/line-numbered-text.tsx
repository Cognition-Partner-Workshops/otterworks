export function LineNumberedText({ text }: { text: string }) {
  let lineCount = 1;
  for (let index = 0; index < text.length; index += 1) {
    if (text.charCodeAt(index) === 10) lineCount += 1;
  }
  if (text.endsWith("\n")) lineCount -= 1;
  const lineNumbers = Array.from({ length: lineCount }, (_, index) => index + 1).join("\n");

  return (
    <div
      data-testid="line-numbered-text"
      className="max-h-[70vh] max-w-full overflow-auto rounded bg-gray-950 p-4 font-mono text-xs leading-5 text-gray-100"
    >
      <div className="flex w-max min-w-full">
        <pre
          aria-hidden="true"
          data-testid="line-number-gutter"
          className="mr-4 w-10 shrink-0 select-none text-right text-gray-500"
        >
          {lineNumbers}
        </pre>
        <pre data-testid="line-number-content" className="min-w-max shrink-0 whitespace-pre">
          {text}
        </pre>
      </div>
    </div>
  );
}
