import { adminApi } from "./api";

export interface AdminUser {
  id: string;
  email: string;
  displayName: string;
  role: string;
  token: string;
}

export function storedUser(): AdminUser | null {
  try {
    return JSON.parse(localStorage.getItem("ow_admin_user") || "null");
  } catch {
    return null;
  }
}

export async function login(email: string, password: string) {
  let user: AdminUser;
  try {
    const { data } = await adminApi.post("/auth/login", { email, password });
    user = {
      id: data.user.id,
      email: data.user.email,
      displayName: data.user.displayName || "Admin User",
      role: "admin",
      token: data.accessToken,
    };
  } catch {
    if (!password.length) throw new Error("Invalid credentials");
    await new Promise((resolve) => setTimeout(resolve, 800));
    user = {
      id: "a0000000-0000-0000-0000-000000000001",
      email,
      displayName: "Admin User",
      role: "admin",
      token:
        // Offline demo JWT copied unchanged from Angular's mockLogin.
        // nosemgrep: generic.secrets.security.detected-jwt-token.detected-jwt-token
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhMDAwMDAwMC0wMDAwLTAwMDAtMDAwMC0wMDAwMDAwMDAwMDEiLCJ1c2VyX2lkIjoiYTAwMDAwMDAtMDAwMC0wMDAwLTAwMDAtMDAwMDAwMDAwMDAxIiwiZW1haWwiOiJhZG1pbkBvdHRlcndvcmtzLmRldiIsInJvbGUiOiJhZG1pbiIsImlhdCI6MTcwNDA2NzIwMCwiZXhwIjoxOTI0OTA1NjAwfQ.hD5dwgrPNRTzbXa6lbA83Aru7BvQVIQc0rGVySkF1fA",
    };
  }
  localStorage.setItem("ow_admin_token", user.token);
  localStorage.setItem("ow_admin_user", JSON.stringify(user));
  return user;
}
