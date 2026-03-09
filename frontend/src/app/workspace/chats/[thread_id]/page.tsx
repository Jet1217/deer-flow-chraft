"use client";

import { ChatPageContent, useThreadChat } from "@/components/workspace/chats";

export default function ChatPage() {
  const { threadId, isNewThread, isMock } = useThreadChat();

  return (
    <ChatPageContent
      threadId={isNewThread ? null : threadId}
      isMock={isMock}
    />
  );
}
