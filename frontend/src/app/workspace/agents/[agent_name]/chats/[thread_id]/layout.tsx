"use client";

import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import { useSidebar } from "@/components/ui/sidebar";
import { ArtifactsProvider } from "@/components/workspace/artifacts";
import { SubtasksProvider } from "@/core/tasks/context";

function AgentChatLayoutInner({ children }: { children: React.ReactNode }) {
  const { setOpen: setSidebarOpen } = useSidebar();
  return (
    <SubtasksProvider>
      <ArtifactsProvider onArtifactSelect={() => setSidebarOpen(false)}>
        <PromptInputProvider>{children}</PromptInputProvider>
      </ArtifactsProvider>
    </SubtasksProvider>
  );
}

export default function AgentChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AgentChatLayoutInner>{children}</AgentChatLayoutInner>;
}
