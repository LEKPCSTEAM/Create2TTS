import { useState } from "react";
import { api } from "../api";
import { AudioInput, Busy, EffectSliders, PresetChips, VoiceSelect } from "../ui";
import { NEUTRAL, type Effects, type Language, type SynthResult } from "../types";
import type { TabProps } from "./shared";

export default function ConvertTab({ voices, presets, defaults, notify, engineLoaded }: TabProps) {
  const [file, setFile] = useState<File | null>(null);
  const [lang, setLang] = useState<Language>("th");
  const [transcript, setTranscript] = useState("");
  const [voice, setVoice] = useState(defaults.voice);
  const [preset, setPreset] = useState<string | null>(defaults.preset);
  const [fx, setFx] = useState<Effects>(NEUTRAL);
  const [step, setStep] = useState<"" | "transcribe" | "convert" | "synth">("");
  const [result, setResult] = useState<SynthResult | null>(null);

  const transcribe = async () => {
    if (!file) return;
    setStep("transcribe");
    try {
      const f = new FormData();
      f.append("file", file);
      f.append("language", lang);
      setTranscript((await api.transcribe(f)).text);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setStep("");
    }
  };

  const generate = async () => {
    setStep("synth");
    try {
      setResult(await api.synthesize({ text: transcript, voice: voice || null, preset, ...fx }));
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setStep("");
    }
  };

  // One-shot path: transcribe and synthesize on the server without editing.
  const convertDirect = async () => {
    if (!file) return;
    setStep("convert");
    try {
      const f = new FormData();
      f.append("file", file);
      f.append("language", lang);
      f.append("request", JSON.stringify({ voice: voice || null, preset, ...fx }));
      const r = await api.convert(f);
      setResult(r);
      if (r.transcript) setTranscript(r.transcript);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setStep("");
    }
  };

  const running = step !== "";
  return (
    <section className="stack">
      <div className="card">
        <h2>1. เสียงต้นฉบับ</h2>
        <AudioInput onFile={setFile} notify={notify} />
        <label className="field">
          <span>ภาษา</span>
          <select value={lang} onChange={(e) => setLang(e.target.value as Language)}>
            <option value="th">ไทย</option>
            <option value="en">English</option>
          </select>
        </label>
        <button type="button" className="btn ghost" disabled={!file || running} onClick={transcribe}>
          {step === "transcribe" ? "กำลังถอดเสียง…" : "ถอดข้อความ"}
        </button>
        <label className="field">
          <span>ข้อความที่ถอดได้ (แก้ไขได้)</span>
          <textarea rows={5} value={transcript} onChange={(e) => setTranscript(e.target.value)} />
        </label>
      </div>

      <div className="card">
        <h2>2. เสียงและเอฟเฟกต์</h2>
        <label className="field">
          <span>เสียง</span>
          <VoiceSelect voices={voices} value={voice} onChange={setVoice} />
        </label>
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
      </div>

      <div className="row wrap">
        <button type="button" className="btn primary big grow" disabled={running || !transcript.trim()} onClick={generate}>
          สร้างเสียงจากข้อความ
        </button>
        <button type="button" className="btn ghost big" disabled={running || !file} onClick={convertDirect}>
          แปลงทันที
        </button>
      </div>
      <Busy running={step === "synth" || step === "convert"} engineLoaded={engineLoaded} label="ผ่านไป" />

      {result && (
        <div className="card">
          <audio controls src={result.url} />
          <a className="btn ghost" href={result.url} download={result.file}>
            ดาวน์โหลด
          </a>
        </div>
      )}
    </section>
  );
}
