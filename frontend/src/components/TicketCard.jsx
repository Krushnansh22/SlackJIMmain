import { useState } from "react";
import { api } from "../api.js";

function ago(iso) {
  if (!iso) return "";
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export default function TicketCard({ ticket, me, refresh }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const isMine = me.trim().toLowerCase() === ticket.creator_name.toLowerCase();

  async function act(fn) {
    setError("");
    if (!me.trim()) return setError("Enter your name first.");
    setBusy(true);
    try {
      await fn(ticket.ticket_id, me.trim());
      await refresh();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="animate-pop rounded-xl border border-wmd-line bg-wmd-card p-3.5 shadow-md">
      <div className="mb-2 flex items-center justify-between text-xs text-zinc-400">
        <span className="font-semibold text-zinc-200">
          {ticket.creator_name}
          {isMine && <span className="ml-1 text-wmd-orange">(you)</span>}
        </span>
        <span>{ago(ticket.created_at)}</span>
      </div>
      <p className="text-sm leading-relaxed text-zinc-100">
        {ticket.raw_transcription}
      </p>

      {ticket.claimed_by && (
        <p className="mt-2 text-xs text-purple-300">
          🦸 Rescuer: <b>{ticket.claimed_by}</b>
        </p>
      )}

      {ticket.status === "OPEN" && !isMine && (
        <button
          disabled={busy}
          onClick={() => act(api.claim)}
          className="mt-3 w-full rounded-lg bg-wmd-purple py-2 text-sm font-bold transition hover:brightness-110 disabled:opacity-50"
        >
          🙋 Claim
        </button>
      )}
      {ticket.status === "CLAIMED" && isMine && (
        <button
          disabled={busy}
          onClick={() => act(api.resolve)}
          className="mt-3 w-full rounded-lg bg-wmd-green py-2 text-sm font-bold text-black transition hover:brightness-110 disabled:opacity-50"
        >
          ✅ Resolved - coffee delivered
        </button>
      )}
      {ticket.status === "RESOLVED" && (
        <p className="mt-2 text-xs text-green-400">☕ Bounty paid. Legends.</p>
      )}
      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}
    </article>
  );
}
