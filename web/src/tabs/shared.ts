import type { Notify } from "../ui";
import type { Preset, Voice } from "../types";

export interface TabProps {
  voices: Voice[];
  presets: Preset[];
  defaults: { voice: string; preset: string };
  notify: Notify;
  reload: () => Promise<void>;
  engineLoaded: boolean;
}

export function fmtTime(iso: string): string {
  return new Date(iso).toLocaleString("th-TH", { dateStyle: "medium", timeStyle: "short" });
}
