import { useCallback, useEffect, useRef, useState } from "react";
import { useRecorder } from "./useRecorder";
import type { Effects, Preset, Voice } from "./types";

export type Notify = (msg: string, kind?: "error" | "ok") => void;

export function useElapsed(running: boolean): number {
  const [s, setS] = useState(0);
  useEffect(() => {
    if (!running) return;
    const t0 = Date.now();
    setS(0);
    const id = setInterval(() => setS((Date.now() - t0) / 1000), 200);
    return () => clearInterval(id);
  }, [running]);
  return s;
}

export function Slider(p: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit?: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="slider">
      <span className="slider-head">
        <span>{p.label}</span>
        <output>
          {p.value}
          {p.unit ?? ""}
        </output>
      </span>
      <input
        type="range"
        min={p.min}
        max={p.max}
        step={p.step}
        value={p.value}
        onChange={(e) => p.onChange(Number(e.target.value))}
      />
    </label>
  );
}

export function EffectSliders({ value, onChange }: { value: Effects; onChange: (e: Effects) => void }) {
  const set = (k: keyof Effects) => (v: number) => onChange({ ...value, [k]: v });
  return (
    <div className="sliders">
      <Slider label="ความเร็ว" value={value.speed} min={0.5} max={2} step={0.05} unit="x" onChange={set("speed")} />
      <Slider label="ระดับเสียง" value={value.pitch} min={-6} max={6} step={0.5} unit=" st" onChange={set("pitch")} />
      <Slider label="ความนุ่ม" value={value.softness} min={0} max={100} step={1} onChange={set("softness")} />
      <Slider label="ความอุ่น" value={value.warmth} min={-100} max={100} step={1} onChange={set("warmth")} />
    </div>
  );
}

export function PresetChips(p: { presets: Preset[]; active: string | null; onPick: (p: Preset) => void }) {
  return (
    <div className="chips" role="group" aria-label="พรีเซ็ต">
      {p.presets.map((x) => (
        <button
          key={x.name}
          type="button"
          className={"chip" + (p.active === x.name ? " on" : "")}
          onClick={() => p.onPick(x)}
        >
          {x.label}
        </button>
      ))}
    </div>
  );
}

export function VoiceSelect(p: { voices: Voice[]; value: string; onChange: (id: string) => void }) {
  return (
    <select value={p.value} onChange={(e) => p.onChange(e.target.value)}>
      <option value="">(เสียงเริ่มต้น)</option>
      {p.voices.map((v) => (
        <option key={v.id} value={v.id}>
          {v.name} · {v.language}
        </option>
      ))}
    </select>
  );
}

export function Busy({ running, engineLoaded, label }: { running: boolean; engineLoaded: boolean; label: string }) {
  const s = useElapsed(running);
  if (!running) return null;
  return (
    <div className="busy" role="status">
      <span className="spinner" />
      <span>
        {label} {s.toFixed(1)} วินาที
        {!engineLoaded && <em> · กำลังโหลดโมเดล… (ครั้งแรกใช้เวลา 15–25 วินาที)</em>}
      </span>
    </div>
  );
}

// Upload-or-record picker; emits a File whenever one is chosen.
export function AudioInput({ onFile, notify }: { onFile: (f: File) => void; notify: Notify }) {
  const [preview, setPreview] = useState<string | null>(null);
  const urlRef = useRef<string | null>(null);

  const take = useCallback(
    (f: File) => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
      urlRef.current = URL.createObjectURL(f);
      setPreview(urlRef.current);
      onFile(f);
    },
    [onFile],
  );
  const onErr = useCallback((m: string) => notify(m), [notify]);
  const rec = useRecorder(
    useCallback(
      (blob: Blob) => {
        const ext = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
        take(new File([blob], `recording.${ext}`, { type: blob.type }));
      },
      [take],
    ),
    onErr,
  );
  useEffect(() => () => {
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
  }, []);

  return (
    <div className="audio-input">
      <div className="row">
        <label className="btn ghost file-btn">
          เลือกไฟล์เสียง
          <input
            type="file"
            accept="audio/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) take(f);
              e.target.value = "";
            }}
          />
        </label>
        <button type="button" className={"btn " + (rec.recording ? "danger" : "ghost")} onClick={rec.recording ? rec.stop : rec.start}>
          {rec.recording ? "■ หยุดอัด" : "● อัดเสียง"}
        </button>
      </div>
      {preview && <audio controls src={preview} />}
    </div>
  );
}
