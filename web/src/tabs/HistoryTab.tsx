import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Notify } from "../ui";
import type { SynthResult } from "../types";
import { fmtTime } from "./shared";

export default function HistoryTab({ notify }: { notify: Notify }) {
  const [items, setItems] = useState<SynthResult[] | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [deleting, setDeleting] = useState(false);
  const allRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.outputs(100);
      setItems(list);
      setPicked((prev) => new Set(list.filter((r) => prev.has(r.file)).map((r) => r.file)));
    } catch (e) {
      notify((e as Error).message);
    }
  }, [notify]);

  useEffect(() => {
    void load();
  }, [load]);

  const count = picked.size;
  const total = items?.length ?? 0;

  useEffect(() => {
    if (allRef.current) allRef.current.indeterminate = count > 0 && count < total;
  }, [count, total]);

  const run = async (task: () => Promise<void>) => {
    setDeleting(true);
    try {
      await task();
      await load();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setDeleting(false);
    }
  };

  const del = (r: SynthResult) => {
    if (!confirm("ลบไฟล์นี้?")) return;
    void run(async () => {
      await api.deleteOutput(r.file);
    });
  };

  const delPicked = () => {
    if (!confirm(`ลบ ${count} รายการที่เลือก?`)) return;
    void run(async () => {
      const { deleted } = await api.deleteOutputs([...picked]);
      notify(`ลบแล้ว ${deleted} รายการ`, "ok");
    });
  };

  const delAll = () => {
    if (!confirm("ลบประวัติทั้งหมด? กู้คืนไม่ได้")) return;
    void run(async () => {
      const { deleted } = await api.clearOutputs();
      notify(`ลบแล้ว ${deleted} รายการ`, "ok");
    });
  };

  const toggle = (file: string) =>
    setPicked((prev) => {
      const next = new Set(prev);
      if (!next.delete(file)) next.add(file);
      return next;
    });

  const toggleAll = () => setPicked(count === total ? new Set() : new Set(items?.map((r) => r.file)));

  if (!items) return <p className="muted">กำลังโหลด…</p>;
  if (items.length === 0) return <p className="muted">ยังไม่มีประวัติ</p>;
  return (
    <div className="stack">
      <div className="card">
        <div className="row between wrap">
          <label className="row">
            <input ref={allRef} type="checkbox" className="pick" checked={count === total} onChange={toggleAll} />
            {count ? `เลือก ${count} จาก ${total}` : `เลือกทั้งหมด (${total})`}
          </label>
          <div className="row">
            <button type="button" className="btn danger-ghost sm" disabled={!count || deleting} onClick={delPicked}>
              ลบที่เลือก
            </button>
            <button type="button" className="btn danger sm" disabled={deleting} onClick={delAll}>
              ลบทั้งหมด
            </button>
          </div>
        </div>
      </div>
      <ul className="list">
        {items.map((r) => (
          <li key={r.id} className={picked.has(r.file) ? "card picked" : "card"}>
            <div className="row start">
              <input
                type="checkbox"
                className="pick"
                aria-label="เลือกรายการนี้"
                checked={picked.has(r.file)}
                onChange={() => toggle(r.file)}
              />
              <p className="ref grow">{r.text}</p>
            </div>
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
              <button type="button" className="btn danger-ghost" disabled={deleting} onClick={() => del(r)}>
                ลบ
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
