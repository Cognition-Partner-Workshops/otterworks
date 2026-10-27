export function legacyDetails({
  suite,
  id,
  group,
  source,
  method,
}: {
  suite: "tosca" | "cypress" | "selenium";
  id: string;
  group: string;
  source: string;
  method?: string;
}) {
  return {
    tag: [`@${id}`, `@${group}`],
    annotation: {
      type: suite,
      description: `${source}${method ? `#${method}` : ""}`,
    },
  };
}
