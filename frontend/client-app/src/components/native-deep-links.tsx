import { App as CapacitorApp } from "@capacitor/app";
import { Capacitor, type PluginListenerHandle } from "@capacitor/core";
import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { getDeepLinkPath } from "@/lib/deep-link";
import { getPublicWebOrigin } from "@/lib/public-web-origin";
import { useAuthStore } from "@/stores/auth-store";

export function NativeDeepLinks() {
  const [pendingPath, setPendingPath] = useState<string | null>(null);
  const { isAuthenticated, isLoading } = useAuthStore();
  const { pathname } = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (Capacitor.getPlatform() !== "ios") return;

    const publicOrigin = getPublicWebOrigin();
    const isInitialPage = window.location.pathname === "/";
    let active = true;
    let receivedOpen = false;
    let listener: PluginListenerHandle | undefined;

    const subscribe = async () => {
      listener = await CapacitorApp.addListener("appUrlOpen", ({ url }) => {
        if (!active) return;
        const path = getDeepLinkPath(url, publicOrigin);
        if (path) {
          receivedOpen = true;
          setPendingPath(path);
        }
      });
      if (!active) {
        await listener.remove();
        return;
      }
      if (!isInitialPage) return;
      const launch = await CapacitorApp.getLaunchUrl();
      if (active && !receivedOpen && launch?.url) {
        setPendingPath(getDeepLinkPath(launch.url, publicOrigin));
      }
    };
    void subscribe().catch(() => {});

    return () => {
      active = false;
      void listener?.remove().catch(() => {});
    };
  }, []);

  useEffect(() => {
    if (!pendingPath || isLoading) return;
    setPendingPath(null);
    if (!isAuthenticated) {
      navigate("/login", { replace: pathname === "/login", state: { deepLinkPath: pendingPath } });
    } else if (pendingPath !== pathname) {
      navigate(pendingPath);
    }
  }, [isAuthenticated, isLoading, navigate, pathname, pendingPath]);

  return null;
}
