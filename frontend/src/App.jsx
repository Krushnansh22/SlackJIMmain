import { useCallback, useEffect, useState } from "react";
import { api } from "./api.js";
import Header from "./components/Header.jsx";
import SOSForm from "./components/SOSForm.jsx";
import Board from "./components/Board.jsx";

const POLL_MS = 3000;

export default function App() {
  const [name, setName] = useState(() => localStorage.getItem("mauji_name") || "");
  const [tickets, setTickets] = useState([]);
  const [online, setOnline] = useState(true);

  useEffect(() => {
    localStorage.setItem("mauji_name", name);
  }, [name]);

  const refresh = useCallback(async () => {
    try {
      setTickets(await api.list());
      setOnline(true);
    } catch {
      setOnline(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return (
    <div className="min-h-screen">
      <Header name={name} setName={setName} online={online} />
      <main className="mx-auto flex max-w-7xl flex-col gap-5 px-4 py-5">
        <SOSForm name={name} onPosted={refresh} />
        <Board tickets={tickets} me={name} refresh={refresh} />
        <footer className="py-4 text-center text-xs text-zinc-500">
          Built with ❤️ for the community · Wispr Flow × Temporal × WeMakeDevs
        </footer>
      </main>
    </div>
  );
}
