import { useState } from "react";
import { api } from "../api.js";
import { useSpeech } from "../useSpeech.js";

const EXAMPLE =
  "I'm stuck on a CORS error, sitting by the window. Offering a cold coffee.";

export default function SOSForm({ name, onPosted }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const { supported, listening, start, stop } = useSpeech(setText);

  async function submit() {
    setError("");
    if (!name.trim()) return setError("Enter your name (top right) first.");
    if (!text.trim()) return setError("Say or type your SOS first.");
    setBusy(true);
    try {
      if (listening) stop();
      await api.create(name.trim(), text.trim());
      setText("");
      onPosted();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-2xl border border-wmd-line bg-wmd-card p-4 shadow-xl">
      <div className="flex flex-col gap-4 md:flex-row md:items-stretch">
        <button
          type="button"
          onClick={listening ? stop : start}
          disabled={!supported}
          title={
            supported
              ? "Tap to speak"
              : "Speech API not available in this browser - use Wispr Flow in the text box"
          }
          className={`grid h-24 w-24 shrink-0 place-items-center self-center rounded-full text-4xl transition ${
            listening
              ? "bg-red-500 animate-ring"
              : "bg-wmd-orange hover:brightness-110"
          } disabled:cursor-not-allowed disabled:opacity-40`}
        >
          {listening ? "⏹" : "🎙️"}
        </button>

        <div className="flex flex-1 flex-col gap-2">
          <label className="text-sm font-semibold text-zinc-300">
            Declare your bug, location & bounty
            <span className="ml-2 font-normal text-zinc-500">
              {listening
                ? "Listening…"
                : "Tap the mic, or use Wispr Flow in this box"}
            </span>
          </label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={3}
            maxLength={600}
            placeholder={EXAMPLE}
            className="w-full flex-1 resize-none rounded-xl border border-wmd-line bg-wmd-bg p-3 text-sm outline-none focus:border-wmd-orange"
          />
          <div className="flex items-center justify-between gap-3">
            <span className="text-xs text-red-400">{error}</span>
            <button
              type="button"
              onClick={submit}
              disabled={busy}
              className="rounded-xl bg-gradient-to-r from-wmd-orange to-wmd-purple px-5 py-2.5 text-sm font-bold shadow-lg transition hover:brightness-110 disabled:opacity-50"
            >
              {busy ? "Posting…" : "🚨 Post SOS"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
