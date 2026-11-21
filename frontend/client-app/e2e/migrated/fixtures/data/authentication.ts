import type { Workspace } from "../otterworks-api";
import type { ToscaInstance } from "../types";

// The account Tosca signed in with: the ValidSignIn row's email and password,
// with the profile from the legacy Cypress fixture user.json.
const workspace: Workspace = {
  user: {
    id: "user-123",
    email: "alex.morgan@example.test",
    displayName: "Alex Morgan",
    createdAt: "2025-01-15T12:00:00.000Z",
    password: "DemoPass123!",
  },
  documents: [],
};

export const ValidSignIn: ToscaInstance = {
  testCaseId: "TC-AUTH-001",
  sheet: "Authentication",
  instance: "ValidSignIn",
  row: {
    TestCaseId: "TC-AUTH-001",
    Instance: "ValidSignIn",
    Email: "alex.morgan@example.test",
    Password: "DemoPass123!",
    Name: "",
    InvalidEmail: "",
    Confirmation: "",
  },
  workspace,
};

export const InvalidEmail: ToscaInstance = {
  testCaseId: "TC-AUTH-002",
  sheet: "Authentication",
  instance: "InvalidEmail",
  row: {
    TestCaseId: "TC-AUTH-002",
    Instance: "InvalidEmail",
    Email: "alex.morgan@example.test",
    Password: "DemoPass123!",
    Name: "",
    InvalidEmail: "not-an-address",
    Confirmation: "",
  },
  workspace,
};

export const RequiredName: ToscaInstance & {
  expected: { nameError: string };
} = {
  testCaseId: "TC-AUTH-003",
  sheet: "Authentication",
  instance: "RequiredName",
  row: {
    TestCaseId: "TC-AUTH-003",
    Instance: "RequiredName",
    Email: "alex.new@example.test",
    Password: "DemoPass123!",
    Name: "",
    InvalidEmail: "",
    Confirmation: "",
  },
  workspace,
  // TC-AUTH-003-STEP-05 expects "Name is required", which the app has never
  // shown; see parity table TC-AUTH-003.
  expected: { nameError: "Name must be at least 2 characters" },
};

export const PasswordMismatch: ToscaInstance = {
  testCaseId: "TC-AUTH-004",
  sheet: "Authentication",
  instance: "PasswordMismatch",
  row: {
    TestCaseId: "TC-AUTH-004",
    Instance: "PasswordMismatch",
    Email: "jordan.lee@example.test",
    Password: "DemoPass123!",
    Name: "Jordan Lee",
    InvalidEmail: "",
    Confirmation: "DifferentPass123!",
  },
  workspace,
};
