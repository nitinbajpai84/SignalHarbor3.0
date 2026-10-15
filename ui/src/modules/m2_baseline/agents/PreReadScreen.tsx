import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import PageHead from "../../../components/PageHead";
import Panel from "../../../components/Panel";
import ScreenState from "../../../components/ScreenState";
import { useLoad } from "../../../components/useLoad";
import { getPreRead, notifyChanged, putPreRead, type PreRead, type PreReadKind } from "../api";
import { m2Pre, m2Work } from "../copy";
import WaitingDocuments from "./WaitingDocuments";

const HOME = "/modules/m2_baseline";

/** Step 0, before the work list: "Give Lens what you already have". A checklist over the company's own uploaded documents (the
 * Company context store), tagged by kind. Every item is optional; "we do not have this" is an answer. Lens reads what is there
 * and the industry text when the work list opens, and the person comes back to review. */
export default function PreReadScreen() {
  const { baselineId = "" } = useParams();
  const loaded = useLoad(() => getPreRead(baselineId), `preread-${baselineId}`);
  const [fresh, setFresh] = useState<PreRead | null>(null);
  const [problem, setProblem] = useState("");
  const go = useNavigate();
  const data = fresh ?? loaded.data;
  const save = (kind: string, body: { docs?: string[]; none?: boolean }) =>
    putPreRead(baselineId, kind, body).then((v) => { setFresh(v); setProblem(""); }).catch((e: unknown) => setProblem(e instanceof ApiError ? e.message : m2Pre.saveFailed));

  const row = (k: PreReadKind, d: PreRead) => (
    <li key={k.key} style={{ listStyle: "none", padding: "10px 0", borderTop: "1px solid var(--n-line, #ddd)" }}>
      <strong>{k.label}</strong>
      <div className="n-muted">{k.help}</div>
      <ul style={{ padding: 0 }}>
        {k.docs.map((x) => (
          <li key={x.doc_id} className="n-flex between wrap" style={{ listStyle: "none" }}>
            <span>{x.title}</span>
            <button type="button" className="n-btn sm" aria-label={`${m2Pre.remove}: ${x.title}`} onClick={() => save(k.key, { docs: k.docs.filter((y) => y.doc_id !== x.doc_id).map((y) => y.doc_id) })}>{m2Pre.remove}</button>
          </li>
        ))}
      </ul>
      <div className="n-flex wrap">
        <select className="n-select" aria-label={`${m2Pre.attach}: ${k.label}`} value="" disabled={k.none || d.documents.length === 0}
          onChange={(e) => e.target.value && save(k.key, { docs: [...k.docs.map((y) => y.doc_id), e.target.value] })}>
          <option value="">{m2Pre.attach}</option>
          {d.documents.filter((x) => !k.docs.some((y) => y.doc_id === x.doc_id)).map((x) => (
            <option key={x.doc_id} value={x.doc_id}>{x.title}{x.restricted ? ` (${m2Pre.restricted})` : ""}</option>
          ))}
        </select>
        <label>
          <input type="checkbox" checked={k.none} disabled={k.docs.length > 0} onChange={(e) => save(k.key, { none: e.target.checked })} /> {m2Pre.none}
        </label>
      </div>
    </li>
  );

  return (
    <>
      <PageHead title={m2Pre.crumb} sub={m2Pre.sub} crumbs={[{ label: m2Work.crumbModules, to: "/" }, { label: m2Work.crumbBaseline, to: HOME }, { label: m2Pre.crumb }]} />
      <ScreenState state={fresh ? "populated" : loaded.state} message={loaded.message} onRetry={loaded.retry}>
        {data ? (
          <Panel title={m2Pre.title}>
            {data.documents.length === 0 ? <p className="n-muted" role="note">{data.pack.available ? m2Pre.noDocs : m2Pre.noDocsNoPack}</p> : null}
            <p className="n-muted">{m2Pre.uploadHelp} <Link to="/company/context">{m2Pre.uploadLink}</Link></p>
            <WaitingDocuments baselineId={baselineId}
              docs={data.documents.filter((x) => x.personal_words && x.restrict_path).map((x) => ({ doc_id: x.doc_id, title: x.title, personal_words: x.personal_words ?? [], restrict_path: x.restrict_path ?? "" }))}
              onDecided={() => { void getPreRead(baselineId).then(setFresh).catch(() => setProblem(m2Pre.saveFailed)); notifyChanged(); }} />
            <ul style={{ padding: 0 }}>{data.kinds.map((k) => row(k, data))}</ul>
            {problem ? <p role="alert" className="state state-error">{problem}</p> : null}
            <button type="button" className="n-btn primary" onClick={() => go(`${HOME}/baselines/${baselineId}`)}>{m2Pre.start}</button>
          </Panel>
        ) : null}
      </ScreenState>
    </>
  );
}
