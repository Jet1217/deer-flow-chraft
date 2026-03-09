"use client";

import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import { ArtifactsProvider } from "@/components/workspace/artifacts";
import { ChatPageContent } from "@/components/workspace/chats";
import { SubtasksProvider } from "@/core/tasks/context";

export default function WorkspaceHomePage() {
  return (
    <SubtasksProvider>
      <ArtifactsProvider>
        <PromptInputProvider>
          <ChatPageContent threadId={null} />
        </PromptInputProvider>
      </ArtifactsProvider>
    </SubtasksProvider>
  );
}
