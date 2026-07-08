"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, ShieldOff, Trash2, Ban, CheckCircle2 } from "lucide-react";

interface Stats {
  total_users: number;
  total_conversations: number;
  total_messages: number;
  active_today: number;
}

interface AdminUser {
  id: string;
  email: string;
  role: "user" | "admin";
  is_active: boolean;
  created_at: string;
}

async function authedFetch(path: string, init?: RequestInit) {
  const token = localStorage.getItem("access_token");
  const res = await fetch(`/api/backend${path}`, {
    ...init,
    headers: { ...(init?.headers || {}), Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "Request failed" }));
    throw new Error(body.detail || "Failed to reach admin API (are you an admin?)");
  }
  return res.status === 204 ? null : res.json();
}

export default function AdminPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [currentUserId, setCurrentUserId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");

  const loadUsers = () => authedFetch("/v1/admin/users").then(setUsers).catch((e) => setActionError(e.message));

  useEffect(() => {
    authedFetch("/v1/admin/stats").then(setStats).catch((e) => setError(e.message));
    loadUsers();
    authedFetch("/v1/users/me").then((me) => setCurrentUserId(me.id)).catch(() => {});
  }, []);

  const toggleActive = async (id: string) => {
    setActionError("");
    try {
      await authedFetch(`/v1/admin/users/${id}/toggle-active`, { method: "PATCH" });
      loadUsers();
    } catch (e: any) {
      setActionError(e.message);
    }
  };

  const toggleRole = async (user: AdminUser) => {
    setActionError("");
    const nextRole = user.role === "admin" ? "user" : "admin";
    try {
      await authedFetch(`/v1/admin/users/${user.id}/role`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ role: nextRole }),
      });
      loadUsers();
    } catch (e: any) {
      setActionError(e.message);
    }
  };

  const deleteUser = async (id: string, email: string) => {
    if (!confirm(`Permanently delete ${email}? This removes all of their conversations and files.`)) return;
    setActionError("");
    try {
      await authedFetch(`/v1/admin/users/${id}`, { method: "DELETE" });
      loadUsers();
    } catch (e: any) {
      setActionError(e.message);
    }
  };

  return (
    <div className="min-h-screen bg-[rgb(var(--bg))] p-8">
      <Link href="/chat" className="mb-6 inline-flex items-center gap-2 text-sm text-[rgb(var(--text-muted))]">
        <ArrowLeft size={14} /> Back to chat
      </Link>
      <h1 className="mb-6 text-2xl font-semibold">Admin dashboard</h1>

      {error && <p className="mb-4 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-500">{error}</p>}
      {actionError && <p className="mb-4 rounded-md bg-red-500/10 px-3 py-2 text-sm text-red-500">{actionError}</p>}

      {stats && (
        <div className="mb-8 grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            ["Total users", stats.total_users],
            ["Conversations", stats.total_conversations],
            ["Messages", stats.total_messages],
            ["Active today", stats.active_today],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-xl border border-[rgb(var(--border))] bg-[rgb(var(--surface))] p-4">
              <p className="text-xs text-[rgb(var(--text-muted))]">{label}</p>
              <p className="text-2xl font-semibold">{value as number}</p>
            </div>
          ))}
        </div>
      )}

      <h2 className="mb-3 text-lg font-medium">Users</h2>
      <div className="overflow-hidden rounded-xl border border-[rgb(var(--border))]">
        <table className="w-full text-sm">
          <thead className="bg-[rgb(var(--surface-2))] text-left">
            <tr>
              <th className="px-4 py-2">Email</th>
              <th className="px-4 py-2">Role</th>
              <th className="px-4 py-2">Active</th>
              <th className="px-4 py-2">Joined</th>
              <th className="px-4 py-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isSelf = u.id === currentUserId;
              return (
                <tr key={u.id} className="border-t border-[rgb(var(--border))]">
                  <td className="px-4 py-2">
                    {u.email} {isSelf && <span className="text-xs text-[rgb(var(--text-muted))]">(you)</span>}
                  </td>
                  <td className="px-4 py-2 capitalize">{u.role}</td>
                  <td className="px-4 py-2">{u.is_active ? "Yes" : "No"}</td>
                  <td className="px-4 py-2">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-3">
                      <button
                        onClick={() => toggleRole(u)}
                        disabled={isSelf}
                        title={u.role === "admin" ? "Revoke admin" : "Make admin"}
                        className="text-[rgb(var(--text-muted))] hover:text-[rgb(var(--accent))] disabled:cursor-not-allowed disabled:opacity-30"
                      >
                        {u.role === "admin" ? <ShieldOff size={16} /> : <ShieldCheck size={16} />}
                      </button>
                      <button
                        onClick={() => toggleActive(u.id)}
                        disabled={isSelf}
                        title={u.is_active ? "Deactivate" : "Reactivate"}
                        className="text-[rgb(var(--text-muted))] hover:text-amber-500 disabled:cursor-not-allowed disabled:opacity-30"
                      >
                        {u.is_active ? <Ban size={16} /> : <CheckCircle2 size={16} />}
                      </button>
                      <button
                        onClick={() => deleteUser(u.id, u.email)}
                        disabled={isSelf}
                        title="Delete user"
                        className="text-[rgb(var(--text-muted))] hover:text-red-500 disabled:cursor-not-allowed disabled:opacity-30"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
