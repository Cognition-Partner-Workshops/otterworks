import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

export function AuthGuard({ children }: { children: ReactNode }) {
  if (!localStorage.getItem("ow_admin_token")) {
    return <Navigate to="/admin/login" replace />;
  }
  return <>{children}</>;
}
