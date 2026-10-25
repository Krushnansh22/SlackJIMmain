export default function Header({ name, setName, online }) {
  return (
    <header className="sticky top-0 z-20 border-b border-wmd-line bg-wmd-bg/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-wmd-orange text-xl shadow-lg shadow-orange-500/20">
            ☕
          </div>
          <div>
            <h1 className="text-lg font-extrabold leading-tight tracking-tight">
              Mauji Cafe <span className="text-wmd-orange">SOS</span> Bribe Board
            </h1>
            <p className="text-xs text-zinc-400">
              Hacktober X · Cloud Native Pune · powered by Temporal
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs ${
              online
                ? "border-green-500/30 text-green-400"
                : "border-red-500/40 text-red-400"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                online ? "bg-green-400" : "bg-red-400 animate-pulse"
              }`}
            />
            {online ? "Live" : "Reconnecting…"}
          </span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={40}
            placeholder="Your name"
            className="w-36 rounded-lg border border-wmd-line bg-wmd-card px-3 py-2 text-sm outline-none focus:border-wmd-orange"
          />
        </div>
      </div>
    </header>
  );
}
