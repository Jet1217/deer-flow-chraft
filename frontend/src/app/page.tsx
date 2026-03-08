"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ArrowRightIcon, BrainCircuitIcon, CodeIcon, SearchIcon, SettingsIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { Toaster } from "sonner";

import type { PromptInputMessage } from "@/components/ai-elements/prompt-input";
import { PromptInputProvider } from "@/components/ai-elements/prompt-input";
import { ArtifactsProvider } from "@/components/workspace/artifacts";
import { InputBox } from "@/components/workspace/input-box";
import { SettingsDialog, SettingsProvider, useSettings } from "@/components/workspace/settings";
import { useLocalSettings } from "@/core/settings";

const queryClient = new QueryClient();

function ChraftHome() {
  const router = useRouter();
  const [settings, setSettings] = useLocalSettings();
  const { open: settingsOpen, openSettings, closeSettings } = useSettings();

  const handleSubmit = useCallback(
    (message: PromptInputMessage) => {
      const text = (message.text ?? "").trim();
      if (!text) return;
      router.push(`/workspace/chats/new?q=${encodeURIComponent(text)}`);
    },
    [router],
  );

  return (
    <div className="flex min-h-screen flex-col bg-[#F1F2F3] dark:bg-background">
      {/* Top Nav */}
      <nav className="sticky top-0 z-40 flex h-14 items-center justify-between border-b border-[#DCDDE0] dark:border-border bg-white/80 dark:bg-card/80 px-6 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-black dark:bg-white">
            <BrainCircuitIcon className="size-4 text-white dark:text-black" />
          </div>
          <span className="text-[15px] font-semibold tracking-tight text-gray-900 dark:text-foreground">Chraft</span>
        </div>
        <div className="flex items-center gap-3">
          <Link
            href="/workspace/chats"
            className="text-sm text-gray-500 dark:text-muted-foreground transition hover:text-gray-900 dark:hover:text-foreground"
          >
            Recent chats
          </Link>
          <button
            onClick={openSettings}
            className="flex size-8 items-center justify-center rounded-lg text-gray-400 dark:text-muted-foreground transition hover:bg-gray-100 dark:hover:bg-accent hover:text-gray-700 dark:hover:text-foreground"
          >
            <SettingsIcon className="size-4" />
          </button>
        </div>
      </nav>

      {/* Hero */}
      <main className="flex flex-1 flex-col items-center justify-center px-4 pb-24 pt-16">
        {/* Headline */}
        <h1 className="mb-3 max-w-xl text-center text-[2.5rem] font-bold leading-[1.15] tracking-tight text-gray-900 dark:text-foreground">
          Think deeper,<br />work faster with{" "}
          <span className="bg-gradient-to-r from-gray-900 via-gray-700 to-gray-500 dark:from-gray-100 dark:via-gray-300 dark:to-gray-500 bg-clip-text text-transparent">
            Chraft
          </span>
        </h1>

        <p className="mb-10 max-w-md text-center text-[15px] leading-relaxed text-gray-500 dark:text-muted-foreground">
          An intelligent agent that researches, codes, and creates — all from a single conversation.
        </p>

        {/* Chat Input */}
        <div className="w-full max-w-2xl">
          <ArtifactsProvider>
            <PromptInputProvider>
              <InputBox
                className="[&_[role=group]]:bg-white dark:[&_[role=group]]:bg-card [&_[role=group]]:border-[#DCDDE0] dark:[&_[role=group]]:border-border [&_[role=group]]:shadow-sm hover:[&_[role=group]]:border-gray-300 dark:hover:[&_[role=group]]:border-border/60"
                autoFocus
                status="ready"
                context={settings.context}
                onContextChange={(context) => setSettings("context", context)}
                onSubmit={handleSubmit}
              />
            </PromptInputProvider>
          </ArtifactsProvider>
        </div>

        {/* Suggestion chips */}
        <div className="mt-5 flex flex-wrap justify-center gap-2">
          {[
            { icon: SearchIcon, label: "Research a topic" },
            { icon: CodeIcon, label: "Write & run code" },
            { icon: BrainCircuitIcon, label: "Analyze data" },
            { icon: ArrowRightIcon, label: "Plan a project" },
          ].map(({ icon: Icon, label }) => (
            <button
              key={label}
              className="flex items-center gap-1.5 rounded-full border border-[#E4E5E7] dark:border-border/50 bg-white dark:bg-card px-3.5 py-1.5 text-[13px] text-gray-500 dark:text-muted-foreground transition hover:border-gray-300 dark:hover:border-border hover:bg-gray-50 dark:hover:bg-accent hover:text-gray-700 dark:hover:text-foreground"
              onClick={() => {
                router.push(`/workspace/chats/new?q=${encodeURIComponent(label)}`);
              }}
            >
              <Icon className="size-3.5" />
              {label}
            </button>
          ))}
        </div>
      </main>

      {/* Footer */}
      <footer className="flex items-center justify-center gap-6 border-t border-[#DCDDE0] dark:border-border py-4 text-xs text-gray-400 dark:text-muted-foreground">
        <span>© 2025 Chraft</span>
        <a href="mailto:support@chraft.ai" className="transition hover:text-gray-600 dark:hover:text-foreground">
          Feedback
        </a>
      </footer>

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={(v) => { if (!v) closeSettings(); }}
      />
      <Toaster position="top-center" />
    </div>
  );
}

export default function Page() {
  return (
    <QueryClientProvider client={queryClient}>
      <SettingsProvider>
        <ChraftHome />
      </SettingsProvider>
    </QueryClientProvider>
  );
}
