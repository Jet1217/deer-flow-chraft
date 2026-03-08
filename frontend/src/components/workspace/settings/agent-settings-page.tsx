"use client";

import { BotIcon, MessageSquareIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import {
  Item,
  ItemActions,
  ItemContent,
  ItemDescription,
  ItemTitle,
} from "@/components/ui/item";
import { useAgents, useDeleteAgent } from "@/core/agents";
import type { Agent } from "@/core/agents/types";
import { useI18n } from "@/core/i18n/hooks";

import { SettingsSection } from "./settings-section";

export function AgentSettingsPage({ onClose }: { onClose?: () => void } = {}) {
  const { t } = useI18n();
  const { agents, isLoading, error } = useAgents();

  return (
    <SettingsSection
      title={t.settings.agents.title}
      description={t.settings.agents.description}
    >
      {isLoading ? (
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      ) : error ? (
        <div className="text-destructive text-sm">Error: {error.message}</div>
      ) : (
        <AgentSettingsList agents={agents} onClose={onClose} />
      )}
    </SettingsSection>
  );
}

function AgentSettingsList({
  agents,
  onClose,
}: {
  agents: Agent[];
  onClose?: () => void;
}) {
  const { t } = useI18n();
  const router = useRouter();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const { mutate: deleteAgent, isPending: isDeleting } = useDeleteAgent();

  const handleNewAgent = () => {
    onClose?.();
    router.push("/workspace/agents/new");
  };

  const handleChat = (agentName: string) => {
    onClose?.();
    router.push(`/workspace/agents/${agentName}/chats/new`);
  };

  const handleDeleteConfirm = () => {
    if (!deleteTarget) return;
    deleteAgent(deleteTarget, {
      onSuccess: () => {
        toast.success(t.agents.deleteSuccess);
        setDeleteTarget(null);
      },
      onError: (err) => {
        toast.error(err.message);
        setDeleteTarget(null);
      },
    });
  };

  return (
    <>
      <div className="flex w-full flex-col gap-4">
        <header className="flex justify-end">
          <Button size="sm" onClick={handleNewAgent}>
            <PlusIcon className="size-4" />
            {t.agents.newAgent}
          </Button>
        </header>

        {agents.length === 0 ? (
          <EmptyAgents onCreateAgent={handleNewAgent} />
        ) : (
          agents.map((agent) => (
            <Item className="w-full" variant="outline" key={agent.name}>
              <ItemContent>
                <ItemTitle>
                  <div className="flex items-center gap-2">
                    <BotIcon className="text-muted-foreground size-4" />
                    {agent.name}
                  </div>
                </ItemTitle>
                {agent.description && (
                  <ItemDescription className="line-clamp-2">
                    {agent.description}
                  </ItemDescription>
                )}
              </ItemContent>
              <ItemActions>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => handleChat(agent.name)}
                  title={t.agents.chat}
                >
                  <MessageSquareIcon className="size-4" />
                  <span className="hidden sm:inline">{t.agents.chat}</span>
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  className="text-destructive hover:text-destructive"
                  onClick={() => setDeleteTarget(agent.name)}
                  title={t.agents.delete}
                >
                  <Trash2Icon className="size-4" />
                  <span className="hidden sm:inline">{t.agents.delete}</span>
                </Button>
              </ItemActions>
            </Item>
          ))
        )}
      </div>

      <Dialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.agents.delete}</DialogTitle>
            <DialogDescription>{t.agents.deleteConfirm}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              disabled={isDeleting}
            >
              {t.common.cancel}
            </Button>
            <Button
              variant="destructive"
              onClick={handleDeleteConfirm}
              disabled={isDeleting}
            >
              {isDeleting ? t.common.loading : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function EmptyAgents({ onCreateAgent }: { onCreateAgent: () => void }) {
  const { t } = useI18n();
  return (
    <Empty>
      <EmptyHeader>
        <EmptyMedia variant="icon">
          <BotIcon />
        </EmptyMedia>
        <EmptyTitle>{t.agents.emptyTitle}</EmptyTitle>
        <EmptyDescription>{t.agents.emptyDescription}</EmptyDescription>
      </EmptyHeader>
      <EmptyContent>
        <Button onClick={onCreateAgent}>{t.agents.newAgent}</Button>
      </EmptyContent>
    </Empty>
  );
}
