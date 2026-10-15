// M1-P06: records the microphone and gives back a 16 kHz mono WAV, which is what the server takes. Reshaped from the
// earlier product's js/voice.js (recordWav, toWav): a recording stops only when the person stops it or the maximum is
// reached, never on a pause in speech. The audio lives in memory only; nothing here saves it.

interface AudioWindow {
  AudioContext?: typeof AudioContext;
  webkitAudioContext?: typeof AudioContext;
}
const audioContext = (): typeof AudioContext => {
  const w = window as unknown as AudioWindow;
  const ctor = w.AudioContext ?? w.webkitAudioContext;
  if (!ctor) throw new Error("no-audio");
  return ctor;
};

const TARGET_RATE = 16000;
const SLICE_MS = 1000; // the recorder hands over a chunk every second so a long answer never sits in one buffer

/** Decodes the recording and re-encodes it as 16 kHz mono 16-bit PCM WAV. */
export async function toWav(blob: Blob): Promise<Blob> {
  const decodeCtx = new (audioContext())();
  try {
    const decoded = await decodeCtx.decodeAudioData(await blob.arrayBuffer());
    const offline = new OfflineAudioContext(1, Math.ceil(decoded.duration * TARGET_RATE), TARGET_RATE);
    const src = offline.createBufferSource();
    src.buffer = decoded; // the offline context mixes any number of channels down to the one it has
    src.connect(offline.destination);
    src.start();
    const pcm = (await offline.startRendering()).getChannelData(0);
    const buffer = new ArrayBuffer(44 + pcm.length * 2);
    const view = new DataView(buffer);
    const text = (at: number, s: string) => [...s].forEach((ch, i) => view.setUint8(at + i, ch.charCodeAt(0)));
    text(0, "RIFF");
    view.setUint32(4, 36 + pcm.length * 2, true);
    text(8, "WAVEfmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); // PCM
    view.setUint16(22, 1, true); // mono
    view.setUint32(24, TARGET_RATE, true);
    view.setUint32(28, TARGET_RATE * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    text(36, "data");
    view.setUint32(40, pcm.length * 2, true);
    pcm.forEach((v, i) => view.setInt16(44 + i * 2, Math.max(-1, Math.min(1, v)) * (v < 0 ? 0x8000 : 0x7fff), true));
    return new Blob([buffer], { type: "audio/wav" });
  } finally {
    void decodeCtx.close().catch(() => undefined);
  }
}

/**
 * Records until `signal` aborts or `maxMs` passes, then resolves the WAV. `onLevel` gets 0 to 1 while sound arrives, so
 * the screen can show the microphone is hearing something. Rejects when the microphone cannot be used.
 */
export function recordWav(opts: { signal: AbortSignal; maxMs: number; onLevel?: (level: number) => void }): Promise<Blob> {
  return new Promise<Blob>((resolve, reject) => {
    if (!navigator.mediaDevices?.getUserMedia) {
      reject(new Error("no-microphone"));
      return;
    }
    navigator.mediaDevices.getUserMedia({ audio: true }).then((stream) => {
      const ctx = new (audioContext())();
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const data = new Uint8Array(analyser.frequencyBinCount);
      let frame = 0;
      const tick = () => {
        analyser.getByteTimeDomainData(data);
        const rms = Math.sqrt(data.reduce((sum, v) => sum + ((v - 128) / 128) ** 2, 0) / data.length);
        opts.onLevel?.(Math.min(1, rms * 4));
        frame = requestAnimationFrame(tick);
      };
      tick();
      const release = () => {
        cancelAnimationFrame(frame);
        clearTimeout(timer);
        stream.getTracks().forEach((t) => t.stop());
        void ctx.close().catch(() => undefined);
      };
      const chunks: Blob[] = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => {
        if (e.data.size) chunks.push(e.data);
      };
      recorder.onerror = () => {
        release();
        reject(new Error("recorder-error"));
      };
      recorder.onstop = () => {
        release();
        toWav(new Blob(chunks, { type: recorder.mimeType || "audio/webm" })).then(resolve, reject);
      };
      const stop = () => {
        if (recorder.state !== "inactive") recorder.stop();
      };
      const timer = setTimeout(stop, opts.maxMs);
      opts.signal.addEventListener("abort", stop, { once: true });
      recorder.start(SLICE_MS);
    }, reject);
  });
}
