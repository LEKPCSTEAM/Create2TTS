import { useCallback, useRef, useState } from "react";

export function useRecorder(onComplete: (blob: Blob) => void, onError: (msg: string) => void) {
  const [recording, setRecording] = useState(false);
  const recRef = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);

  const start = useCallback(async () => {
    if (recRef.current) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      onError("เบราว์เซอร์นี้อัดเสียงไม่ได้ ให้เปิดผ่าน http://localhost");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      onError("เข้าถึงไมโครโฟนไม่ได้: " + (e as Error).message);
      return;
    }
    const rec = new MediaRecorder(stream);
    chunks.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size) chunks.current.push(e.data);
    };
    rec.onstop = () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunks.current, { type: rec.mimeType || "audio/webm" });
      recRef.current = null;
      setRecording(false);
      if (blob.size > 0) onComplete(blob);
    };
    rec.start();
    recRef.current = rec;
    setRecording(true);
  }, [onComplete, onError]);

  const stop = useCallback(() => recRef.current?.stop(), []);

  return { recording, start, stop };
}
