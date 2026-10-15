import { useState } from "react";

import { Button } from "../../design";
import type { LineEdit } from "../i4/api";

// One line of a document with an "edit" link (copied from the first version of ConversationPage; the layout of the template uses it too).
export default function Line({ label, value, edit, can, save }: { label: string; value: string; edit: Omit<LineEdit, "value">; can: boolean; save: (e: LineEdit) => Promise<void> }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(value);
  if (!open) {
    return (
      <p style={{ margin: "4px 0" }}>
        <span className="ds-muted">{label}: </span>{value || <span className="ds-muted">Not stated</span>}
        {can ? <> <button type="button" className="ds-link" aria-label={`Edit ${label}`} onClick={() => { setText(value); setOpen(true); }}>edit</button></> : null}
      </p>
    );
  }
  return (
    <form style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "4px 0" }}
      onSubmit={(ev) => { ev.preventDefault(); void save({ ...edit, value: text }).then(() => setOpen(false)); }}>
      <input className="ds-input" aria-label={label} value={text} onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 200px" }} />
      <Button variant="primary" type="submit">Save</Button>
      <Button onClick={() => setOpen(false)}>Cancel</Button>
    </form>
  );
}
