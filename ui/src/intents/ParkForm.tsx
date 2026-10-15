import { useState } from "react";

import { Button } from "../design";
import "../modules/m1_intent/define/define.css";

/** The Future shelf park form from the Define screen (DefineScreen.tsx), as one component with its words as props.
 * The backlog uses it for park (with a review date) and drop (without); Define can take it in place of its inline form. */
export interface ParkFormProps {
  title: string;
  reasonLabel: string;
  needMessage: string;
  saveLabel: string;
  cancelLabel: string;
  /** Shown with an editable date when given (the park form); left out for a drop. */
  review?: { value: string; line: (date: string) => string };
  footer?: string;
  onSave: (reason: string, reviewDate?: string) => void | Promise<void>;
  onCancel: () => void;
}

export default function ParkForm({ title, reasonLabel, needMessage, saveLabel, cancelLabel, review, footer, onSave, onCancel }: ParkFormProps) {
  const [reason, setReason] = useState("");
  const [date, setDate] = useState(review?.value ?? "");
  const [error, setError] = useState("");
  const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
  return (
    <form className="ds-card df-park" role="dialog" aria-label={title}
      onSubmit={(e) => { e.preventDefault(); if (!reason.trim()) setError(needMessage); else void onSave(reason.trim(), review ? date : undefined); }}>
      <strong>{title}</strong>
      <label>
        {reasonLabel}
        <input type="text" value={reason} maxLength={300} onChange={(e) => { setReason(e.target.value); setError(""); }} />
      </label>
      {error ? <p role="alert" className="df-alert">{error}</p> : null}
      {review ? (
        <label>
          <span className="ds-muted">{review.line(date)}</span>
          <input type="date" value={date} min={tomorrow} onChange={(e) => setDate(e.target.value || review.value)} />
        </label>
      ) : null}
      <div className="df-row">
        <Button type="submit" variant="primary" disabled={!reason.trim()}>{saveLabel}</Button>
        <Button onClick={onCancel}>{cancelLabel}</Button>
      </div>
      {footer ? <span className="ds-muted">{footer}</span> : null}
    </form>
  );
}
