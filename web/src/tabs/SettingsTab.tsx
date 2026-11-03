import { useEffect, useState, type ReactNode } from "react";
import { api } from "../api";
import { EffectSliders, type Notify } from "../ui";
import { NEUTRAL, type EngineConfig, type Preset, type Settings, type WorkerStatus } from "../types";

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="card">
      <legend>{title}</legend>
      {children}
    </fieldset>
  );
}

function Num(p: { label: string; value: number; min: number; max: number; step?: number; hint?: string; onChange: (v: number) => void }) {
  return (
    <label className="field">
      <span>
        {p.label} <small className="muted">({p.min}–{p.max})</small>
      </span>
      <input type="number" value={p.value} min={p.min} max={p.max} step={p.step ?? 1} onChange={(e) => p.onChange(Number(e.target.value))} />
      {p.hint && <small className="muted">{p.hint}</small>}
    </label>
  );
}

function Txt(p: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="field">
      <span>{p.label}</span>
      <input value={p.value} onChange={(e) => p.onChange(e.target.value)} />
    </label>
  );
}

function StatusPanel({ status, notify }: { status: WorkerStatus | null; notify: Notify }) {
  const act = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      notify(ok, "ok");
    } catch (e) {
      notify((e as Error).message);
    }
  };
  return (
    <Group title="สถานะ worker">
      {status ? (
        <dl className="kv">
          <dt>อุปกรณ์</dt>
          <dd>{status.device}</dd>
          <dt>โมเดลที่โหลดอยู่</dt>
          <dd>{status.loaded_engines.length ? status.loaded_engines.join(", ") : "ไม่มี"}</dd>
          <dt>สถานะ</dt>
          <dd>{status.busy ? "กำลังทำงาน" : "ว่าง"}</dd>
          <dt>ว่างมาแล้ว</dt>
          <dd>
            {Math.round(status.idle_s)} วินาที (ปิดเมื่อครบ {status.idle_timeout_min} นาที)
          </dd>
          <dt>เวอร์ชัน / PID</dt>
          <dd>
            {status.version} / {status.pid}
          </dd>
        </dl>
      ) : (
        <p className="muted">worker ไม่ตอบสนอง</p>
      )}
      <div className="row wrap">
        <button type="button" className="btn ghost" disabled={!status} onClick={() => act(api.unload, "ปล่อยหน่วยความจำแล้ว")}>
          ปล่อยหน่วยความจำ
        </button>
        <button
          type="button"
          className="btn danger-ghost"
          disabled={!status}
          onClick={() => confirm("ปิด worker ?") && act(api.shutdown, "กำลังปิด worker")}
        >
          ปิด worker
        </button>
      </div>
    </Group>
  );
}

function PresetManager({ presets, notify, onChanged }: { presets: Record<string, Preset>; notify: Notify; onChanged: () => Promise<void> }) {
  const [draft, setDraft] = useState<Preset | null>(null);
  const [isNew, setIsNew] = useState(false);

  const save = async () => {
    if (!draft) return;
    try {
      await api.putPreset(draft);
      setDraft(null);
      await onChanged();
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const del = async (name: string) => {
    if (!confirm(`ลบพรีเซ็ต "${name}" ?`)) return;
    try {
      await api.deletePreset(name);
      await onChanged();
    } catch (e) {
      notify((e as Error).message);
    }
  };

  return (
    <Group title="พรีเซ็ต">
      <ul className="list tight">
        {Object.values(presets).map((p) => (
          <li key={p.name} className="row between">
            <span>
              {p.label} <small className="muted">{p.name}</small>
            </span>
            <span className="row">
              <button
                type="button"
                className="btn ghost sm"
                onClick={() => {
                  setDraft(structuredClone(p));
                  setIsNew(false);
                }}
              >
                แก้ไข
              </button>
              {p.name !== "neutral" && (
                <button type="button" className="btn danger-ghost sm" onClick={() => del(p.name)}>
                  ลบ
                </button>
              )}
            </span>
          </li>
        ))}
      </ul>
      {draft ? (
        <div className="subcard">
          <Txt label="รหัส (a-z 0-9 _ -)" value={draft.name} onChange={(v) => isNew && setDraft({ ...draft, name: v })} />
          <Txt label="ชื่อที่แสดง" value={draft.label} onChange={(v) => setDraft({ ...draft, label: v })} />
          <EffectSliders value={draft.effects} onChange={(effects) => setDraft({ ...draft, effects })} />
          <div className="row">
            <button type="button" className="btn primary" disabled={!draft.name || !draft.label} onClick={save}>
              บันทึกพรีเซ็ต
            </button>
            <button type="button" className="btn ghost" onClick={() => setDraft(null)}>
              ยกเลิก
            </button>
          </div>
        </div>
      ) : (
        <button
          type="button"
          className="btn ghost"
          onClick={() => {
            setDraft({ name: "", label: "", effects: { ...NEUTRAL } });
            setIsNew(true);
          }}
        >
          + เพิ่มพรีเซ็ต
        </button>
      )}
    </Group>
  );
}

export default function SettingsTab({ notify, status, onSaved }: { notify: Notify; status: WorkerStatus | null; onSaved: () => Promise<void> }) {
  const [s, setS] = useState<Settings | null>(null);
  const [orig, setOrig] = useState<Settings | null>(null);
  const [voices, setVoices] = useState<{ id: string; name: string }[]>([]);
  const [enginesText, setEnginesText] = useState("");
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const [cfg, v] = await Promise.all([api.settings(), api.voices()]);
      setS(cfg);
      setOrig(cfg);
      setVoices(v);
      setEnginesText(JSON.stringify(cfg.engines, null, 2));
    } catch (e) {
      notify((e as Error).message);
    }
  };
  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!s || !orig) return <p className="muted">กำลังโหลด…</p>;
  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS({ ...s, [k]: v });
  const netChanged = s.host !== orig.host || s.port !== orig.port;
  const engineIds = Object.keys(s.engines);

  const save = async () => {
    let engines: Record<string, EngineConfig>;
    try {
      engines = JSON.parse(enginesText);
    } catch {
      notify("JSON ของ engines ไม่ถูกต้อง");
      return;
    }
    setSaving(true);
    try {
      const r = await api.saveSettings({ ...s, engines });
      setS(r.settings);
      setOrig(r.settings);
      setEnginesText(JSON.stringify(r.settings.engines, null, 2));
      notify(r.restart ? "บันทึกแล้ว ต้องรีสตาร์ท worker เพื่อใช้ host/port ใหม่" : "บันทึกการตั้งค่าแล้ว", "ok");
      await onSaved();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="stack">
      <StatusPanel status={status} notify={notify} />

      <Group title="เซิร์ฟเวอร์">
        <Txt label="Host" value={s.host} onChange={(v) => set("host", v)} />
        <Num label="Port" value={s.port} min={1024} max={65535} onChange={(v) => set("port", v)} />
        {netChanged && <p className="note">ต้องรีสตาร์ท worker จึงจะมีผล</p>}
      </Group>

      <Group title="โมเดล">
        <label className="field">
          <span>อุปกรณ์ (device)</span>
          <select value={s.device} onChange={(e) => set("device", e.target.value as Settings["device"])}>
            <option value="auto">auto</option>
            <option value="mps">mps</option>
            <option value="cpu">cpu</option>
          </select>
        </label>
        <label className="field">
          <span>engine ภาษาไทย</span>
          <select value={s.engine_th} onChange={(e) => set("engine_th", e.target.value)}>
            {engineIds.map((id) => (
              <option key={id}>{id}</option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>engine ภาษาอังกฤษ</span>
          <select value={s.engine_en} onChange={(e) => set("engine_en", e.target.value)}>
            {engineIds.map((id) => (
              <option key={id}>{id}</option>
            ))}
          </select>
        </label>
        <Num label="nfe_step" value={s.nfe_step} min={8} max={64} onChange={(v) => set("nfe_step", v)} />
        <Num label="cfg_strength" value={s.cfg_strength} min={0.5} max={5} step={0.1} onChange={(v) => set("cfg_strength", v)} />
        <Txt label="ASR model (อังกฤษ)" value={s.asr_model} onChange={(v) => set("asr_model", v)} />
        <Txt label="ASR model (ไทย)" value={s.asr_model_th} onChange={(v) => set("asr_model_th", v)} />
        <Num
          label="idle_timeout_min (นาที)"
          value={s.idle_timeout_min}
          min={0}
          max={240}
          step={0.5}
          hint="0 = ปิดทันทีหลังเสร็จงาน"
          onChange={(v) => set("idle_timeout_min", v)}
        />
      </Group>

      <Group title="เอาต์พุต">
        <label className="field">
          <span>ฟอร์แมตไฟล์</span>
          <select value={s.output_format} onChange={(e) => set("output_format", e.target.value as Settings["output_format"])}>
            <option value="wav">wav</option>
            <option value="mp3">mp3</option>
          </select>
        </label>
        <label className="field">
          <span>เสียงเริ่มต้น</span>
          <select value={s.default_voice ?? ""} onChange={(e) => set("default_voice", e.target.value || null)}>
            <option value="">(ไม่กำหนด)</option>
            {voices.map((v) => (
              <option key={v.id} value={v.id}>
                {v.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>พรีเซ็ตเริ่มต้น</span>
          <select value={s.default_preset} onChange={(e) => set("default_preset", e.target.value)}>
            {Object.values(s.presets).map((p) => (
              <option key={p.name} value={p.name}>
                {p.label}
              </option>
            ))}
          </select>
        </label>
        <Num label="chunk_gap_ms" value={s.chunk_gap_ms} min={0} max={1000} onChange={(v) => set("chunk_gap_ms", v)} />
        <Num label="max_segment_chars" value={s.max_segment_chars} min={40} max={500} onChange={(v) => set("max_segment_chars", v)} />
      </Group>

      <Group title="ขั้นสูง">
        <label className="field">
          <span>engines (JSON)</span>
          <textarea className="mono" rows={10} value={enginesText} onChange={(e) => setEnginesText(e.target.value)} spellCheck={false} />
        </label>
      </Group>

      <button type="button" className="btn primary big" disabled={saving} onClick={save}>
        {saving ? "กำลังบันทึก…" : "บันทึกการตั้งค่า"}
      </button>

      <PresetManager
        presets={s.presets}
        notify={notify}
        onChanged={async () => {
          await load();
          await onSaved();
        }}
      />
    </section>
  );
}
