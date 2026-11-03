import type {
  Preset,
  Settings,
  SynthRequest,
  SynthResult,
  TranscribeResult,
  Voice,
  VoiceUpdate,
  WorkerStatus,
} from "./types";

async function fail(res: Response): Promise<never> {
  let msg = `${res.status} ${res.statusText}`;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") msg = body.detail;
    else if (Array.isArray(body.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join("; ");
  } catch {
    /* non-JSON error body */
  }
  throw new Error(msg);
}

async function call<T>(path: string, init?: RequestInit): Promise<{ data: T; res: Response }> {
  let res: Response;
  try {
    res = await fetch(path, init);
  } catch {
    throw new Error("เชื่อมต่อ worker ไม่ได้");
  }
  if (!res.ok) return fail(res);
  const data = (res.status === 204 || res.status === 202 ? undefined : await res.json().catch(() => undefined)) as T;
  return { data, res };
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  status: () => call<WorkerStatus>("/api/status").then((r) => r.data),
  heartbeat: () => call<void>("/api/heartbeat", { method: "POST" }),
  unload: () => call<void>("/api/models/unload", { method: "POST" }),
  shutdown: () => call<void>("/api/shutdown", { method: "POST" }),

  voices: () => call<Voice[]>("/api/voices").then((r) => r.data),
  addVoice: (form: FormData) => call<Voice>("/api/voices", { method: "POST", body: form }).then((r) => r.data),
  updateVoice: (id: string, body: VoiceUpdate) =>
    call<Voice>(`/api/voices/${id}`, json("PATCH", body)).then((r) => r.data),
  deleteVoice: (id: string) => call<void>(`/api/voices/${id}`, { method: "DELETE" }),
  voiceAudio: (id: string) => `/api/voices/${id}/audio`,

  transcribe: (form: FormData) =>
    call<TranscribeResult>("/api/transcribe", { method: "POST", body: form }).then((r) => r.data),
  synthesize: (req: SynthRequest) => call<SynthResult>("/api/synthesize", json("POST", req)).then((r) => r.data),
  convert: (form: FormData) => call<SynthResult>("/api/convert", { method: "POST", body: form }).then((r) => r.data),

  outputs: (limit = 100) => call<SynthResult[]>(`/api/outputs?limit=${limit}`).then((r) => r.data),
  deleteOutput: (file: string) => call<void>(`/api/outputs/${file}`, { method: "DELETE" }),
  deleteOutputs: (files: string[]) =>
    call<{ deleted: number }>("/api/outputs/delete", json("POST", { files })).then((r) => r.data),
  clearOutputs: () => call<{ deleted: number }>("/api/outputs", { method: "DELETE" }).then((r) => r.data),

  presets: () => call<Preset[]>("/api/presets").then((r) => r.data),
  putPreset: (p: Preset) => call<Preset>(`/api/presets/${p.name}`, json("PUT", p)).then((r) => r.data),
  deletePreset: (name: string) => call<void>(`/api/presets/${name}`, { method: "DELETE" }),

  settings: () => call<Settings>("/api/settings").then((r) => r.data),
  saveSettings: (s: Settings) =>
    call<Settings>("/api/settings", json("PUT", s)).then((r) => ({
      settings: r.data,
      restart: r.res.headers.get("X-Restart-Required") === "1",
    })),
};
