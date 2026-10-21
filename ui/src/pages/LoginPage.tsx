import { useEffect, useRef, useState, type FormEvent } from "react";

import { ApiError, apiSend } from "../api/client";
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
  const [otp, setOtp] = useState("");
  const [step, setStep] = useState<"password" | "code" | "setup">("password");
  const [setup, setSetup] = useState<{ secret: string; otpauth: string; codes?: string[] } | null>(null);
  const first = useRef<HTMLInputElement>(null);

  useEffect(() => first.current?.focus(), []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password, step === "code" ? otp : undefined);
    } catch (err) {
      // W7: the server asks for the authenticator code (401) or for the office's required set-up (403)
      const msg = err instanceof ApiError ? err.message : "";
      if (err instanceof ApiError && err.status === 403 && /second step/i.test(msg)) { setStep("setup"); setError(msg); }
      else if (err instanceof ApiError && err.status === 401 && /6-digit|code did not work/i.test(msg)) { setStep("code"); setError(msg); setOtp(""); }
      else { setError(err instanceof ApiError && err.status === 401 ? copy.login.mismatch : copy.login.unavailable); setPassword(""); setStep("password"); }
      setBusy(false);
    }
  }

  async function startSetup() {
    setError(null);
    try { setSetup(await apiSend("POST", "/api/auth/mfa/start", { email, password })); } catch (err) { setError((err as Error).message); }
  }
  async function confirmSetup() {
    setError(null);
    try {
      const r = await apiSend<{ recovery_codes: string[] }>("POST", "/api/auth/mfa/confirm", { email, password, otp });
      setSetup((s) => (s ? { ...s, codes: r.recovery_codes } : s));
    } catch (err) { setError((err as Error).message); }
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
          {step === "code" ? (
            <label htmlFor="otp" className="lg-field">
              Authenticator code or recovery code
              <input id="otp" className="lg-input" inputMode="numeric" autoComplete="one-time-code" required value={otp} onChange={(e) => setOtp(e.target.value)} />
            </label>
          ) : null}
          {error ? <p role="alert" className="lg-line">{error}</p> : null}
          {step === "setup" ? (
            <div className="lg-form">
              {!setup ? <Button type="button" variant="primary" onClick={() => void startSetup()}>Set up my authenticator app</Button> : setup.codes ? (
                <>
                  <p className="lg-tagline">Keep these recovery codes somewhere safe. Each works once and they are not shown again.</p>
                  <pre>{setup.codes.join(" ")}</pre>
                  <Button type="button" variant="primary" onClick={() => { setStep("password"); setSetup(null); setOtp(""); setError(null); }}>Done, sign in</Button>
                </>
              ) : (
                <>
                  <p className="lg-tagline">Add this key to your authenticator app (shown once): <b>{setup.secret}</b>. <a href={setup.otpauth}>Open in app</a></p>
                  <input aria-label="Code from the app" className="lg-input" inputMode="numeric" value={otp} onChange={(e) => setOtp(e.target.value)} />
                  <Button type="button" variant="primary" onClick={() => void confirmSetup()}>Turn it on</Button>
                </>
              )}
            </div>
          ) : <Button type="submit" variant="primary" disabled={busy}>{busy ? copy.login.busy : copy.login.button}</Button>}
        </form>
        <div className="lg-theme"><ThemeControl /></div>
      </div>
    </div>
  );
}
