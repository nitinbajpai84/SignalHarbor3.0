import { useState, type ReactNode } from "react";

import { Button } from "../../design";
import { Grey } from "./DocumentLayout";
import { getTemplate, type OutlineItem, type Template, type TemplateSummary } from "./api";
import "./templates.css";

// T1b: templates shown as documents. The thumbnail is drawn from the template's section list (no image file): a heading bar per section
// (amber when required), then grey lines or the columns of a table. "Preview" opens the whole skeleton.

export function Thumb({ outline }: { outline: OutlineItem[] }) {
  return (
    <div className="tpl-thumb" aria-hidden="true">
      {outline.slice(0, 7).map((o) => (
        <div key={o.key}>
          <b className={o.required ? "req" : undefined} style={{ width: `${Math.min(90, 28 + o.heading.length)}%` }} />
          {o.type === "table" ? <u>{(o.columns?.length ? o.columns : ["a", "b", "c"]).slice(0, 5).map((c) => <span key={c} />)}</u>
            : <i style={{ width: "92%", marginTop: 2 }} />}
        </div>
      ))}
    </div>
  );
}

export function Skeleton({ t }: { t: Template }) {
  return (
    <div className="tpl-doc" aria-label={`Preview of ${t.name}`}>
      {(t.sections ?? []).map((s) => (
        <section key={s.key} className="tpl-sec tpl-sec--grey">
          <h3 className="tpl-h">{s.heading}{s.required ? <span className="tpl-req"> Required</span> : null}</h3>
          <Grey s={s} />
        </section>
      ))}
      <section className="tpl-sec tpl-sec--grey"><h3 className="tpl-h">Anything else</h3><p className="tpl-ins tpl-grey">Anything the template does not ask for.</p></section>
    </div>
  );
}

export default function TemplateCards({ templates, pick, onPick, extra }: {
  templates: TemplateSummary[]; pick: string; onPick: (id: string) => void; extra?: (t: TemplateSummary) => ReactNode;
}) {
  const [open, setOpen] = useState<Template | null>(null);
  const [failed, setFailed] = useState("");
  const preview = (id: string) => {
    if (open?.id === id) { setOpen(null); return; }
    setFailed("");
    getTemplate(id).then(setOpen).catch(() => setFailed("The preview could not be opened. Please try again."));
  };
  return (
    <>
      <div className="tpl-picks" role="radiogroup" aria-label="Templates">
        {templates.map((t) => (
          <div key={t.id} className="tpl-pick" data-chosen={pick === t.id}>
            {t.outline?.length ? <Thumb outline={t.outline} /> : null}
            <label>
              <input type="radio" name="template" checked={pick === t.id} onChange={() => onPick(t.id)} /> <strong>{t.name}</strong>
              {t.standard ? <span className="ds-muted"> (your company's standard)</span> : null}
            </label>
            {t.description ? <div className="ds-muted">{t.description}</div> : null}
            {t.companions && Object.keys(t.companions).length ? (
              <div className="ds-muted">Comes with: {Object.values(t.companions).map((c) => c.name).join(" and ")}</div>
            ) : null}
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <Button onClick={() => preview(t.id)} aria-label={`Preview ${t.name}`}>{open?.id === t.id ? "Close preview" : "Preview"}</Button>
              {extra?.(t)}
            </div>
          </div>
        ))}
      </div>
      {failed ? <p role="alert">{failed}</p> : null}
      {open ? <div className="tpl-preview"><h3 style={{ marginTop: 0 }}>{open.name}</h3><Skeleton t={open} /></div> : null}
    </>
  );
}
