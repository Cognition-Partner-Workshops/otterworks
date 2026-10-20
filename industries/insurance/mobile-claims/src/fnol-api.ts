import { apiClient } from "@/lib/api-client";

export interface FnolReceipt {
  status: string;
  rqUid: string;
  claimNumber: string;
}

export async function submitFnol(xml: string): Promise<FnolReceipt> {
  const { data } = await apiClient.post<FnolReceipt>("/claims/fnol", xml, {
    headers: { "Content-Type": "application/xml" },
  });
  return data;
}
