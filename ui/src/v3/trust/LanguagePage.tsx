import { useState, type FormEvent } from "react";

import V3Frame from "../Frame";
import TrustTabs from "../TrustTabs";
import { addWord, decideCorrection, getLanguage, type Language } from "../api";
import { Status, useLoad } from "./a/useLoad";

export default function LanguagePage() {
  const { data: l, setData, failed, load } = useLoad<Language>(getLanguage);
  const [word, setWord] = useState("");
  const [means, setMeans] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");

  async function send(call: () => Promise<Language>) {
    setBusy(true);
    setProblem("");
    try {
      setData(await call());
      return true;
    } catch {
      setProblem("That did not go through. Try again.");
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function add(e: FormEvent) {
    e.preventDefault();
    if (word.trim() && means.trim() && (await send(() => addWord(word.trim(), means.trim())))) {
      setWord("");
      setMeans("");
    }
  }

  return (
    <V3Frame>
      <TrustTabs />
      <main className="v3-main">
        {!l ? <Status failed={failed} retry={load} what="office's words" /> : (
          <>
            <section className="v3-col" style={{ flex: "999 1 640px" }}>
              <div className="v3-head"><h1>The office's words</h1></div>
              <p className="v3-mute">Harbor suggests a word or a rule. You approve it once, and it applies everywhere.</p>
              <div className="v3-card">
                <div className="v3-head"><h2>Lexicon</h2><span className="v3-mute">{l.words.length} words</span></div>
                {l.words.length === 0 ? <p className="v3-mute">No words yet. Add the first one below.</p> : (
                  <div className="tr-scroll"><table style={{ borderCollapse: "collapse", fontSize: 14 }}>
                    <thead><tr><th align="left">The office's word</th><th align="left">Means</th><th align="left">Added by</th><th align="left">Used</th></tr></thead>
                    <tbody>
                      {l.words.map((w) => (
                        <tr key={w.word}>
                          <td style={{ padding: "6px 16px 6px 0" }}><b>{w.word}</b></td><td>{w.means}</td><td>{w.by}</td>
                          <td className="num">{w.used} times</td>
                        </tr>
                      ))}
                    </tbody>
                  </table></div>
                )}
                <form className="v3-row" onSubmit={add} aria-label="Add a word">
                  <input aria-label="Word" placeholder="Add a word" value={word} onChange={(e) => setWord(e.target.value)} />
                  <input aria-label="Means" placeholder="Means" value={means} onChange={(e) => setMeans(e.target.value)} />
                  <button type="submit" className="go" disabled={busy || !word.trim() || !means.trim()}>Add</button>
                </form>
              </div>
              <div className="v3-card">
                <div className="v3-head"><h2>Golden questions</h2><span className="v3-mute">{l.golden.length} approved</span></div>
                <p className="v3-mute">Approved question and answer pairs. Harbor checks new answers against these first.</p>
                {l.golden.length === 0 && <p className="v3-mute">None approved yet.</p>}
                {l.golden.map((g) => (
                  <div key={g.q} className="v3-fig"><b>{g.q}</b><p style={{ margin: "6px 0" }}>{g.a}</p><small>Approved by {g.by}</small></div>
                ))}
              </div>
            </section>
            <aside className="v3-side">
              <span className="v3-kicker">Needs you · Correction · {l.corrections.length} waiting</span>
              <h2>Corrections waiting</h2>
              <p className="v3-mute">Harbor noticed a pattern in how the office talks. Is it right?</p>
              {l.corrections.length === 0 && <p className="v3-mute">Nothing waiting.</p>}
              {l.corrections.map((c) => (
                <div key={c.id} className="v3-card need">
                  <p>{c.text}</p>
                  <div className="v3-row">
                    <button type="button" className="go" disabled={busy} onClick={() => send(() => decideCorrection(c.id, "admit"))}>Admit</button>
                    <button type="button" disabled={busy} onClick={() => send(() => decideCorrection(c.id, "reject"))}>Not right</button>
                  </div>
                </div>
              ))}
              {problem && <p className="v3-err" role="alert">{problem}</p>}
              <h2>Taught knowledge</h2>
              <p className="v3-mute">Books and policies distilled into playbooks. Suggestions only; people decide what applies.</p>
              {l.taught.length === 0 && <p className="v3-mute">Nothing taught yet.</p>}
              {l.taught.map((t) => (
                <div key={t.name} className="v3-link">
                  <b>{t.name}<span className="v3-mute">v{t.version} · <span className={`v3-pill ${t.on ? "done" : "info"}`}>{t.on ? "On" : "Off"}</span></span></b>
                  <small>Distilled from {t.books} {t.books === 1 ? "book" : "books"}</small>
                </div>
              ))}
              <p className="v3-mute">Everything here stays in your environment; Harbor suggests from it, people decide.</p>
            </aside>
          </>
        )}
      </main>
    </V3Frame>
  );
}
