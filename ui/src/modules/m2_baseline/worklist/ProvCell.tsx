import StatusPill from "../../../components/StatusPill";
import type { Prov } from "../api";
import { m2Work } from "../copy";
import { S } from "./layout";

const TONE = { stated: "success", guessed: "warning", unknown: "muted" } as const;

/** A provenance value: the words, how sure (stated, a guess, unknown) and who said it and where it came from.
 * Unknown shows no words, only its mark: a blank is never shown as known. */
export default function ProvCell({ p }: { p: Prov }) {
  return (
    <div style={S.prov}>
      {p.value ? <div>{p.value}</div> : null}
      <div className="n-flex wrap">
        <StatusPill tone={TONE[p.mark]}>{m2Work.marks[p.mark]}</StatusPill>
        {p.mark !== "unknown" && p.by ? (
          <span className="n-muted" style={S.by}>
            {m2Work.by(p.by)}
            {p.from ? ` · ${m2Work.fromWhere(p.from)}` : ""}
          </span>
        ) : null}
      </div>
    </div>
  );
}
