export type Language = "th" | "en";
export type AudioFormat = "wav" | "mp3";

export interface Effects {
  speed: number; // 0.5-2.0
  pitch: number; // -6..6 semitones
  softness: number; // 0-100
  warmth: number; // -100..100, negative = brighter
}

export interface Preset {
  name: string; // ^[a-z0-9_-]{1,32}$
  label: string;
  effects: Effects;
}

export interface Voice {
  id: string;
  name: string;
  language: Language;
  ref_text: string;
  duration_s: number;
  created_at: string;
  source: "upload" | "record" | "builtin";
}

export interface VoiceUpdate {
  name?: string | null;
  ref_text?: string | null;
  language?: Language | null;
}

export interface SynthRequest {
  text: string;
  voice?: string | null;
  preset?: string | null;
  speed?: number | null;
  pitch?: number | null;
  softness?: number | null;
  warmth?: number | null;
  seed?: number | null;
  format?: AudioFormat | null;
}

export interface SynthResult {
  id: string;
  file: string;
  path: string;
  url: string;
  duration_s: number;
  sample_rate: number;
  voice: string;
  text: string;
  effects: Effects;
  seed: number | null;
  created_at: string;
  elapsed_s: number;
  transcript?: string | null;
}

export interface TranscribeResult {
  text: string;
  language: Language;
}

export interface WorkerStatus {
  pid: number;
  version: string;
  device: string;
  loaded_engines: string[];
  busy: boolean;
  idle_s: number;
  auto_exit: boolean;
  idle_timeout_min: number;
  web_client: boolean;
}

export interface EngineConfig {
  id: string;
  language: Language;
  arch: string;
  checkpoint: string;
  vocab_file: string;
}

export interface Settings {
  host: string;
  port: number; // 1024-65535
  device: "auto" | "mps" | "cpu";
  idle_timeout_min: number; // 0-240
  engine_th: string;
  engine_en: string;
  engines: Record<string, EngineConfig>;
  nfe_step: number; // 8-64
  cfg_strength: number; // 0.5-5.0
  chunk_gap_ms: number; // 0-1000
  max_segment_chars: number; // 40-500
  output_format: AudioFormat;
  default_voice: string | null;
  default_preset: string;
  asr_model: string;
  asr_model_th: string;
  presets: Record<string, Preset>;
}

export const NEUTRAL: Effects = { speed: 1, pitch: 0, softness: 0, warmth: 0 };
