"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useLayoutEffect, useState } from "react";
import { Toaster } from "sonner";

import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { SettingsDialog, SettingsProvider, useSettings } from "@/components/workspace/settings";
import { WorkspaceSidebar } from "@/components/workspace/workspace-sidebar";
import { getLocalSettings, useLocalSettings } from "@/core/settings";

const queryClient = new QueryClient();

function WorkspaceLayoutInner({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const [settings, setSettings] = useLocalSettings();
  const [open, setOpen] = useState(false);
  const { open: settingsOpen, closeSettings } = useSettings();

  useLayoutEffect(() => {
    setOpen(!getLocalSettings().layout.sidebar_collapsed);
  }, []);
  useEffect(() => {
    setOpen(!settings.layout.sidebar_collapsed);
  }, [settings.layout.sidebar_collapsed]);

  const handleOpenChange = useCallback(
    (open: boolean) => {
      setOpen(open);
      setSettings("layout", { sidebar_collapsed: !open });
    },
    [setSettings],
  );

  return (
    <SidebarProvider
      className="h-screen"
      open={open}
      onOpenChange={handleOpenChange}
    >
      <WorkspaceSidebar />
      <SidebarInset className="min-w-0">{children}</SidebarInset>
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={(v) => { if (!v) closeSettings(); }}
      />
    </SidebarProvider>
  );
}

export default function WorkspaceLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <WorkspaceLayoutInner>{children}</WorkspaceLayoutInner>
      </SettingsProvider>
      <Toaster position="top-center" />
    </QueryClientProvider>
  );
}
