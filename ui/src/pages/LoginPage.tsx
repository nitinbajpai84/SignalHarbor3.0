import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError } from "../api/client";
import BrandMark from "../components/BrandMark";
import ThemeControl from "../components/ThemeControl";
import { copy } from "../copy";
import { Button } from "../design";
import { useSession } from "../useSession";
import { loginCopy } from "./loginCopy";

// One card on the design tokens (styles/design.css); page-only layout here, no inline colours.
const loginStyle = `
.lg-page { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 16px; box-sizing: border-box; background: var(--ds-ground); }
.lg-card { width: 100%; max-width: 380px; box-sizing: border-box; padding: 32px 28px; display: flex; flex-direction: column; gap: 20px; border-radius: var(--ds-radius-lg); }
.lg-head { display: flex; flex-direction: column; align-items: center; gap: 10px; text-align: center; }
.lg-title { margin: 0; font-size: 22px; font-weight: 700; color: var(--ds-ink); }
.lg-tagline { margin: 0; font-size: 14px; color: var(--ds-ink-muted); }
.lg-form { display: flex; flex-direction: column; gap: 14px; }
.lg-field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--ds-ink-soft); }
.lg-input { min-height: 44px; box-sizing: border-box; padding: 8px 12px; border-radius: 8px; border: 1px solid var(--ds-line-2); background: var(--ds-ground); color: var(--ds-ink); font: inherit; font-size: 14px; }
.lg-input:focus-visible { outline: 2px solid var(--ds-teal-bright); outline-offset: 1px; }
.lg-line { margin: 0; font-size: 13px; color: var(--ds-amber); }
.lg-theme { display: flex; justify-content: center; color: var(--ds-ink-muted); font-size: 13px; }
@media (max-width: 480px) { .lg-card { padding: 24px 20px; } .lg-title { font-size: 20px; } }
`;

export default function LoginPage() {
  const { signIn, sessionEnded } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => first.current?.focus(), []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? copy.login.mismatch : copy.login.unavailable);
      setPassword("");
      setBusy(false);
    }
  }

  return (
    <div className="ds-screen lg-page">
      <style>{loginStyle}</style>
      <div className="ds-card lg-card">
        <div className="lg-head">
          <BrandMark named={false} size={48} />
          <h1 className="lg-title">{copy.product}</h1>
          <p className="lg-tagline">{loginCopy.tagline}</p>
        </div>
        {sessionEnded ? <p role="status" className="lg-line">{copy.errors.sessionEnded}</p> : null}
        <form className="lg-form" onSubmit={submit}>
          <label htmlFor="email" className="lg-field">
            {copy.login.email}
            <input id="email" ref={first} className="lg-input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label htmlFor="password" className="lg-field">
            {copy.login.password}
            <input id="password" className="lg-input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>
          {error ? <p role="alert" className="lg-line">{error}</p> : null}
          <Button type="submit" variant="primary" disabled={busy}>{busy ? copy.login.busy : copy.login.button}</Button>
        </form>
        <div className="lg-theme"><ThemeControl /></div>
      </div>
    </div>
  );
}
