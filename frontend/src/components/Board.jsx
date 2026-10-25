import TicketCard from "./TicketCard.jsx";

const COLUMNS = [
  { key: "OPEN", title: "🚨 SOS (Open)", accent: "border-t-wmd-orange" },
  { key: "CLAIMED", title: "🦸 Rescuing", accent: "border-t-wmd-purple" },
  { key: "RESOLVED", title: "☕ Caffeinated (Done)", accent: "border-t-wmd-green" },
];

export default function Board({ tickets, me, refresh }) {
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
      {COLUMNS.map((col) => {
        const items = tickets.filter((t) => t.status === col.key);
        return (
          <section
            key={col.key}
            className={`rounded-2xl border border-wmd-line border-t-4 ${col.accent} bg-black/20 p-3`}
          >
            <h2 className="mb-3 flex items-center justify-between text-sm font-bold">
              {col.title}
              <span className="rounded-full bg-wmd-card px-2 py-0.5 text-xs text-zinc-400">
                {items.length}
              </span>
            </h2>
            <div className="flex flex-col gap-3">
              {items.length === 0 && (
                <p className="py-6 text-center text-xs text-zinc-600">
                  Nothing here yet
                </p>
              )}
              {items.map((t) => (
                <TicketCard key={t.ticket_id} ticket={t} me={me} refresh={refresh} />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
