import { useEffect, useState } from "react";
import { api } from "../api";
import { Busy, EffectSliders, PresetChips, VoiceSelect } from "../ui";
import { NEUTRAL, type Effects, type SynthResult } from "../types";
import type { TabProps } from "./shared";

export default function GenerateTab({ voices, presets, defaults, notify, reload, engineLoaded }: TabProps) {
  const [text, setText] = useState("");
  const [voice, setVoice] = useState(defaults.voice);
  const [preset, setPreset] = useState<string | null>(defaults.preset);
  const [fx, setFx] = useState<Effects>(NEUTRAL);
  const [seed, setSeed] = useState("");
  const [lock, setLock] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<SynthResult | null>(null);

  useEffect(() => {
    setVoice((v) => v || defaults.voice);
    const p = presets.find((x) => x.name === defaults.preset);
    if (p) {
      setPreset(p.name);
      setFx(p.effects);
    }
  }, [defaults, presets]);

  const generate = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      const r = await api.synthesize({
        text,
        voice: voice || null,
        preset,
        ...fx,
        seed: lock && seed !== "" ? Number(seed) : null,
      });
      setResult(r);
      if (r.seed != null && lock) setSeed(String(r.seed));
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const savePreset = async () => {
    const label = prompt("ชื่อพรีเซ็ต (ภาษาไทยหรืออังกฤษ)");
    if (!label) return;
    const name = prompt("รหัสพรีเซ็ต (a-z 0-9 _ -)", label.toLowerCase().replace(/[^a-z0-9_-]+/g, "-").slice(0, 32));
    if (!name) return;
    try {
      await api.putPreset({ name, label, effects: fx });
      notify("บันทึกพรีเซ็ตแล้ว", "ok");
      setPreset(name);
      await reload();
    } catch (e) {
      notify((e as Error).message);
    }
  };

  return (
    <section className="stack">
      <div className="card">
        <label className="field">
          <span>ข้อความ</span>
          <textarea rows={6} value={text} maxLength={5000} onChange={(e) => setText(e.target.value)} placeholder="พิมพ์ข้อความที่ต้องการให้อ่าน" />
          <small className="muted right">{text.length} / 5000</small>
        </label>
        <label className="field">
          <span>เสียง</span>
          <VoiceSelect voices={voices} value={voice} onChange={setVoice} />
        </label>
      </div>

      <div className="card">
        <span className="label">พรีเซ็ต</span>
        <PresetChips
          presets={presets}
          active={preset}
          onPick={(p) => {
            setPreset(p.name);
            setFx(p.effects);
          }}
        />
        <EffectSliders
          value={fx}
          onChange={(e) => {
            setFx(e);
            setPreset(null);
          }}
        />
        <div className="row wrap">
          <label className="field grow">
            <span>Seed</span>
            <input type="number" value={seed} placeholder="สุ่ม" onChange={(e) => setSeed(e.target.value)} />
          </label>
          <label className="check">
            <input type="checkbox" checked={lock} onChange={(e) => setLock(e.target.checked)} />
            ล็อก seed
          </label>
        </div>
        <button type="button" className="btn ghost" onClick={savePreset}>
          บันทึกค่านี้เป็นพรีเซ็ต
        </button>
      </div>

      <button type="button" className="btn primary big" disabled={busy || !text.trim()} onClick={generate}>
        {busy ? "กำลังสร้าง…" : "สร้างเสียง"}
      </button>
      <Busy running={busy} engineLoaded={engineLoaded} label="ผ่านไป" />

      {result && (
        <div className="card">
          <audio controls src={result.url} />
          <div className="row between wrap">
            <small className="muted">
              {result.duration_s.toFixed(1)} วินาที · ใช้เวลา {result.elapsed_s.toFixed(1)} วินาที · seed {result.seed ?? "-"}
            </small>
            <a className="btn ghost" href={result.url} download={result.file}>
              ดาวน์โหลด
            </a>
          </div>
        </div>
      )}
    </section>
  );
}
