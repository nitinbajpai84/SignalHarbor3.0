import type { FormEvent, KeyboardEvent } from "react";

import Icon from "./Icon";

/** js/companion.js 241-248: Enter sends, Shift+Enter is a new line; and 127-131: the box grows with what is written. */
const sendsOnEnter = (e: KeyboardEvent) => e.key === "Enter" && !e.shiftKey && !e.altKey && !e.ctrlKey && !e.metaKey && !e.nativeEvent.isComposing;
const rowsFor = (text: string) => Math.min(8, Math.max(1, text.split("\n").reduce((n, line) => n + Math.max(1, Math.ceil(line.length / 46)), 0)));

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  label: string;
  placeholder: string;
  sendLabel: string;
  busy?: boolean;
}

/** The docked panel's ask box, moved out of module 1's NiraDock so every agent's panel has the same one. */
export default function AskBox({ value, onChange, onSubmit, label, placeholder, sendLabel, busy = false }: Props) {
  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    onSubmit();
  };
  return (
    <form className="n-companion-ask" onSubmit={submit}>
      <Icon name="chat" size={14} />
      <textarea
        className="n-companion-ask-input"
        rows={rowsFor(value)}
        placeholder={placeholder}
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (!sendsOnEnter(e)) return;
          e.preventDefault();
          submit();
        }}
      />
      <button type="submit" className="n-icon-btn" aria-label={sendLabel} disabled={busy}>
        <Icon name="send" size={13} />
      </button>
    </form>
  );
}
