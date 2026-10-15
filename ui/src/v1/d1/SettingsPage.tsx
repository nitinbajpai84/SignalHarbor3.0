import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import { Button, PageFrame, Pill } from "../../design";
import * as api from "./api";
import type { HookState, Settings } from "./api";
import "./d1.css";

// V5 D1: where an administrator sets up Slack, Teams and outgoing webhooks. The address itself is a secret kept outside the product: here you save its NAME
// and the host it sends to. Email is set up on the server (SH_SMTP_URL); this page only says whether it is.
const plain = (e: unknown) => (e instanceof ApiError && e.message ? e.message : "That did not go through. Please try again.");

function Row({ h, onSaved }: { h: HookState; onSaved: (s: Settings) => void }) {
  const [secret, setSecret] = useState(h.secret);
  const [host, setHost] = useState(h.host);
  const [error, setError] = useState("");
  const save = (s: string, ho: string) => api.putSettings(h.kind, s, ho).then((r) => { setError(""); onSaved(r); }).catch((e) => setError(plain(e)));
  return (
    <li className="d1-card">
      <header><h3>{h.label}</h3><Pill tone={h.configured ? "ok" : "draft"}>{h.configured ? "Set up" : "Not set up"}</Pill></header>
      <div className="d1-form">
        <label>Name of the secret that holds the address <input value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="SH_SLACK_WEBHOOK" /></label>
        <label>Host it sends to <input value={host} onChange={(e) => setHost(e.target.value)} placeholder="hooks.slack.com" /></label>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="d1-row"><Button variant="primary" onClick={() => void save(secret, host)}>Save</Button>{h.secret && <Button onClick={() => void save("", "")}>Remove</Button>}</div>
      {h.secret && !h.configured && <p>The secret named {h.secret} has no value on the server yet. Ask whoever runs the server to set it.</p>}
    </li>
  );
}

export default function SettingsPage() {
  const [s, setS] = useState<Settings | null>(null);
  const [error, setError] = useState("");
  useEffect(() => { api.getSettings().then(setS).catch((e) => setError(plain(e))); }, []);
  return (
    <PageFrame title="Delivery channels" crumbs={<Link className="ds-link" to="/centre/build">Build</Link>}
      subline="Where Lumen may send approved dashboards. Only the hosts listed here can be reached. Every send is logged without its content.">
      {error && <p role="alert">{error}</p>}
      {s && <>
        <ul className="d1-list">{s.channels.map((h) => <Row key={h.kind} h={h} onSaved={setS} />)}</ul>
        <section className="d1-card"><header><h3>Email digest</h3><Pill tone={s.email.configured ? "ok" : "draft"}>{s.email.configured ? "Set up" : "Not set up"}</Pill></header>
          <p>{s.email.configured ? "Email goes out through your mail server." : "Email is not set up on the server yet, so email messages are kept in the outbox."}</p>
          <p>Allowed address domains: {s.email.domains.length ? s.email.domains.join(", ") : "none yet"}.</p></section></>}
    </PageFrame>
  );
}
