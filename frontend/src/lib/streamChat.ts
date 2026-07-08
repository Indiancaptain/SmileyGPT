import { api } from "./api";

interface StreamHandlers {
  onStart?: (conversationId: string) => void;
  onToken: (token: string) => void;
  onDone?: (conversationId: string) => void;
  onError?: (message: string) => void;
}

export async function streamChat(
  payload: { conversation_id?: string; message: string; model?: string; use_memory?: boolean; attachment_ids?: string[] },
  handlers: StreamHandlers,
) {
  const res = await fetch(api.streamChatUrl(), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...api.authHeaders() },
    body: JSON.stringify(payload),
  });

  if (!res.ok || !res.body) {
    const detail = await res.json().catch(() => ({ detail: "Stream failed" }));
    handlers.onError?.(detail.detail || "Stream failed");
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const raw of events) {
      const lines = raw.split("\n");
      const eventLine = lines.find((l) => l.startsWith("event:"));
      const dataLine = lines.find((l) => l.startsWith("data:"));
      if (!eventLine || !dataLine) continue;

      const eventType = eventLine.replace("event:", "").trim();
      const data = JSON.parse(dataLine.replace("data:", "").trim());

      if (eventType === "start") handlers.onStart?.(data.conversation_id);
      if (eventType === "token") handlers.onToken(data.content);
      if (eventType === "done") handlers.onDone?.(data.conversation_id);
    }
  }
}
