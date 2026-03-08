"use client";

import { BotIcon, PlusIcon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useAgents } from "@/core/agents";
import { useI18n } from "@/core/i18n/hooks";

import { AgentCard } from "./agent-card";

export function AgentGallery() {
  const { t } = useI18n();
  const { agents, isLoading } = useAgents();
  const router = useRouter();
  const [tab, setTab] = useState<"builtin" | "custom">("builtin");

  const handleNewAgent = () => {
    router.push("/workspace/agents/new");
  };

  const builtinAgents = agents.filter((a) => a.builtin);
  const customAgents = agents.filter((a) => !a.builtin);
  const displayedAgents = tab === "builtin" ? builtinAgents : customAgents;

  return (
    <div className="flex size-full flex-col">
      {/* Page header */}
      <div className="flex items-center justify-between border-b px-6 py-4">
        <div>
          <h1 className="text-xl font-semibold">{t.agents.title}</h1>
          <p className="text-muted-foreground mt-0.5 text-sm">
            {t.agents.description}
          </p>
        </div>
        <Button onClick={handleNewAgent}>
          <PlusIcon className="mr-1.5 h-4 w-4" />
          {t.agents.newAgent}
        </Button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="text-muted-foreground flex h-40 items-center justify-center text-sm">
            {t.common.loading}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <Tabs
              value={tab}
              onValueChange={(v) => setTab(v as "builtin" | "custom")}
            >
              <TabsList variant="line">
                <TabsTrigger value="builtin">
                  {t.agents.builtinSection}
                </TabsTrigger>
                <TabsTrigger value="custom">
                  {t.agents.customSection}
                </TabsTrigger>
              </TabsList>
            </Tabs>

            {tab === "custom" && customAgents.length === 0 ? (
              <div className="flex h-48 flex-col items-center justify-center gap-3 text-center">
                <div className="bg-muted flex h-14 w-14 items-center justify-center rounded-full">
                  <BotIcon className="text-muted-foreground h-7 w-7" />
                </div>
                <div>
                  <p className="font-medium">{t.agents.emptyTitle}</p>
                  <p className="text-muted-foreground mt-1 text-sm">
                    {t.agents.emptyDescription}
                  </p>
                </div>
                <Button
                  variant="outline"
                  className="mt-2"
                  onClick={handleNewAgent}
                >
                  <PlusIcon className="mr-1.5 h-4 w-4" />
                  {t.agents.newAgent}
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {displayedAgents.map((agent) => (
                  <AgentCard key={agent.name} agent={agent} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
