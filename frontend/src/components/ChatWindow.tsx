"use client";

import { useEffect, useRef, useState } from "react";
import { Send, Paperclip, Mic, Volume2, Square, X } from "lucide-react";
import { Markdown } from "@/components/Markdown";
import { api } from "@/lib/api";
import { streamChat } from "@/lib/streamChat";
import { useVoice } from "@/hooks/useVoice";

interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  attachment?: string;
}

const MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"];

export function ChatWindow({
  conversationId,
  onConversationCreated,
}: {
  conversationId: string | null;
  onConversationCreated: (id: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [model, setModel] = useState(MODELS[0]);
  const [pendingFile, setPendingFile] = useState<{ id: string; filename: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const voice = useVoice();

  useEffect(() => {
    if (conversationId) {
      api.getMessages(conversationId).then((msgs) =>
        setMessages(msgs.map((m: any) => ({ id: m.id, role: m.role, content: m.content }))),
      );
    } else {
      setMessages([]);
    }
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async () => {
    if ((!input.trim() && !pendingFile) || streaming) return;
    const userText = input;
    const attachmentIds = pendingFile ? [pendingFile.id] : [];
    const attachedFilename = pendingFile?.filename;
    setInput("");
    setPendingFile(null);
    setMessages((prev) => [
      ...prev,
      { id: `tmp-user-${Date.now()}`, role: "user", content: userText, attachment: attachedFilename },
    ]);

    const assistantId = `tmp-assistant-${Date.now()}`;
    setMessages((prev) => [...prev, { id: assistantId, role: "assistant", content: "" }]);
    setStreaming(true);

    let finalConversationId = conversationId;
    let assistantText = "";

    await streamChat(
      { conversation_id: conversationId || undefined, message: userText, model, attachment_ids: attachmentIds },
      {
        onStart: (id) => {
          if (!conversationId) {
            finalConversationId = id;
            onConversationCreated(id);
          }
        },
        onToken: (token) => {
          assistantText += token;
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: assistantText } : m)));
        },
        onDone: () => setStreaming(false),
        onError: (msg) => {
          setMessages((prev) => prev.map((m) => (m.id === assistantId ? { ...m, content: `⚠️ ${msg}` } : m)));
          setStreaming(false);
        },
      },
    );
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const result = await api.uploadFile(file);
      setPendingFile({ id: result.id, filename: result.filename });
    } catch (err: any) {
      alert(err.message);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  return (
    <div className="flex h-full flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-[rgb(var(--border))] px-4 py-2.5">
        <h1 className="text-sm font-semibold">SmileyGPT</h1>
        <select
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="rounded-md border border-[rgb(var(--border))] bg-transparent px-2 py-1 text-xs"
        >
          {MODELS.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </div>

      <div className="scrollbar-thin flex-1 overflow-y-auto px-4 py-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {messages.length === 0 && (
            <div className="mt-20 text-center text-[rgb(var(--text-muted))]">
              <p className="text-lg font-medium">What can I help with today?</p>
            </div>
          )}
          {messages.map((m) => (
            <div key={m.id} className="flex gap-3">
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  m.role === "user" ? "bg-[rgb(var(--surface-2))]" : "bg-[rgb(var(--accent))] text-[rgb(var(--accent-fg))]"
                }`}
              >
                {m.role === "user" ? "U" : "S"}
              </div>
              <div className="flex-1 pt-0.5">
                {m.attachment && (
                  <div className="mb-1 inline-flex items-center gap-1 rounded-md bg-[rgb(var(--surface-2))] px-2 py-1 text-xs text-[rgb(var(--text-muted))]">
                    <Paperclip size={12} /> {m.attachment}
                  </div>
                )}
                {m.content ? (
                  <Markdown content={m.content} />
                ) : (
                  <span className="typing-dot">●</span>
                )}
                {m.role === "assistant" && m.content && (
                  <button
                    onClick={() => voice.speak(m.content)}
                    className="mt-1 text-[rgb(var(--text-muted))] hover:text-[rgb(var(--accent))]"
                    title="Read aloud"
                  >
                    <Volume2 size={14} />
                  </button>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-[rgb(var(--border))] p-4">
        <div className="mx-auto max-w-3xl rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-2">
          {pendingFile && (
            <div className="mb-2 flex items-center gap-2 px-1">
              <span className="inline-flex items-center gap-1 rounded-md bg-[rgb(var(--surface-2))] px-2 py-1 text-xs">
                <Paperclip size={12} /> {pendingFile.filename}
              </span>
              <button onClick={() => setPendingFile(null)} className="text-[rgb(var(--text-muted))] hover:text-red-500">
                <X size={14} />
              </button>
            </div>
          )}
          <div className="flex items-end gap-2">
          <label className="cursor-pointer rounded-lg p-2 hover:bg-[rgb(var(--surface-2))]">
            <Paperclip size={18} />
            <input type="file" className="hidden" onChange={handleFileUpload} />
          </label>

          {voice.supported && (
            <button
              onClick={() => (voice.listening ? voice.stopListening() : voice.startListening(setInput))}
              className={`rounded-lg p-2 hover:bg-[rgb(var(--surface-2))] ${voice.listening ? "text-red-500" : ""}`}
              title="Voice input"
            >
              <Mic size={18} />
            </button>
          )}

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Message SmileyGPT..."
            rows={1}
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-2 text-sm outline-none"
          />

          {streaming ? (
            <button className="rounded-lg bg-[rgb(var(--surface-2))] p-2" disabled>
              <Square size={18} />
            </button>
          ) : (
            <button
              onClick={send}
              disabled={!input.trim() && !pendingFile}
              className="rounded-lg bg-[rgb(var(--accent))] p-2 text-[rgb(var(--accent-fg))] disabled:opacity-40"
            >
              <Send size={18} />
            </button>
          )}
          </div>
        </div>
      </div>
    </div>
  );
}
