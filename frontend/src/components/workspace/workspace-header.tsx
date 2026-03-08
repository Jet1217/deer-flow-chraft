"use client";

import { BrainCircuitIcon, MessageSquarePlus } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";

import {
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarTrigger,
  useSidebar,
} from "@/components/ui/sidebar";
import { useI18n } from "@/core/i18n/hooks";
import { env } from "@/env";
import { cn } from "@/lib/utils";

export function WorkspaceHeader({ className }: { className?: string }) {
  const { t } = useI18n();
  const { state } = useSidebar();
  const pathname = usePathname();
  return (
    <>
      <div
        className={cn(
          "group/workspace-header flex h-12 flex-col justify-center",
          className,
        )}
      >
        {state === "collapsed" ? (
          <div className="flex w-full cursor-pointer items-center justify-center">
            <div className="flex size-6 items-center justify-center rounded-md bg-black dark:bg-white group-hover/workspace-header:hidden">
              <BrainCircuitIcon className="size-3.5 text-white dark:text-black" />
            </div>
            <SidebarTrigger className="hidden group-hover/workspace-header:flex" />
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 px-2">
            {env.NEXT_PUBLIC_STATIC_WEBSITE_ONLY === "true" ? (
              <Link href="/" className="flex items-center gap-2">
                <div className="flex size-6 items-center justify-center rounded-md bg-black dark:bg-white">
                  <BrainCircuitIcon className="size-3.5 text-white dark:text-black" />
                </div>
                <span className="text-[14px] font-semibold tracking-tight">Chraft</span>
              </Link>
            ) : (
              <div className="flex items-center gap-2">
                <div className="flex size-6 items-center justify-center rounded-md bg-black dark:bg-white">
                  <BrainCircuitIcon className="size-3.5 text-white dark:text-black" />
                </div>
                <span className="text-[14px] font-semibold tracking-tight">Chraft</span>
              </div>
            )}
            <SidebarTrigger />
          </div>
        )}
      </div>
      <SidebarMenu>
        <SidebarMenuItem>
          <SidebarMenuButton
            isActive={pathname === "/workspace/chats/new"}
            asChild
          >
            <Link className="text-muted-foreground" href="/workspace/chats/new">
              <MessageSquarePlus size={16} />
              <span>{t.sidebar.newChat}</span>
            </Link>
          </SidebarMenuButton>
        </SidebarMenuItem>
      </SidebarMenu>
    </>
  );
}
