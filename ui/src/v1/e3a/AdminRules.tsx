import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../../api/client";
import Panel from "../../components/Panel";
import { Button, PageFrame, Pill } from "../../design";
import { useSession } from "../../useSession";
import { listFiles, type IntakeFile } from "../e0c/api";
import { approveRule, importSigned, listRules, proposeRule, ruleHistory, type ImportResult, type RuleLine, type RuleVersion } from "./api";

// E3a: /centre/admin/rules, the Admin rules register: each rule in words, who owns it, and what waits for a second person to sign.
const plain = (err: unknown) => (err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
const STATE: Record<RuleVersion["state"], string> = { draft: "Waiting for a signature", approved: "Signed", retired: "Retired" };
const TONE = { draft: "open", approved: "signed", retired: "draft" } as const;
const KINDS = ["tolerance", "materiality", "policy", "fixing", "deadline", "limit"];
const WRITERS = ["company_admin", "sponsor", "analyst"]; // the approver reads the register (P15); e3_rules refuses their writes too

export default function AdminRules() {
  const roles = useSession().user?.roles ?? [];
  const writer = roles.some((r) => WRITERS.includes(r));
  const [rules, setRules] = useState<RuleLine[] | null>(null);
  const [note, setNote] = useState("");
  const [shown, setShown] = useState("");
  const [history, setHistory] = useState<RuleVersion[]>([]);
  const load = useCallback(() => listRules().then(setRules).catch((e) => { setRules([]); setNote(plain(e)); }), []);
  useEffect(() => { void load(); }, [load]);
  const open = (code: string) => { setShown(code); ruleHistory(code).then(setHistory).catch((e) => setNote(plain(e))); };
  const sign = async (id: string) => {
    setNote("");
    try { await approveRule(id); await load(); if (shown) open(shown); } catch (e) { setNote(plain(e)); }
  };

  return (
    <PageFrame title="Rules"
      subline={`The rules the figures follow, and the benchmarks. A new version counts only after someone other than its proposer signs it.${writer ? "" : " You can read them here; the data team proposes and signs."}`}>
      {note ? <p role="alert">{note}</p> : null}
      {rules === null ? <p className="ds-muted" role="status">Loading the rules.</p> : rules.length === 0 ? <p className="ds-muted">No rules yet. Propose the first one below.</p> : (
        <table className="ds-table" style={{ width: "100%" }}>
          <thead><tr><th>Rule</th><th>Value in words</th><th>From</th><th>Owner</th><th>State</th></tr></thead>
          <tbody>{rules.map((r) => (
            <tr key={r.rule_code}>
              <td>{r.rule_type === "benchmark" ? <>Benchmark {r.rule_code}</> : <Button onClick={() => open(r.rule_code)}>{r.rule_code.replace(/_/g, " ")}</Button>}</td>
              <td>{r.definition_text}</td><td>{r.effective_from}</td><td>{r.owner ?? (r.rule_type === "benchmark" ? "Each version is signed by a second person, named beside it" : "Not named")}</td>
              <td><Pill tone={TONE[r.state]}>{STATE[r.state]}</Pill>{r.waiting ? <> {r.waiting} new {r.waiting === 1 ? "version" : "versions"} waiting</> : null}</td>
            </tr>))}</tbody>
        </table>
      )}
      {shown ? (
        <Panel title={`History of ${shown.replace(/_/g, " ")}`}>
          <ul>{history.map((v) => (
            <li key={v.rule_version_id}>
              Version {v.version_number}, from {v.effective_from}: {v.definition_text} <Pill tone={TONE[v.state]}>{STATE[v.state]}</Pill>
              {v.approved_by ? <> by {v.approved_by}</> : null}
              {v.state === "draft" && writer ? <> <Button variant="primary" onClick={() => void sign(v.rule_version_id)}>Approve</Button></> : null}
            </li>))}</ul>
        </Panel>
      ) : null}
      {writer ? <ImportSigned onDone={() => { void load(); }} /> : null}
      {writer ? <Propose codes={(rules ?? []).filter((r) => r.rule_type !== "benchmark").map((r) => r.rule_code)} onDone={() => { void load(); }} /> : null}
    </PageFrame>
  );
}

// UC5: the signed limits workbook, uploaded in Data intake, read line by line against the register; changes wait for a second person to sign.
function ImportSigned({ onDone }: { onDone: () => void }) {
  const [files, setFiles] = useState<IntakeFile[]>([]);
  const [pick, setPick] = useState("");
  const [out, setOut] = useState<ImportResult | null>(null);
  const [msg, setMsg] = useState("");
  useEffect(() => { listFiles().then((r) => setFiles(r.files.filter((f) => /\.(xlsx|xlsm)$/i.test(f.name)))).catch(() => setFiles([])); }, []);
  const send = async () => {
    setMsg(""); setOut(null);
    try { const r = await importSigned(pick); setOut(r); onDone(); } catch (e) { setMsg(plain(e)); }
  };
  const pct = (x: { min_pct: number; max_pct: number }) => `${x.min_pct}% to ${x.max_pct}%`;
  return (
    <Panel title="Import signed limits" eyebrow="Upload the signed sheet in Data intake first">
      <p><label>Signed limits workbook <select value={pick} onChange={(e) => setPick(e.target.value)}>
        <option value="">Choose a file</option>{files.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}</select></label></p>
      <Button variant="primary" disabled={!pick} onClick={() => void send()}>Import signed limits</Button>
      {msg ? <p role="alert">{msg}</p> : null}
      {out ? (
        <div role="status">
          <p>{out.version ?? "The sheet"}, in force from {out.effective_from}.</p>
          {out.proposed.length ? <ul>{out.proposed.map((p) => <li key={p.rule_code}>{p.rule_code.replace(/_/g, " ")}: {p.before ? pct(p.before) : "not in the register"} → {pct(p.after)}. Waits for a signature.</li>)}</ul> : null}
          {out.unchanged.length ? <p className="ds-muted">Unchanged: {out.unchanged.map((c) => c.replace(/_/g, " ")).join(", ")}.</p> : null}
          {out.waiting.length ? <p className="ds-muted">Already waiting for a signature: {out.waiting.map((c) => c.replace(/_/g, " ")).join(", ")}.</p> : null}
          {out.case_id ? <p>The signer has an item in Action naming what differs.</p> : !out.proposed.length ? <p>The register already matches the signed sheet.</p> : null}
        </div>) : null}
    </Panel>
  );
}

function Propose({ codes, onDone }: { codes: string[]; onDone: () => void }) {
  const [code, setCode] = useState("");
  const [kind, setKind] = useState("tolerance");
  const [words, setWords] = useState("");
  const [from, setFrom] = useState("");
  const [values, setValues] = useState("{}");
  const [msg, setMsg] = useState("");
  const isNew = code !== "" && !codes.includes(code);
  const send = async () => {
    setMsg("");
    let parameters: Record<string, unknown>;
    try { parameters = JSON.parse(values || "{}") as Record<string, unknown>; } catch { setMsg("The values must look like {\"abs_amount\": 5000, \"currency\": \"USD\"}."); return; }
    try {
      await proposeRule(code.trim(), { definition_text: words, parameters, effective_from: from, rule_type: isNew ? kind : undefined });
      setMsg("Sent. It counts once someone else signs it."); setWords(""); onDone();
    } catch (e) { setMsg(plain(e)); }
  };
  return (
    <Panel title="Propose a new version" eyebrow="The rule's owner proposes, or the data team proposes for them; someone else signs">
      <p><label>Rule code <input list="rule-codes" value={code} onChange={(e) => setCode(e.target.value)} /></label>
        <datalist id="rule-codes">{codes.map((c) => <option key={c} value={c} />)}</datalist></p>
      {isNew ? <p><label>Kind of rule <select value={kind} onChange={(e) => setKind(e.target.value)}>{KINDS.map((k) => <option key={k}>{k}</option>)}</select></label></p> : null}
      <p><label>The rule in words <input value={words} onChange={(e) => setWords(e.target.value)} /></label></p>
      <p><label>Applies from <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></label></p>
      <p><label>Values the system reads <input value={values} onChange={(e) => setValues(e.target.value)} /></label></p>
      <Button variant="primary" disabled={!code.trim() || !words.trim() || !from} onClick={() => void send()}>Send for signature</Button>
      {msg ? <p role="status">{msg}</p> : null}
    </Panel>
  );
}
