import type { ToscaInstance } from "../types";
import type { Workspace } from "../otterworks-api";

const workspace: Workspace = {
  // Synthetic user ID; identity comes from the last Tosca settings.png.
  user: { id: "user-123", email: "alex.morgan@example.test", displayName: "Alex Morgan",
    createdAt: "2025-01-15T12:00:00.000Z" },
  documents: [],
  // settings.png shows Enabled after TC-SET-002's single click, so start disabled.
  // This is a stored preference, not the service's new-user default (true).
  settings: { notificationEmail: false, notificationInApp: true,
    notificationDesktop: false, theme: "system", language: "en" },
};

export const Profile: ToscaInstance = {
  testCaseId: "TC-SET-001", sheet: "Settings", instance: "Profile",
  row: { TestCaseId: "TC-SET-001", Instance: "Profile", Name: "Alex Morgan",
    Email: "alex.morgan@example.test", UpdatedName: "", Preference: "" },
  workspace,
};

export const Notifications: ToscaInstance = {
  testCaseId: "TC-SET-002", sheet: "Settings", instance: "Notifications",
  row: { TestCaseId: "TC-SET-002", Instance: "Notifications", Name: "Email notifications",
    Email: "", UpdatedName: "", Preference: "" },
  workspace,
};

export const SaveProfile: ToscaInstance = {
  testCaseId: "TC-SET-003", sheet: "Settings", instance: "SaveProfile",
  row: { TestCaseId: "TC-SET-003", Instance: "SaveProfile", Name: "Alex Morgan",
    Email: "alex.morgan@example.test", UpdatedName: "Casey Taylor", Preference: "" },
  workspace,
};
