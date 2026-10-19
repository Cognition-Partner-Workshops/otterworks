import { createContext, useContext, useState, type ReactNode } from "react";
import { fixtures as baseFixtures } from "@/fixtures/fixtures";
import type { Fixtures, Person } from "@/fixtures/types";
import { isValidTenantId } from "@/tenant";

export interface WorkbenchUser {
  sub: string;
  name: string;
  email: string;
}

export interface WorkbenchContextValue {
  fixtures: Fixtures;
  user: WorkbenchUser;
  mode: "hosted" | "static";
  tenantId: string;
  setTenantId: (tenantId: string) => void;
}

function staticUser(fixtures: Fixtures): WorkbenchUser {
  const person: Person | undefined = fixtures.people.find((candidate) => candidate.id === fixtures.currentUserId);
  return {
    sub: fixtures.currentUserId,
    name: person?.name ?? "Local user",
    email: person?.title ?? "",
  };
}

const defaultContext: WorkbenchContextValue = {
  fixtures: baseFixtures,
  user: staticUser(baseFixtures),
  mode: "static",
  tenantId: "",
  setTenantId: () => undefined,
};

export const WorkbenchContext = createContext<WorkbenchContextValue>(defaultContext);

export function WorkbenchProvider({ value, children }: { value: Omit<WorkbenchContextValue, "user"> & { user?: WorkbenchUser }; children: ReactNode }) {
  const [tenantId, setTenant] = useState(value.tenantId);
  const setTenantId = (requested: string) => {
    const tenant = requested && isValidTenantId(requested) ? requested : "";
    value.setTenantId(tenant);
    setTenant(tenant);
  };
  return (
    <WorkbenchContext.Provider value={{
      ...value,
      tenantId,
      setTenantId,
      user: value.user ?? staticUser(value.fixtures),
    }}>
      {children}
    </WorkbenchContext.Provider>
  );
}

export function useWorkbench(): WorkbenchContextValue {
  return useContext(WorkbenchContext);
}
