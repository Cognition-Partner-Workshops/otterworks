import { useCallback, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { filesApi } from "@/lib/api";

export function usePreviewUrl(id: string, enabled = true) {
  const queryClient = useQueryClient();
  const queryKey = useMemo(() => ["files", id, "download-url"], [id]);
  const queryFn = useCallback(() => filesApi.getDownloadUrl(id), [id]);
  const query = useQuery({
    queryKey,
    queryFn,
    enabled: Boolean(id) && enabled,
    staleTime: 30 * 60 * 1000,
  });

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey, refetchType: "none" });
    return queryClient.fetchQuery({ queryKey, queryFn, staleTime: 0 });
  }, [queryClient, queryFn, queryKey]);

  const notFound = isAxiosError(query.error) && query.error.response?.status === 404;

  return {
    url: query.data,
    isLoading: query.isLoading,
    notFound,
    error: query.error,
    refresh,
  };
}
