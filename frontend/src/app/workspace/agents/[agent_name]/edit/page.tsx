"use client";

import { ArrowLeftIcon, BotIcon, CheckCircleIcon } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import {
  PromptInput,
  PromptInputFooter,
  PromptInputSubmit,
  PromptInputTextarea,
} from "@/components/ai-elements/prompt-input";
import { Button } from "@/components/ui/button";
import { ArtifactsProvider } from "@/components/workspace/artifacts";
import { MessageList } from "@/components/workspace/messages";
import { ThreadContext } from "@/components/workspace/messages/context";
import type { Agent } from "@/core/agents";
import { getAgent } from "@/core/agents/api";
import { useI18n } from "@/core/i18n/hooks";
import { useThreadStream } from "@/core/threads/hooks";
import { uuid } from "@/core/utils/uuid";

export default function EditAgentPage() {
  const { t } = useI18n();
  const router = useRouter();
  const params = useParams<{ agent_name: string }>();
  const agentName = params.agent_name;

  const [agent, setAgent] = useState<Agent | null>(null);
  const [updatedAgent, setUpdatedAgent] = useState<Agent | null>(null);
  const [isLoadingAgent, setIsLoadingAgent] = useState(true);
  const [loadError, setLoadError] = useState("");

  // Stable thread ID
  const threadId = useMemo(() => uuid(), []);

  const [thread, sendMessage] = useThreadStream({
    threadId: agent ? threadId : undefined,
    context: {
      mode: "flash",
      is_bootstrap: true,
    },
    onToolEnd({ name }) {
      if (name !== "setup_agent" || !agentName) return;
      getAgent(agentName)
        .then((fetched) => setUpdatedAgent(fetched))
        .catch(() => {
          // agent write may not be flushed yet — ignore silently
        });
    },
  });

  // Load existing agent on mount
  useEffect(() => {
    if (!agentName) return;
    setIsLoadingAgent(true);
    getAgent(agentName)
      .then((fetched) => {
        setAgent(fetched);
        setIsLoadingAgent(false);
      })
      .catch(() => {
        setLoadError(`Agent "${agentName}" not found.`);
        setIsLoadingAgent(false);
      });
  }, [agentName]);

  // Auto-send bootstrap message once agent is loaded
  const [bootstrapped, setBootstrapped] = useState(false);
  useEffect(() => {
    if (!agent || bootstrapped) return;
    setBootstrapped(true);
    const soulSection = agent.soul
      ? `\n\nCurrent SOUL:\n${agent.soul}`
      : "";
    const descSection = agent.description
      ? `\n\nCurrent description: ${agent.description}`
      : "";
    void sendMessage(threadId, {
      text: `I want to edit the agent named "${agentName}".${descSection}${soulSection}\n\nPlease help me refine this agent through conversation.`,
      files: [],
    }, { agent_name: agentName });
  }, [agent, bootstrapped, agentName, sendMessage, threadId]);

  const handleChatSubmit = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || thread.isLoading) return;
      await sendMessage(
        threadId,
        { text: trimmed, files: [] },
        { agent_name: agentName },
      );
    },
    [thread.isLoading, sendMessage, threadId, agentName],
  );

  const header = (
    <header className="flex shrink-0 items-center gap-3 border-b px-4 py-3">
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => router.push("/workspace/agents")}
      >
        <ArrowLeftIcon className="h-4 w-4" />
      </Button>
      <h1 className="text-sm font-semibold">
        {t.agents.editPageTitle}
        {agentName && (
          <span className="text-muted-foreground ml-2 font-normal">
            — {agentName}
          </span>
        )}
      </h1>
    </header>
  );

  // Loading state
  if (isLoadingAgent) {
    return (
      <div className="flex size-full flex-col">
        {header}
        <main className="flex flex-1 items-center justify-center">
          <p className="text-muted-foreground text-sm">{t.common.loading}</p>
        </main>
      </div>
    );
  }

  // Error state
  if (loadError || !agent) {
    return (
      <div className="flex size-full flex-col">
        {header}
        <main className="flex flex-1 flex-col items-center justify-center gap-4 px-4">
          <div className="bg-muted flex h-14 w-14 items-center justify-center rounded-full">
            <BotIcon className="text-muted-foreground h-7 w-7" />
          </div>
          <p className="text-destructive text-sm">
            {loadError || "Agent not found."}
          </p>
          <Button
            variant="outline"
            onClick={() => router.push("/workspace/agents")}
          >
            {t.agents.backToGallery}
          </Button>
        </main>
      </div>
    );
  }

  return (
    <ThreadContext.Provider value={{ thread }}>
      <ArtifactsProvider>
        <div className="flex size-full flex-col">
          {header}

          <main className="flex min-h-0 flex-1 flex-col">
            {/* Message area */}
            <div className="flex min-h-0 flex-1 justify-center">
              <MessageList
                className="size-full pt-10"
                threadId={threadId}
                thread={thread}
              />
            </div>

            {/* Bottom action area */}
            <div className="bg-background flex shrink-0 justify-center border-t px-4 py-4">
              <div className="w-full max-w-(--container-width-md)">
                {updatedAgent ? (
                  // Success card
                  <div className="flex flex-col items-center gap-4 rounded-2xl border py-8 text-center">
                    <CheckCircleIcon className="text-primary h-10 w-10" />
                    <p className="font-semibold">{t.agents.agentUpdated}</p>
                    <div className="flex gap-2">
                      <Button
                        onClick={() =>
                          router.push(
                            `/workspace/agents/${agentName}/chats/new`,
                          )
                        }
                      >
                        {t.agents.startChatting}
                      </Button>
                      <Button
                        variant="outline"
                        onClick={() => router.push("/workspace/agents")}
                      >
                        {t.agents.backToGallery}
                      </Button>
                    </div>
                  </div>
                ) : (
                  // Input
                  <PromptInput
                    onSubmit={({ text }) => void handleChatSubmit(text)}
                  >
                    <PromptInputTextarea
                      autoFocus
                      placeholder={t.agents.editPageSubtitle}
                      disabled={thread.isLoading}
                    />
                    <PromptInputFooter className="justify-end">
                      <PromptInputSubmit disabled={thread.isLoading} />
                    </PromptInputFooter>
                  </PromptInput>
                )}
              </div>
            </div>
          </main>
        </div>
      </ArtifactsProvider>
    </ThreadContext.Provider>
  );
}
