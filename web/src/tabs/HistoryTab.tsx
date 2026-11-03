import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import type { Notify } from "../ui";
import type { SynthResult } from "../types";
import { fmtTime } from "./shared";

export default function HistoryTab({ notify }: { notify: Notify }) {
  const [items, setItems] = useState<SynthResult[] | null>(null);

  const load = useCallback(async () => {
    try {
      setItems(await api.outputs(100));
    } catch (e) {
      notify((e as Error).message);
    }
  }, [notify]);

  useEffect(() => {
    void load();
  }, [load]);

  const del = async (r: SynthResult) => {
    if (!confirm("ลบไฟล์นี้?")) return;
    try {
      await api.deleteOutput(r.file);
      await load();
    } catch (e) {
      notify((e as Error).message);
    }
  };

  if (!items) return <p className="muted">กำลังโหลด…</p>;
  if (items.length === 0) return <p className="muted">ยังไม่มีประวัติ</p>;
  return (
    <ul className="list">
      {items.map((r) => (
        <li key={r.id} className="card">
          <p className="ref">{r.text}</p>
          <audio controls preload="none" src={r.url} />
          <small className="muted">
            {fmtTime(r.created_at)} · เสียง {r.voice} · {r.duration_s.toFixed(1)} วินาที · seed {r.seed ?? "-"}
            <br />
            ความเร็ว {r.effects.speed} · ระดับ {r.effects.pitch} · นุ่ม {r.effects.softness} · อุ่น {r.effects.warmth}
          </small>
          <div className="row">
            <a className="btn ghost" href={r.url} download={r.file}>
              ดาวน์โหลด
            </a>
            <button type="button" className="btn danger-ghost" onClick={() => del(r)}>
              ลบ
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
