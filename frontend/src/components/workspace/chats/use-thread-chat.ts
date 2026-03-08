"use client";

import { useParams, usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { uuid } from "@/core/utils/uuid";

export function useThreadChat() {
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const initialQuery = threadIdFromPath === "new"
    ? (searchParams.get("q") ?? undefined)
    : undefined;

  // Initialize with threadIdFromPath to keep SSR and client hydration in sync.
  // For "new" threads, uuid() is generated client-side only via useEffect.
  const [threadId, setThreadId] = useState(threadIdFromPath);

  // If there's an initial query, skip the welcome state and go straight into chat.
  const [isNewThread, setIsNewThread] = useState(
    () => threadIdFromPath === "new" && !initialQuery,
  );

  // Generate the actual UUID for new threads on the client side only,
  // after hydration, to avoid SSR/client mismatch.
  useEffect(() => {
    if (threadIdFromPath === "new") {
      setThreadId(uuid());
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (pathname.endsWith("/new")) {
      setIsNewThread(true);
      setThreadId(uuid());
    }
  }, [pathname]);

  const isMock = searchParams.get("mock") === "true";

  return { threadId, setThreadId, isNewThread, setIsNewThread, isMock, initialQuery };
}
