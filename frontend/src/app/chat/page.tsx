"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/Sidebar";
import { ChatWindow } from "@/components/ChatWindow";
import { api } from "@/lib/api";

export default function ChatPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [isAdmin, setIsAdmin] = useState(false);
  const [ready, setReady] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      router.replace("/login");
      return;
    }
    api
      .me()
      .then((user) => {
        setIsAdmin(user.role === "admin");
        setReady(true);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  if (!ready) return null;

  return (
    <div className="flex h-screen">
      <Sidebar activeId={conversationId} onSelect={setConversationId} onNew={() => setConversationId(null)} isAdmin={isAdmin} />
      <ChatWindow conversationId={conversationId} onConversationCreated={setConversationId} />
    </div>
  );
}
