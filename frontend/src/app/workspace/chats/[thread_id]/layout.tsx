"use client";

import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import { useSidebar } from "@/components/ui/sidebar";
import { ArtifactsProvider } from "@/components/workspace/artifacts";
import { SubtasksProvider } from "@/core/tasks/context";

function ChatLayoutInner({ children }: { children: React.ReactNode }) {
  const { setOpen: setSidebarOpen } = useSidebar();
  return (
    <SubtasksProvider>
      <ArtifactsProvider onArtifactSelect={() => setSidebarOpen(false)}>
        <PromptInputProvider>{children}</PromptInputProvider>
      </ArtifactsProvider>
    </SubtasksProvider>
  );
}

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <ChatLayoutInner>{children}</ChatLayoutInner>;
}
