import { Navigate, useSearchParams } from "react-router-dom";

import { Chip, PageFrame } from "../../design";
import DefinitionsTab from "./DefinitionsTab";
import ModelTab from "./ModelTab";
import OntologyPage from "./OntologyPage";
import ProcessTab from "./ProcessTab";

// The Map: one page, four views read from the company's records; nothing here can be edited.
// Old links still land: ?tab=flow|conversations opens the ontology (with ?focus kept), ?tab=health is now /centre/operations.
export const VIEWS = [{ id: "ontology", label: "Ontology" }, { id: "processes", label: "Process map" }, { id: "model", label: "Data model" }, { id: "definitions", label: "Business glossary" }] as const;

export default function MapPage() {
  const [q, setQ] = useSearchParams();
  const t = q.get("tab") ?? q.get("view"), focus = q.get("focus");
  if (t === "health") return <Navigate to="/centre/operations" replace />;
  if (t === "flow" || t === "conversations") return <Navigate to={focus ? `/centre/map?focus=${encodeURIComponent(focus)}` : "/centre/map"} replace />;
  const tab = VIEWS.find((v) => v.id === t)?.id ?? "ontology";
  return (
    <PageFrame title={tab === "model" ? "The data model" : "The office's ontology"} subline={tab === "model" ? undefined : "People, projects and data, and how each number is made."}>
      <div role="tablist" aria-label="Map views" style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {VIEWS.map((v) => <Chip key={v.id} tone={tab === v.id ? "active" : "default"} onClick={() => setQ(v.id === "ontology" ? {} : { tab: v.id })}>{v.label}</Chip>)}
      </div>
      {tab === "ontology" ? <OntologyPage /> : null}
      {tab === "processes" ? <ProcessTab focus={focus} /> : null}
      {tab === "model" ? <ModelTab focus={focus} /> : null}
      {tab === "definitions" ? <DefinitionsTab focus={focus} /> : null}
    </PageFrame>
  );
}
