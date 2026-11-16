import { useCallback, useRef, useState } from "react";

const ignoreError = () => {};

export function usePreviewRetry(
  initialUrl: string,
  retryWithFreshUrl: () => Promise<string>,
  onError: () => void = ignoreError,
) {
  const [url, setUrl] = useState(initialUrl);
  const [retryVersion, setRetryVersion] = useState(0);
  const attempted = useRef(false);

  const retry = useCallback(async () => {
    if (attempted.current) {
      onError();
      return;
    }
    attempted.current = true;
    try {
      setUrl(await retryWithFreshUrl());
      setRetryVersion((version) => version + 1);
    } catch {
      onError();
    }
  }, [retryWithFreshUrl, onError]);

  return { url, retry, retryVersion };
}
