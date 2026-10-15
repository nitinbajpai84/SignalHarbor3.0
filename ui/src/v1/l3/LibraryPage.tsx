import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { changeItem, deleteItem } from "../c4/api";
import { PageFrame } from "../../design";
import { getOpenPlaces, type OpenPlaces } from "./api";
import LibraryFolders from "./LibraryFolders";

// UX3: every document the person may see, in one place. The same folders, search, Open link and locked rows as the Saved documents window,
// without the ticks. Owners keep Share and Delete. Open needs a project: ?iid= from the Saved documents window, else (INT3) the
// project the file is ticked in, else the viewer's first project.
export default function LibraryPage() {
  const [params] = useSearchParams();
  const iid = params.get("iid") || undefined;
  const [places, setPlaces] = useState<OpenPlaces | null>(null);
  useEffect(() => {
    if (iid) return;
    let live = true;
    getOpenPlaces().then((p) => live && setPlaces(p), () => undefined);
    return () => { live = false; };
  }, [iid]);
  return (
    <PageFrame title="Library" subline="Every document you may see. A locked file shows what it is; ask for access to read it.">
      <LibraryFolders iid={iid} openIn={places ? (i) => places.byItem[i.id] ?? places.first : undefined} extra={(i, reload) => i.mine ? (
        <>
          <label style={{ fontSize: 13 }}>
            <input type="checkbox" role="switch" checked={i.visibility === "company"} aria-label={`Share ${i.name} with the company`}
              onChange={(e) => void changeItem(i.id, { visibility: e.target.checked ? "company" : "private" }).then(reload, reload)} /> Share with the company
          </label>
          <button type="button" className="ds-link" onClick={() => void deleteItem(i.id).then(reload, reload)}>Delete</button>
        </>
      ) : null} />
    </PageFrame>
  );
}
