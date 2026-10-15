import { useState } from "react";

import { ApiError } from "../../api/client";
import { Button } from "../../design";
import { raiseRequest } from "./api";

// "Need a different template? Ask your company admin": a short request that the admin sees in the console (a ticket once T2 exists).
export default function RequestBox({ about = "" }: { about?: string }) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [state, setState] = useState<"" | "sending" | "sent">("");
  const [error, setError] = useState("");

  async function send() {
    setState("sending");
    setError("");
    try {
      await raiseRequest({ kind: "template", about, text: text.trim() });
      setState("sent");
    } catch (err) {
      setState("");
      setError(err instanceof ApiError && err.message ? err.message : "That did not go through. Please try again.");
    }
  }

  if (state === "sent") return <p className="ds-muted" role="status">Thank you. Your company admin has your request.</p>;
  return (
    <div>
      <p className="ds-muted" style={{ margin: "8px 0" }}>
        Need a different template? <Button onClick={() => setOpen(!open)}>Ask your company admin</Button>
      </p>
      {open ? (
        <form onSubmit={(ev) => { ev.preventDefault(); if (text.trim()) void send(); }} style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input className="ds-input" aria-label="What template do you need" placeholder="What do you need that the templates do not cover?"
            value={text} onChange={(ev) => setText(ev.target.value)} style={{ flex: "1 1 260px" }} />
          <Button variant="primary" type="submit" disabled={state === "sending" || !text.trim()}>Send request</Button>
        </form>
      ) : null}
      {error ? <p role="alert">{error}</p> : null}
    </div>
  );
}
