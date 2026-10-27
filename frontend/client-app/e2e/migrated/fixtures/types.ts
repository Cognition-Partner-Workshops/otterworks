import type { Workspace } from "./otterworks-api";

export type ToscaInstance = {
  testCaseId: string;
  sheet: string;
  instance: string;
  row: Record<string, string>;
  workspace: Workspace;
};
