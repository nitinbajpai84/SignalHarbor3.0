import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { getEmail, type EmailNote } from "./api";
import { Loading, plain } from "./format";

// E6: the Morning Note as it arrives by email. The same template package 4 sends (k10_note.render_email); shown here in a sandboxed frame so nothing in it can run.
export default function EmailPreview({ ccy }: { ccy: string }) {
  const [mail, setMail] = useState<EmailNote | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    setMail(null); setError("");
    getEmail(ccy).then((r) => { if (live) setMail(r); }, (e) => { if (live) setError(plain(e)); });
    return () => { live = false; };
  }, [ccy]);
  if (error) return <p role="alert">{error}</p>;
  if (!mail) return <Loading what="the email" />;
  return (
    <>
      <p className="ds-muted" style={{ letterSpacing: 1, fontSize: "0.8rem", margin: 0 }}>DELIVERY PREVIEW</p>
      <h3 style={{ margin: "4px 0" }}>The Morning Note by email</h3>
      <p>The same note, with the same figures as the Consume page; every link opens the signed source.</p>
      <p><strong>Subject:</strong> {mail.subject}</p>
      <iframe title="Morning Note email" sandbox="" srcDoc={mail.html} style={{ width: "100%", minHeight: 560, border: "1px solid var(--ds-line, #ccc)", background: "#fff" }} />
      <p><Link className="ds-link" to="/centre/consume">Back to the Morning Note</Link></p>
    </>
  );
}
