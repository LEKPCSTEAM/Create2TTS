import { useState } from "react";
import { api } from "../api";
import { AudioInput } from "../ui";
import type { Language, Voice } from "../types";
import { fmtTime, type TabProps } from "./shared";

function AddVoice({ notify, onDone }: Pick<TabProps, "notify"> & { onDone: () => Promise<void> }) {
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [lang, setLang] = useState<Language>("th");
  const [refText, setRefText] = useState("");
  const [busy, setBusy] = useState<"" | "transcribe" | "save">("");

  const form = (withText: boolean) => {
    const f = new FormData();
    f.append("file", file!);
    f.append("language", lang);
    if (withText) {
      f.append("name", name);
      f.append("ref_text", refText);
      f.append("source", file!.name.startsWith("recording.") ? "record" : "upload");
    }
    return f;
  };

  const transcribe = async () => {
    if (!file) return;
    setBusy("transcribe");
    try {
      const r = await api.transcribe(form(false));
      setRefText(r.text);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  const save = async () => {
    if (!file || !name.trim()) return;
    setBusy("save");
    try {
      await api.addVoice(form(true));
      notify("เพิ่มเสียงแล้ว", "ok");
      setFile(null);
      setName("");
      setRefText("");
      await onDone();
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy("");
    }
  };

  return (
    <div className="card">
      <h2>เพิ่มเสียงใหม่</h2>
      <AudioInput onFile={setFile} notify={notify} />
      <p className="muted">ใช้เสียงอ้างอิงยาว 2–15 วินาที พูดชัด ไม่มีเสียงรบกวน</p>
      <div className="row wrap">
        <label className="field grow">
          <span>ชื่อเสียง</span>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label className="field">
          <span>ภาษา</span>
          <select value={lang} onChange={(e) => setLang(e.target.value as Language)}>
            <option value="th">ไทย</option>
            <option value="en">English</option>
          </select>
        </label>
      </div>
      <label className="field">
        <span>ข้อความในเสียงอ้างอิง (เว้นว่างเพื่อถอดอัตโนมัติ)</span>
        <textarea rows={3} value={refText} onChange={(e) => setRefText(e.target.value)} />
      </label>
      <div className="row wrap">
        <button type="button" className="btn ghost" disabled={!file || !!busy} onClick={transcribe}>
          {busy === "transcribe" ? "กำลังถอดเสียง…" : "ถอดข้อความ"}
        </button>
        <button type="button" className="btn primary" disabled={!file || !name.trim() || !!busy} onClick={save}>
          {busy === "save" ? "กำลังบันทึก…" : "บันทึกเสียง"}
        </button>
      </div>
    </div>
  );
}

function VoiceRow({ v, notify, onChanged }: { v: Voice; notify: TabProps["notify"]; onChanged: () => Promise<void> }) {
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState(v.name);
  const [refText, setRefText] = useState(v.ref_text);
  const [lang, setLang] = useState<Language>(v.language);

  const save = async () => {
    try {
      await api.updateVoice(v.id, { name, ref_text: refText, language: lang });
      setEdit(false);
      await onChanged();
    } catch (e) {
      notify((e as Error).message);
    }
  };
  const del = async () => {
    if (!confirm(`ลบเสียง "${v.name}" ?`)) return;
    try {
      await api.deleteVoice(v.id);
      await onChanged();
    } catch (e) {
      notify((e as Error).message);
    }
  };

  return (
    <li className="card voice">
      {edit ? (
        <>
          <label className="field">
            <span>ชื่อ</span>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            <span>ภาษา</span>
            <select value={lang} onChange={(e) => setLang(e.target.value as Language)}>
              <option value="th">ไทย</option>
              <option value="en">English</option>
            </select>
          </label>
          <label className="field">
            <span>ข้อความอ้างอิง</span>
            <textarea rows={3} value={refText} onChange={(e) => setRefText(e.target.value)} />
          </label>
          <div className="row">
            <button type="button" className="btn primary" onClick={save}>
              บันทึก
            </button>
            <button type="button" className="btn ghost" onClick={() => setEdit(false)}>
              ยกเลิก
            </button>
          </div>
        </>
      ) : (
        <>
          <div className="row between wrap">
            <strong>{v.name}</strong>
            <small className="muted">
              {v.language} · {v.duration_s.toFixed(1)} วินาที · {fmtTime(v.created_at)}
            </small>
          </div>
          <p className="ref">{v.ref_text}</p>
          <audio controls preload="none" src={api.voiceAudio(v.id)} />
          <div className="row">
            <button type="button" className="btn ghost" onClick={() => setEdit(true)}>
              แก้ไข
            </button>
            {v.source !== "builtin" && (
              <button type="button" className="btn danger-ghost" onClick={del}>
                ลบ
              </button>
            )}
          </div>
        </>
      )}
    </li>
  );
}

export default function VoicesTab({ voices, notify, reload }: TabProps) {
  return (
    <section className="stack">
      <AddVoice notify={notify} onDone={reload} />
      <h2>คลังเสียง ({voices.length})</h2>
      {voices.length === 0 && <p className="muted">ยังไม่มีเสียง</p>}
      <ul className="list">
        {voices.map((v) => (
          <VoiceRow key={v.id} v={v} notify={notify} onChanged={reload} />
        ))}
      </ul>
    </section>
  );
}
