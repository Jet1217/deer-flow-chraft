"use client";

import { useParams, usePathname, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

export function useThreadChat() {
  const { thread_id: threadIdFromPath } = useParams<{ thread_id: string }>();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const initialQuery = threadIdFromPath === "new"
    ? (searchParams.get("q") ?? undefined)
    : undefined;

  const [threadId, setThreadId] = useState<string | undefined>(() => {
    return threadIdFromPath === "new" ? undefined : threadIdFromPath;
  });

  // If there's an initial query, skip the welcome state and go straight into chat.
  const [isNewThread, setIsNewThread] = useState(
    () => threadIdFromPath === "new" && !initialQuery,
  );

  useEffect(() => {
    const routeIsNewThread = pathname.endsWith("/new");
    setIsNewThread(routeIsNewThread && !initialQuery);
    setThreadId(routeIsNewThread ? undefined : threadIdFromPath);
  }, [initialQuery, pathname, threadIdFromPath]);

  const isMock = searchParams.get("mock") === "true";

  return { threadId, setThreadId, isNewThread, setIsNewThread, isMock, initialQuery };
}
