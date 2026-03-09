"use client";

import {
  ChevronsUpDown,
  InfoIcon,
  MailIcon,
  MoreHorizontalIcon,
  Settings2Icon,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";

import { SettingsDialog } from "./settings";

export function WorkspaceNavMenu() {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settingsDefaultSection, setSettingsDefaultSection] = useState<
    "appearance" | "memory" | "tools" | "skills" | "notification" | "agents" | "cron" | "about"
  >("appearance");
  const [mounted, setMounted] = useState(false);
  const { open: isSidebarOpen } = useSidebar();
  const { t } = useI18n();

  useEffect(() => {
    setMounted(true);
  }, []);

  function openSettings(
    section: "appearance" | "memory" | "tools" | "skills" | "notification" | "agents" | "cron" | "about" = "appearance",
  ) {
    setSettingsDefaultSection(section);
    setSettingsOpen(true);
  }

  return (
    <>
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        defaultSection={settingsDefaultSection}
      />
      <SidebarMenu className="w-full">
        {/* Direct Settings button */}
        <SidebarMenuItem>
          {mounted ? (
            <SidebarMenuButton
              size="lg"
              className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              onClick={() => openSettings("appearance")}
            >
              {isSidebarOpen ? (
                <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
                  <Settings2Icon className="size-4" />
                  <span>{t.common.settings}</span>
                </div>
              ) : (
                <div className="flex size-full items-center justify-center">
                  <Settings2Icon className="text-muted-foreground size-4" />
                </div>
              )}
            </SidebarMenuButton>
          ) : (
            <SidebarMenuButton size="lg" className="pointer-events-none">
              <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
                <Settings2Icon className="size-4" />
                {isSidebarOpen && <span>{t.common.settings}</span>}
              </div>
            </SidebarMenuButton>
          )}
        </SidebarMenuItem>

        {/* About + More dropdown */}
        <SidebarMenuItem>
          {mounted ? (
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton
                  size="lg"
                  className="data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
                >
                  {isSidebarOpen ? (
                    <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
                      <InfoIcon className="size-4" />
                      <span>{t.workspace.about}</span>
                      <ChevronsUpDown className="text-muted-foreground ml-auto size-4" />
                    </div>
                  ) : (
                    <div className="flex size-full items-center justify-center">
                      <MoreHorizontalIcon className="text-muted-foreground size-4" />
                    </div>
                  )}
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                className="w-(--radix-dropdown-menu-trigger-width) min-w-56 rounded-lg"
                align="end"
                sideOffset={4}
              >
                <DropdownMenuGroup>
                  <DropdownMenuItem onClick={() => openSettings("about")}>
                    <InfoIcon />
                    {t.workspace.about}
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <a href="mailto:support@flowengine.ai">
                    <DropdownMenuItem>
                      <MailIcon />
                      {t.workspace.contactUs}
                    </DropdownMenuItem>
                  </a>
                </DropdownMenuGroup>
              </DropdownMenuContent>
            </DropdownMenu>
          ) : (
            <SidebarMenuButton size="lg" className="pointer-events-none">
              <div className="text-muted-foreground flex w-full items-center gap-2 text-left text-sm">
                <InfoIcon className="size-4" />
                {isSidebarOpen && <span>{t.workspace.about}</span>}
              </div>
            </SidebarMenuButton>
          )}
        </SidebarMenuItem>
      </SidebarMenu>
    </>
  );
}
