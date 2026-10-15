import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError, Refused } from "../../api/client";
import { Button, DataTable, EmptyState, PageFrame, Pill, SideCard, Strip } from "../../design";
import { confirmType, decideRevision, fileName, getOverview, propose, type DocType, type Overview } from "./api";

// X5 spec panel: per kind of document, what North takes out of it (values, where they usually sit, checks), the documents read and
// their state, and a revised spec after a layout change (before and after on two documents, yes or no). `SpecPanel` may be placed
// in another screen; ExtractionPage frames it at /centre/intent/:iid/extraction.
const CHECK: Record<string, string> = { present: "must be there", parses: "must read as", range: "within", ties_to: "must agree with" };

function TypeCard({ iid, t, onDone }: { iid: string; t: DocType; onDone: () => void }) {
  const [failed, setFailed] = useState(false);
  const act = (p: Promise<unknown>) => { setFailed(false); p.then(onDone).catch(() => setFailed(true)); };
  return (
    <SideCard title={`${t.name} · version ${t.version}`}>
      <p><Pill tone={t.state === "confirmed" ? "signed" : "draft"}>{t.state === "confirmed" ? "Confirmed" : "Proposed by North"}</Pill>{" "}
        {t.sample_files.length ? `From ${t.sample_files.map(fileName).join(", ")}` : ""}</p>
      <DataTable columns={[{ key: "n", label: "Value" }, { key: "m", label: "Meaning" }, { key: "f", label: "Kind" }, { key: "w", label: "Usually under" }, { key: "r", label: "Required" }]}
        rows={t.fields.map((f) => ({ n: f.name, m: f.meaning || "not said", f: f.format, w: f.where_usually || "not said", r: f.required ? "Yes" : "No" }))} />
      {t.checks.length > 0 && <ul>{t.checks.map((c, i) => <li key={i}>{c.field} {CHECK[c.kind]} {c.detail}</li>)}</ul>}
      {t.examples.length > 0 && <p className="ds-soft">{t.examples.length} worked example{t.examples.length === 1 ? "" : "s"} from corrections.</p>}
      {t.state === "proposed" && <Button variant="primary" onClick={() => act(confirmType(iid, t.id))}>Confirm this list</Button>}
      {t.revision && (
        <div role="region" aria-label="Revised spec">
          <p><strong>North suggests a revised spec.</strong> {t.revision.why}</p>
          <DataTable columns={[{ key: "d", label: "Document" }, { key: "b", label: "Before" }, { key: "a", label: "After" }]}
            rows={t.revision.before_after.map((x) => ({ d: fileName(x.file), b: x.before || "not found", a: x.after || "not found" }))} />
          <Button variant="primary" onClick={() => act(decideRevision(iid, t.id, true))}>Use the revised spec</Button>{" "}
          <Button onClick={() => act(decideRevision(iid, t.id, false))}>Keep the current one</Button>
        </div>
      )}
      {failed && <p role="alert" className="ds-warn">Could not save. Try again.</p>}
    </SideCard>
  );
}

export function SpecPanel({ iid }: { iid: string }) {
  const [data, setData] = useState<Overview | null>(null);
  const [state, setState] = useState<"loading" | "error" | "refused" | "ready">("loading");
  const [file, setFile] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let live = true;
    getOverview(iid).then((o) => { if (live) { setData(o); setState("ready"); } })
      .catch((e: unknown) => { if (live) setState(e instanceof Refused || (e instanceof ApiError && e.status === 403) ? "refused" : "error"); });
    return () => { live = false; };
  }, [iid, attempt]);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  if (state === "loading") return <EmptyState title="Reading the extraction spec" lines={["One moment."]} />;
  if (state === "refused") return <EmptyState title="You do not have access to this" lines={["The decision maker and the analyst see the spec."]} />;
  if (state === "error" || !data) return <><EmptyState title="The spec could not be read" lines={["Nothing was changed."]} /><Button onClick={reload}>Try again</Button></>;
  const ask = () => { propose(iid, file).then(() => { setFile(""); reload(); }).catch(() => setState("error")); };
  return (
    <>
      <Strip label={data.queue.line} tone={data.queue.count ? "amber" : "teal"}>
        {data.types.length ? data.types.map((t) => <TypeCard key={t.id} iid={iid} t={t} onDone={reload} />)
          : <EmptyState title="No document types yet" lines={["Tell North what you take out of your documents, or ask it to propose from one."]} />}
        <p>
          <input aria-label="Document to propose from" placeholder="File name, for example statement.md" value={file} onChange={(e) => setFile(e.target.value)} />{" "}
          <Button disabled={!file.trim()} onClick={ask}>Propose from this document</Button>
        </p>
      </Strip>
      {data.documents.length > 0 && (
        <Strip label="Documents read">
          <DataTable columns={[{ key: "f", label: "Document" }, { key: "t", label: "Kind" }, { key: "v", label: "Version" }, { key: "s", label: "State" }]}
            rows={data.documents.map((d) => ({ f: fileName(d.file), t: d.type_name, v: String(d.version),
              s: <Pill tone={d.status === "ok" ? "ok" : "late"}>{d.status === "ok" ? "Read" : "Needs a look"}</Pill> }))} />
          {data.queue.count > 0 && <p><a href="/centre/extract/review">Open the review queue</a></p>}
        </Strip>
      )}
    </>
  );
}

export default function ExtractionPage() {
  const { iid = "" } = useParams();
  return (
    <div className="ds-screen">
      <PageFrame title="What North takes out of documents" crumbs="Intent · Extraction" subline="Per kind of document: the values, where they usually sit, and the checks.">
        <SpecPanel iid={iid} />
      </PageFrame>
    </div>
  );
}
