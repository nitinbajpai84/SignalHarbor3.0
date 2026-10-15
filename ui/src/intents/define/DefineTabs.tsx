import { Component, lazy, Suspense, type ComponentType, type ReactNode } from "react";

import ScreenState from "../../components/ScreenState";
import { Chip } from "../../design";

// The tabs of Define (file 26, ruling 18: ?tab=). Each tab's content belongs to its own card; a file not landed yet shows its "waits for" line.

export type DefineTab = "clusters" | "process-map" | "data-sources" | "glossary" | "catalogue" | "source-map";
/** What every tab receives: the intent, the wall session behind it and the selected cluster (null with nothing selected). */
export interface DefineTabProps { intentId: string; sessionId: string | null; clusterId: string | null }

export const TABS: { key: DefineTab; label: string; file: string | null; spec: string }[] = [
  { key: "clusters", label: "Clusters and shelves", file: null, spec: "26" },
  { key: "process-map", label: "Process map", file: "ProcessMapTab", spec: "27" },
  { key: "data-sources", label: "Data sources", file: "DataSourcesTab", spec: "28" },
  { key: "glossary", label: "Glossary", file: "GlossaryTab", spec: "29" },
  { key: "catalogue", label: "Catalogue", file: "CatalogueTab", spec: "30" },
  { key: "source-map", label: "Source map", file: "SourceMapTab", spec: "28" },
];

export const waits = (spec: string) => `Not available yet. Waits for file ${spec}.`;

/** The tab named by ?tab=, else clusters. */
export function tabFrom(search: string): DefineTab {
  const t = new URLSearchParams(search).get("tab");
  return TABS.some((x) => x.key === t) ? (t as DefineTab) : "clusters";
}

type Loaded = { default?: ComponentType<DefineTabProps> } & Record<string, unknown>;
const loaders = import.meta.glob<Loaded>(["./*Tab.tsx", "./LensStrip.tsx"]);

class Guard extends Component<{ spec: string; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <ScreenState state="empty" message={waits(this.props.spec)} /> : this.props.children; }
}

const cache: Record<string, ComponentType<DefineTabProps>> = {};
function partOf(file: string, spec: string): ComponentType<DefineTabProps> {
  const load = loaders[`./${file}.tsx`];
  if (!load) return () => <ScreenState state="empty" message={waits(spec)} />;
  return (cache[file] ??= lazy(async () => {
    const m = await load();
    return { default: (m.default ?? m[file]) as ComponentType<DefineTabProps> };
  }));
}

/** A part another card owns, by file name, behind the guard. */
export function Part({ file, spec, ...props }: DefineTabProps & { file: string; spec: string }) {
  const P = partOf(file, spec);
  return <Guard spec={spec}><Suspense fallback={<ScreenState state="loading" />}><P {...props} /></Suspense></Guard>;
}

const NEEDS_BASELINE: DefineTab[] = ["data-sources", "catalogue"];
export const NO_BASELINE = "No baseline is linked to this intent yet.";

export default function DefineTabs({ tab, props, clusters, hasBaseline = true }: { tab: DefineTab; props: DefineTabProps; clusters: ReactNode; hasBaseline?: boolean }) {
  const here = TABS.find((t) => t.key === tab) ?? TABS[0]!;
  return (
    <>
      <nav aria-label="Define tabs" style={{ display: "flex", gap: 8, flexWrap: "wrap", overflowX: "auto", margin: "12px 0" }}>
        {TABS.map((t) => <Chip key={t.key} href={`?tab=${t.key}`} tone={t.key === tab ? "active" : "default"}>{t.label}</Chip>)}
      </nav>
      {here.file === null ? clusters : !hasBaseline && NEEDS_BASELINE.includes(tab) ? <ScreenState state="empty" message={NO_BASELINE} /> : <Part file={here.file} spec={here.spec} {...props} />}
    </>
  );
}
