"use client";

import { useEffect, useState } from "react";
import { Plus, Search, Trash2, Moon, Sun, ShieldCheck, LogOut } from "lucide-react";
import { api } from "@/lib/api";
import { useTheme } from "@/components/ThemeProvider";

interface Conversation {
  id: string;
  title: string;
  updated_at: string;
}

export function Sidebar({
  activeId,
  onSelect,
  onNew,
  isAdmin,
}: {
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  isAdmin: boolean;
}) {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [query, setQuery] = useState("");
  const { theme, toggle } = useTheme();

  const load = async (q?: string) => {
    try {
      const data = await api.listConversations(q);
      setConversations(data);
    } catch {
      // Silently ignore; user may not be authenticated yet
    }
  };

  useEffect(() => {
    load();
  }, [activeId]);

  useEffect(() => {
    const timeout = setTimeout(() => load(query || undefined), 300);
    return () => clearTimeout(timeout);
  }, [query]);

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    await api.deleteConversation(id);
    load(query || undefined);
    if (id === activeId) onNew();
  };

  const logout = async () => {
    try {
      await api.logout();
    } catch {
      // Best-effort: even if the server call fails (e.g. offline), still
      // clear local tokens so the client-side session ends regardless.
    }
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    window.location.href = "/login";
  };

  return (
    <aside className="flex h-full w-72 flex-col border-r border-[rgb(var(--border))] bg-[rgb(var(--surface))]">
      <div className="p-3">
        <button
          onClick={onNew}
          className="flex w-full items-center gap-2 rounded-lg bg-[rgb(var(--accent))] px-3 py-2 text-sm font-medium text-[rgb(var(--accent-fg))] transition hover:opacity-90"
        >
          <Plus size={16} /> New chat
        </button>
      </div>

      <div className="px-3 pb-2">
        <div className="flex items-center gap-2 rounded-lg border border-[rgb(var(--border))] px-2 py-1.5">
          <Search size={14} className="text-[rgb(var(--text-muted))]" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search conversations"
            className="w-full bg-transparent text-sm outline-none placeholder:text-[rgb(var(--text-muted))]"
          />
        </div>
      </div>

      <div className="scrollbar-thin flex-1 overflow-y-auto px-2">
        {conversations.map((c) => (
          <div
            key={c.id}
            onClick={() => onSelect(c.id)}
            className={`group mb-1 flex cursor-pointer items-center justify-between rounded-lg px-3 py-2 text-sm transition ${
              activeId === c.id ? "bg-[rgb(var(--surface-2))]" : "hover:bg-[rgb(var(--surface-2))]"
            }`}
          >
            <span className="truncate">{c.title}</span>
            <button
              onClick={(e) => handleDelete(e, c.id)}
              className="hidden text-[rgb(var(--text-muted))] hover:text-red-500 group-hover:block"
            >
              <Trash2 size={14} />
            </button>
          </div>
        ))}
        {conversations.length === 0 && (
          <p className="mt-4 px-3 text-xs text-[rgb(var(--text-muted))]">No conversations yet. Start one above.</p>
        )}
      </div>

      <div className="flex items-center justify-between border-t border-[rgb(var(--border))] p-3">
        <button onClick={toggle} className="rounded-lg p-2 hover:bg-[rgb(var(--surface-2))]" title="Toggle theme">
          {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        </button>
        {isAdmin && (
          <a href="/admin" className="rounded-lg p-2 hover:bg-[rgb(var(--surface-2))]" title="Admin dashboard">
            <ShieldCheck size={16} />
          </a>
        )}
        <button onClick={logout} className="rounded-lg p-2 hover:bg-[rgb(var(--surface-2))]" title="Log out">
          <LogOut size={16} />
        </button>
      </div>
    </aside>
  );
}
