// F3 (design board 4): a picture of a paper sketch, read box by box into what is possible today.
import { useEffect, useState } from "react";
import { buildSketch, readSketchFile, readSketchLabels, requestSketch, type BoxStatus, type SketchBox } from "./sketchApi";

const PILL: Record<BoxStatus, { word: string; color: string; border: string }> = {
  possible: { word: "POSSIBLE TODAY", color: "#5FC2C2", border: "#5FC2C2" },
  needs_definition: { word: "NEEDS A DEFINITION", color: "#E0A34A", border: "#E0A34A" },
  not_possible: { word: "NOT POSSIBLE YET", color: "#BFD8D5", border: "#2E4059" },
};
const card = { background: "#16263D", border: "1px solid #22344D", borderRadius: 12, padding: "12px 14px", display: "flex", flexWrap: "wrap", justifyContent: "space-between", gap: 10, alignItems: "center", color: "#F6F4EE" } as const;
const solid = { background: "#177878", color: "#F6F4EE", border: 0, borderRadius: 10, padding: "11px 16px", fontWeight: 600, fontSize: 14 } as const;
const ghost = { background: "transparent", color: "inherit", border: "1px solid #2E4059", borderRadius: 10, padding: "11px 16px", fontWeight: 500, fontSize: 14 } as const;

export default function SketchPanel({ pid, did, onChanged }: { pid: string; did: string; onChanged: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [boxes, setBoxes] = useState<SketchBox[] | null>(null);
  const [title, setTitle] = useState("");
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  useEffect(() => {
    if (!file || !file.type.startsWith("image/") || typeof URL.createObjectURL !== "function") { setPreview(null); return; }
    const u = URL.createObjectURL(file);
    setPreview(u);
    return () => URL.revokeObjectURL?.(u);
  }, [file]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true); setMsg("");
    try { await fn(); } catch (e) { setMsg(e instanceof Error ? e.message : "That did not work."); } finally { setBusy(false); }
  };
  const read = () => run(async () => { const r = await readSketchFile(pid, did, file!); setBoxes(r.boxes); setTitle(r.title ?? ""); });
  const readTyped = () => run(async () => {
    const labels = typed.split("\n").map((l) => l.trim()).filter(Boolean);
    setBoxes((await readSketchLabels(pid, did, labels)).boxes);
  });
  const possible = (boxes ?? []).filter((b) => b.status === "possible");
  const missing = (boxes ?? []).filter((b) => b.status === "not_possible");
  const build = () => run(async () => {
    const r = await buildSketch(pid, did, possible, title);
    setMsg(`Placed ${r.placed} on the dashboard.`); onChanged();
  });
  const ask = () => run(async () => {
    const r = await requestSketch(pid, did, missing);
    setMsg(`Request sent to the data team: ${r.request_id}`);
  });

  return (
    <section aria-label="Sketch to dashboard" style={{ display: "flex", flexWrap: "wrap", gap: 20, alignItems: "flex-start", background: "#0F1B2D", color: "#F6F4EE", borderRadius: 12, padding: 20 }}>
      <div style={{ flex: "1 1 240px", minWidth: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ fontFamily: "monospace", fontSize: 12, color: "#8FA3B0", letterSpacing: "0.06em" }}>READ ON THIS MACHINE, THE PICTURE NEVER LEAVES</div>
        <label style={{ ...ghost, cursor: "pointer" }}>
          Choose or photograph a picture
          <input type="file" accept="image/*,application/pdf" capture="environment" aria-label="Sketch picture" style={{ marginLeft: 8 }}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
        {preview && <img src={preview} alt="Your sketch" style={{ maxWidth: "100%", borderRadius: 12, background: "#F6F4EE" }} />}
        {file && !preview && <div>{file.name}</div>}
        <button style={solid} disabled={!file || busy} onClick={read}>Read my sketch</button>
        <label style={{ fontSize: 13, color: "#8FA3B0" }}>Type the boxes instead
          <textarea value={typed} onChange={(e) => setTyped(e.target.value)} rows={4} placeholder="One box per line" style={{ display: "block", width: "100%", marginTop: 6, boxSizing: "border-box" }} />
        </label>
        <button style={ghost} disabled={!typed.trim() || busy} onClick={readTyped}>Read these boxes</button>
      </div>
      <div style={{ flex: "1 1 240px", minWidth: 0, display: "flex", flexDirection: "column", gap: 10 }}>
        <h2 style={{ margin: 0, fontSize: 18 }}>What Lumen understood, box by box</h2>
        {boxes === null && <p style={{ margin: 0, color: "#8FA3B0" }}>{busy ? "Reading your sketch on this machine..." : "Nothing read yet."}</p>}
        {title ? <p style={{ margin: 0 }}>Title read from the sketch: <strong>{title}</strong> (used as the dashboard's name)</p> : null}
        {boxes?.length === 0 && <p style={{ margin: 0, color: "#8FA3B0" }}>No boxes found in that picture.</p>}
        {boxes?.map((b) => {
          const p = PILL[b.status];
          const note = (b.status === "needs_definition" && b.question ? `${b.why} Needs one decision: ${b.question}` : b.status === "not_possible" && b.needs ? `${b.why} Needs ${b.needs}.` : b.why) + (b.note ? ` Your note: "${b.note}".` : "");
          return (
            <div key={b.id} style={card}>
              <span><strong>{b.label}</strong> → {note}</span>
              <span style={{ fontFamily: "monospace", fontSize: 11, color: p.color, border: `1px solid ${p.border}`, borderRadius: 999, padding: "3px 9px" }}>{p.word}</span>
            </div>
          );
        })}
        {boxes && boxes.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            <button style={solid} disabled={!possible.length || busy} onClick={build}>Build the {possible.length} possible now</button>
            <button style={ghost} disabled={!missing.length || busy} onClick={ask}>Ask the data team for the {missing.length} missing</button>
          </div>
        )}
        {msg && <p role="status" style={{ margin: 0, fontSize: 13 }}>{msg}</p>}
      </div>
    </section>
  );
}
