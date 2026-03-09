"use client";

import { BotIcon, PlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
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
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAgents, useDeleteAgent } from "@/core/agents";
import type { Agent } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

import { SettingsSection } from "./settings-section";

export function AgentSettingsPage({ onClose }: { onClose?: () => void } = {}) {
  const { t } = useI18n();
  const { agents, isLoading, error } = useAgents();
  const router = useRouter();

  const handleNewAgent = () => {
    onClose?.();
    router.push("/workspace/agents/new");
  };

  const handleChat = (agentName: string) => {
    onClose?.();
    router.push(`/workspace/agents/${agentName}/chats/new`);
  };

  return (
    <SettingsSection
      title={t.agents.title}
      description={t.agents.description}
    >
      {isLoading ? (
        <div className="text-muted-foreground text-sm">{t.common.loading}</div>
      ) : error ? (
        <div className="text-destructive text-sm">{(error as Error).message}</div>
      ) : (
        <AgentList agents={agents} onNewAgent={handleNewAgent} onChat={handleChat} />
      )}
    </SettingsSection>
  );
}

function AgentList({
  agents,
  onNewAgent,
  onChat,
}: {
  agents: Agent[];
  onNewAgent: () => void;
  onChat: (name: string) => void;
}) {
  const { t } = useI18n();
  const [filter, setFilter] = useState<"builtin" | "custom">("builtin");

  const filtered = useMemo(
    () => agents.filter((a) => (a.category ?? "custom") === filter),
    [agents, filter],
  );

  return (
    <div className="flex w-full flex-col gap-4">
      <header className="flex items-center justify-between">
        <Tabs
          defaultValue="builtin"
          onValueChange={(v) => setFilter(v as "builtin" | "custom")}
        >
          <TabsList variant="line">
            <TabsTrigger value="builtin">{t.common.builtin}</TabsTrigger>
            <TabsTrigger value="custom">{t.common.custom}</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button size="sm" onClick={onNewAgent}>
          <PlusIcon className="size-4" />
          {t.agents.newAgent}
        </Button>
      </header>

      {filtered.length === 0 ? (
        <EmptyAgents onNewAgent={onNewAgent} />
      ) : (
        <div className="flex flex-col gap-2">
          {filtered.map((agent) => (
            <AgentItem
              key={agent.name}
              agent={agent}
              onChat={() => onChat(agent.name)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function AgentItem({
  agent,
  onChat,
}: {
  agent: Agent;
  onChat: () => void;
}) {
  const { t } = useI18n();
  const deleteAgent = useDeleteAgent();
  const isBuiltin = agent.category === "builtin";
  const [deleteOpen, setDeleteOpen] = useState(false);

  async function handleDelete() {
    try {
      await deleteAgent.mutateAsync(agent.name);
      toast.success(t.agents.deleteSuccess);
      setDeleteOpen(false);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err));
    }
  }

  return (
    <>
      <Item className="w-full" variant="outline">
        <ItemContent>
          <ItemTitle>
            <div className="flex items-center gap-2">
              {agent.name}
              {isBuiltin && (
                <Badge variant="secondary" className="text-xs">
                  {t.common.builtin}
                </Badge>
              )}
              {agent.model && (
                <Badge variant="outline" className="text-xs">
                  {agent.model}
                </Badge>
              )}
            </div>
          </ItemTitle>
          {agent.description && (
            <ItemDescription className="line-clamp-2">
              {agent.description}
            </ItemDescription>
          )}
        </ItemContent>
        <ItemActions>
          <Button size="sm" variant="ghost" onClick={onChat}>
            {t.agents.chat}
          </Button>
          {!isBuiltin && (
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive hover:text-destructive"
              onClick={() => setDeleteOpen(true)}
            >
              {t.common.delete}
            </Button>
          )}
        </ItemActions>
      </Item>

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t.agents.delete}</DialogTitle>
            <DialogDescription>{t.agents.deleteConfirm}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteOpen(false)} disabled={deleteAgent.isPending}>
              {t.common.cancel}
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={deleteAgent.isPending}>
              {deleteAgent.isPending ? t.common.loading : t.common.delete}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function EmptyAgents({ onNewAgent }: { onNewAgent: () => void }) {
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
        <Button onClick={onNewAgent}>
          <PlusIcon className="mr-1.5 h-4 w-4" />
          {t.agents.newAgent}
        </Button>
      </EmptyContent>
    </Empty>
  );
}
