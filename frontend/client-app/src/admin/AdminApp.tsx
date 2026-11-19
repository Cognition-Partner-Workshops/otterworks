import { Route, Routes, useParams } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import { QueryProvider } from "@/providers/query-provider";
import Shell, { legacyUrl } from "./layout/Shell";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Users from "./pages/Users";

function UserDetail() {
  const { id } = useParams();
  return (
    <section>
      <h1 className="mb-4 text-2xl font-semibold">
        User details — not yet ported
      </h1>
      <a
        className="text-blue-700 underline"
        href={`${legacyUrl}/users/${encodeURIComponent(id ?? "")}`}
      >
        Open user details in the Angular admin app
      </a>
    </section>
  );
}

export default function AdminApp() {
  return (
    <QueryProvider>
      <Routes>
        <Route path="login" element={<Login />} />
        <Route element={<Shell />}>
          <Route index element={<Dashboard />} />
          <Route path="users" element={<Users />} />
          <Route path="users/:id" element={<UserDetail />} />
          <Route
            path="*"
            element={
              <p>
                Not yet ported.{" "}
                <a href={legacyUrl} className="text-blue-700 underline">
                  Open the Angular admin app
                </a>
              </p>
            }
          />
        </Route>
      </Routes>
      <Toaster />
    </QueryProvider>
  );
}
