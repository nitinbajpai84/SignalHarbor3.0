import { useState } from "react";

import { ApiError } from "../../../api/client";
import { getCharterEmail, getCharterFiles, type CharterEmail } from "../api";
import { m1Charter as T } from "../copy";

const say = (e: unknown, fallback: string) => (e instanceof ApiError && e.status !== 0 && e.status < 500 && e.message ? e.message : fallback);

/** Once the charter is signed: download it (everyone who may read it) and, for the organiser, a ready email for the people
 * who took part. Nothing is sent from here; addresses typed for guests live only in this component. */
export default function ShareCharter({ sessionId, organiser }: { sessionId: string; organiser: boolean }) {
  const [note, setNote] = useState<string | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const [email, setEmail] = useState<CharterEmail | "loading" | null>(null);
  const [typed, setTyped] = useState<Record<number, string>>({});

  async function download(format: "html" | "markdown") {
    setProblem(null);
    try {
      const file = (await getCharterFiles(sessionId)).files.find((f) => f.format === format);
      if (!file) throw new Error("missing");
      const url = URL.createObjectURL(new Blob([file.content], { type: `${file.mime};charset=utf-8` }));
      const a = document.createElement("a");
      a.href = url;
      a.download = file.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setProblem(say(e, T.downloadFailed));
    }
  }

  async function prepare() {
    setProblem(null);
    setNote(null);
    setTyped({});
    setEmail("loading");
    try {
      setEmail(await getCharterEmail(sessionId));
    } catch (e) {
      setEmail(null);
      setProblem(say(e, T.emailFailed));
    }
  }

  const ready = email !== null && email !== "loading" ? email : null;
  const text = ready ? ready.body : ""; // the server put the full address in
  const addresses = ready ? ready.people.map((p, i) => p.email ?? (typed[i] ?? "").trim()).filter((a) => a !== "") : [];
  const mailto = ready ? `mailto:?bcc=${addresses.map(encodeURIComponent).join(",")}&subject=${encodeURIComponent(ready.subject)}&body=${encodeURIComponent(text)}` : "";
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(`Subject: ${ready?.subject}\n\n${text}`);
      setNote(T.emailCopied);
    } catch {
      setNote(T.emailCopyFailed);
    }
  };

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="m1-actions">
        <button type="button" className="n-btn primary" onClick={() => void download("html")}>
          {T.download}
        </button>
        <button type="button" className="n-btn" onClick={() => void download("markdown")}>
          {T.downloadMarkdown}
        </button>
        {organiser ? (
          <button type="button" className="n-btn" disabled={email === "loading"} onClick={() => void prepare()}>
            {T.emailPeople}
          </button>
        ) : null}
      </div>
      {email === "loading" ? <p role="status" className="state n-muted">{T.emailLoading}</p> : null}
      {ready ? (
        <div>
          <p className="n-e1-def-note">{T.emailHelp}</p>
          {ready.no_address.length > 0 ? <p role="status">{T.emailMissing(ready.no_address)}</p> : null}
          <h3>{T.emailPeopleTitle}</h3>
          <ul>
            {ready.people.map((p, i) => (
              <li key={i}>
                {p.name}
                {p.email ? `, ${p.email}` : (
                  <>
                    {` (${T.emailNoAddress}) `}
                    <input type="email" aria-label={T.emailTypeAddress(p.name)} value={typed[i] ?? ""} onChange={(e) => setTyped((v) => ({ ...v, [i]: e.target.value }))} />
                  </>
                )}
              </li>
            ))}
          </ul>
          <label>
            {T.emailSubject}
            <input style={{ width: "100%" }} type="text" readOnly value={ready.subject} />
          </label>
          <label>
            {T.emailBody}
            <textarea style={{ width: "100%" }} rows={10} readOnly value={text} />
          </label>
          <div className="m1-actions">
            <button type="button" className="n-btn" onClick={() => void copy()}>
              {T.emailCopy}
            </button>
            <a className="n-btn" href={mailto}>
              {T.emailOpen}
            </a>
          </div>
        </div>
      ) : null}
      {note ? <p role="status" className="state n-muted">{note}</p> : null}
      {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
    </div>
  );
}
