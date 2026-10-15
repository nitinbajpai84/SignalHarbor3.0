import { Link, useSearchParams } from "react-router-dom";

import { getWorkbench, listThreads, type Workbench } from "../api";
import { TrustPage, useLoad } from "./b/Shell";

const LAYERS = [["raw", "Raw · as received"], ["clean", "Clean · shared by the office"], ["ready", "Ready · this thread"]] as const;
const KICK = "Trust › Workbench · for the data engineer";

function Picker() {
  const s = useLoad(listThreads, "threads");
  const ts = s.data?.threads ?? [];
  return (
    <TrustPage kicker={KICK} title="Pick a thread" sub="The workbench is per thread." state={s} empty={s.data && !ts.length ? "There are no threads yet." : false}>
      {ts.map((t) => (
        <Link key={t.id} className="v3-link" to={`/v3/trust/workbench?thread=${encodeURIComponent(t.id)}`}>
          <b>{t.title}<span className="v3-mute">{t.stage}</span></b>
        </Link>))}
    </TrustPage>
  );
}

function Bench({ id }: { id: string }) {
  const s = useLoad<Workbench>(() => getWorkbench(id), id);
  const w = s.data;
  const none = !!w && !w.steps.length && !w.tables.length && !w.rules.length;
  return (
    <TrustPage kicker={KICK} title="What Harbor did, and the rules it works under" sub="One click from any thread. The business user never has to come here." state={s}
      empty={none ? "Harbor has not done any work on this thread yet." : false}>
      {w && <>
        <section className="v3-card"><h2>Steps</h2>
          {w.steps.map((x) => (
            <div key={x.n} className="v3-row tr-step">
              <span className="num">{x.n}</span><b>{x.agent}</b><span style={{ flex: 1 }}>{x.action}</span>
              {x.run_id && <code className="num">{x.run_id}</code>}
              <span className={`v3-pill ${x.ok ? "done" : "problem"}`}>{x.ok ? "OK" : "Failed"}</span>
            </div>))}
        </section>
        <section><h2>The model and its lineage</h2>
          <div className="v3-checks" style={{ gridTemplateColumns: "repeat(auto-fit,minmax(220px,1fr))", marginTop: 10 }}>
            {LAYERS.map(([layer, label]) => (
              <div key={layer}><b>{label}</b>
                {w.tables.filter((t) => t.layer === layer).map((t) => (
                  <p key={t.name} className="v3-mute"><span className="num">{t.name}</span> · {t.rows} rows · {t.state}</p>))}
              </div>))}
          </div>
        </section>
        <section className="v3-card"><h2>When Harbor must ask a person</h2>
          <ul>{w.rules.map((r) => <li key={r}>{r}</li>)}</ul>
          <p className="v3-mute">Everything else it does, records, and lets you undo.</p>
        </section>
        <p><Link to={`/v3/thread/${encodeURIComponent(id)}`}>Back to the thread</Link> · <Link to="/v3/trust/people">Autonomy per thread</Link></p>
      </>}
    </TrustPage>
  );
}

export default function WorkbenchPage() {
  const [q] = useSearchParams();
  const id = q.get("thread");
  return id ? <Bench id={id} /> : <Picker />;
}
