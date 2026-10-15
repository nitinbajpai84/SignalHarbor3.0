import { useId, useRef, useState } from "react";

import { ApiError } from "../../../api/client";
import { m3Intake as T } from "./copy";
import { readFile } from "./api";

/** Choose one file and send it. `send` gets the file's name and its base64 text; a refusal shows the server's plain sentence. */
export default function FilePicker({ label, button, send }: { label: string; button: string; send: (filename: string, data: string) => Promise<void> }) {
  const id = useId();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function go() {
    const file = input.current?.files?.[0];
    if (!file) return;
    setBusy(true);
    setProblem(null);
    try {
      await send(file.name, await readFile(file));
      if (input.current) input.current.value = "";
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : T.actionFailed);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <label htmlFor={id}>{label}</label>{" "}
      <input id={id} ref={input} type="file" accept=".xlsx,.csv,.json" disabled={busy} />{" "}
      <button type="button" className="n-btn" disabled={busy} onClick={() => void go()}>
        {busy ? T.uploading : button}
      </button>
      {problem ? (
        <p role="alert" className="state state-error">
          {problem}
        </p>
      ) : null}
    </div>
  );
}
