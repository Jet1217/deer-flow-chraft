"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Settings2Icon } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Toaster } from "sonner";

import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import { ArtifactsProvider } from "@/components/workspace/artifacts";
import { ChatPageContent } from "@/components/workspace/chats";
import { SettingsDialog } from "@/components/workspace/settings";
import { Button } from "@/components/ui/button";
import { SubtasksProvider } from "@/core/tasks/context";

const queryClient = new QueryClient();

function LandingPage() {
  const router = useRouter();
  const [settingsOpen, setSettingsOpen] = useState(false);

  return (
    <div className="relative flex h-screen w-full flex-col overflow-hidden">
      {/* Top bar */}
      <header className="absolute top-0 right-0 left-0 z-40 flex h-12 items-center justify-between px-4">
        {/* Brand */}
        <div
          className="cursor-pointer font-serif text-lg font-semibold text-foreground"
          onClick={() => router.push("/")}
        >
          FlowEngine
        </div>

        {/* Settings button */}
        <Button
          variant="ghost"
          size="icon"
          className="text-muted-foreground"
          onClick={() => setSettingsOpen(true)}
        >
          <Settings2Icon className="size-4" />
        </Button>
      </header>

      {/* Chat input — full screen, centered via ChatPageContent new-thread mode */}
      <SubtasksProvider>
        <ArtifactsProvider>
          <PromptInputProvider>
            <ChatPageContent threadId={null} />
          </PromptInputProvider>
        </ArtifactsProvider>
      </SubtasksProvider>

      {/* Settings dialog */}
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        defaultSection="appearance"
      />

      <Toaster position="top-center" />
    </div>
  );
}

export default function HomePage() {
  return (
    <QueryClientProvider client={queryClient}>
      <LandingPage />
    </QueryClientProvider>
  );
}
