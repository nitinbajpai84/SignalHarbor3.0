import { Link } from "react-router-dom";

import V3Frame from "../Frame";
import TrustTabs from "../TrustTabs";
import { getLanguage, getModel, listPacks, type Language, type Model, type Pack } from "../api";
import { Status, useLoad } from "./a/useLoad";

interface ModelView { model: Model; packs: Pack[]; current: string; language: Language | null }
const loadAll = async (): Promise<ModelView> => {
  const [model, p, language] = await Promise.all([getModel(), listPacks(), getLanguage().catch(() => null)]);
  return { model, packs: p.packs, current: p.current, language };
};

function Layer({ title, note, items }: { title: string; note: string; items: { key: string; name: string; text: string }[] }) {
  return (
    <section className="v3-card" aria-label={title}>
      <h2>{title}</h2>
      <p className="v3-mute">{note}</p>
      {items.length === 0 ? <p className="v3-mute">Nothing here yet.</p> : (
        <div className="v3-figs">{items.map((i) => <div key={i.key} className="v3-fig"><b>{i.name}</b><small>{i.text}</small></div>)}</div>
      )}
    </section>
  );
}

export default function ModelPage() {
  const { data, failed, load } = useLoad<ModelView>(loadAll);
  const m = data?.model;
  const office = m?.objects.filter((o) => o.from !== "industry") ?? [];
  const industry = m?.objects.filter((o) => o.from === "industry") ?? [];
  const day = m && [
    ["Pick the industry", `${m.pack.label}, the model this office runs on`],
    ["Harbor reads your history files", "Every file you drop or connect"],
    ["Every column is placed on the model", `${m.coverage.pct}% placed by themselves, ${m.coverage.unmapped.length} asked`],
    ["First question", "Harbor asks one question about your numbers, in your words"],
    ["Live", "Threads run on your files from here on"],
  ];
  return (
    <V3Frame>
      <TrustTabs />
      <main className="v3-main">
        {!data || !m ? <Status failed={failed} retry={load} what="industry model" /> : !m.pack?.id ? (
          <div className="v3-card">
            <h1>No industry model yet</h1>
            <p>This office has not picked an industry pack. Pick one and the office starts with that pack's model.</p>
            <Link to="/v3/setup">Pick the industry in setup</Link>
          </div>
        ) : (
          <>
            <section className="v3-col" style={{ flex: "999 1 640px" }}>
              <div className="v3-head"><h1>This office runs on the {m.pack.label} model, version {m.pack.version}</h1></div>
              <p className="v3-mute">One industry model is shared by every office in the industry. This office adds its own pieces on top, and keeps its own words.</p>
              <h2>Three layers, one model</h2>
              <Layer title="Your language" note="Words this office uses. Harbor answers in them."
                items={(data.language?.words ?? []).map((w) => ({ key: w.word, name: w.word, text: w.means }))} />
              <Layer title="Learned here, stays here" note="Added by this office. Only this office uses these."
                items={office.map((o) => ({ key: o.name, name: o.label, text: o.from === "proposed" ? "Proposed, waiting for you" : "Added by this office" }))} />
              <Layer title="Comes with the pack" note="Shared by every office in the industry. Standard names and definitions."
                items={industry.map((o) => ({ key: o.name, name: o.label, text: `${o.count} rows` }))} />
            </section>
            <aside className="v3-side">
              <h2>How a new office starts (day one)</h2>
              <ol aria-label="Day one">{day!.map(([t, d]) => <li key={t}><b>{t}</b><br /><span className="v3-mute">{d}</span></li>)}</ol>
              <p className="v3-mute">A second office in the same industry starts with the same model, so the same questions and checks work on day one.</p>
              <h2>Other industries</h2>
              <p className="v3-mute">Same Harbor, same screens, a different model.</p>
              {data.packs.length === 0 ? <p className="v3-mute">No other industry packs are installed.</p> : data.packs.map((p) => (
                <div key={p.id} className="v3-link">
                  <b>{p.label}{p.id === data.current && <span className="v3-kicker">Current</span>}</b>
                  <small>{p.objects} objects · {p.questions} questions</small>
                </div>
              ))}
            </aside>
          </>
        )}
      </main>
    </V3Frame>
  );
}
