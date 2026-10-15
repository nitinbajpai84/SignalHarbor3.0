import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { shellCopy } from "./shellCopy";

export interface Crumb {
  label: string;
  to?: string;
}

interface Props {
  title: string;
  /** A small teal label above the title (for example the company the session belongs to). */
  eyebrow?: string;
  sub?: ReactNode;
  crumbs?: Crumb[];
  /** Right-hand side: a status pill or the main button. */
  actions?: ReactNode;
}

/** The earlier prototype's page header: n-crumb trail, then n-page-head with the page title (Fraunces) and its one-line sub. */
export default function PageHead({ title, eyebrow, sub, crumbs, actions }: Props) {
  return (
    <>
      {crumbs && crumbs.length > 0 ? (
        <nav className="n-crumb" aria-label={shellCopy.crumbs}>
          {crumbs.map((c, i) => (
            <Fragment key={`${i}-${c.label}`}>
              {i > 0 ? (
                <span className="sep" aria-hidden="true">
                  /
                </span>
              ) : null}
              {c.to ? <Link to={c.to}>{c.label}</Link> : <span aria-current="page">{c.label}</span>}
            </Fragment>
          ))}
        </nav>
      ) : null}
      <div className="n-page-head">
        <div>
          {eyebrow ? <div className="eyebrow">{eyebrow}</div> : null}
          <h1 className="n-page-title">{title}</h1>
          {sub ? <div className="n-page-sub">{sub}</div> : null}
        </div>
        {actions ? <div className="n-flex wrap">{actions}</div> : null}
      </div>
    </>
  );
}
