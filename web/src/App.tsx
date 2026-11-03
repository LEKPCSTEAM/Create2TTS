import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Notify } from "./ui";
import type { Preset, Voice, WorkerStatus } from "./types";
import GenerateTab from "./tabs/GenerateTab";
import VoicesTab from "./tabs/VoicesTab";
import ConvertTab from "./tabs/ConvertTab";
import HistoryTab from "./tabs/HistoryTab";
import SettingsTab from "./tabs/SettingsTab";

const TABS = ["สร้างเสียง", "คลังเสียง", "แปลงเสียง", "ประวัติ", "ตั้งค่า"] as const;

interface Toast {
  id: number;
  msg: string;
  kind: "error" | "ok";
}

export default function App() {
  const [tab, setTab] = useState(0);
  const [voices, setVoices] = useState<Voice[]>([]);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [defaults, setDefaults] = useState<{ voice: string; preset: string }>({ voice: "", preset: "neutral" });
  const [status, setStatus] = useState<WorkerStatus | null>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const notify: Notify = useCallback((msg, kind = "error") => {
    const id = nextId.current++;
    setToasts((t) => [...t, { id, msg, kind }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 6000);
  }, []);

  const reload = useCallback(async () => {
    try {
      const [v, p, s] = await Promise.all([api.voices(), api.presets(), api.settings()]);
      setVoices(v);
      setPresets(p);
      setDefaults({ voice: s.default_voice ?? "", preset: s.default_preset });
    } catch (e) {
      notify((e as Error).message);
    }
  }, [notify]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    const beat = () => void api.heartbeat().catch(() => undefined);
    beat();
    const id = setInterval(beat, 30_000);
    return () => clearInterval(id);
  }, []);

  useEffect(() => {
    const poll = () => api.status().then(setStatus, () => setStatus(null));
    void poll();
    const id = setInterval(poll, 5_000);
    return () => clearInterval(id);
  }, []);

  const engineLoaded = (status?.loaded_engines.length ?? 0) > 0;
  const shared = { voices, presets, defaults, notify, reload, engineLoaded };

  return (
    <div className="app">
      <header className="top">
        <h1>Create2TTS</h1>
        <span className={"dot " + (status ? "up" : "down")} title={status ? "worker พร้อม" : "worker ไม่ตอบสนอง"} />
      </header>
      <nav className="tabs" role="tablist">
        {TABS.map((t, i) => (
          <button key={t} role="tab" aria-selected={tab === i} className={tab === i ? "on" : ""} onClick={() => setTab(i)}>
            {t}
          </button>
        ))}
      </nav>
      <main>
        {tab === 0 && <GenerateTab {...shared} />}
        {tab === 1 && <VoicesTab {...shared} />}
        {tab === 2 && <ConvertTab {...shared} />}
        {tab === 3 && <HistoryTab notify={notify} />}
        {tab === 4 && <SettingsTab notify={notify} status={status} onSaved={reload} />}
      </main>
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={"toast " + t.kind} onClick={() => setToasts((x) => x.filter((y) => y.id !== t.id))}>
            {t.msg}
          </div>
        ))}
      </div>
    </div>
  );
}
