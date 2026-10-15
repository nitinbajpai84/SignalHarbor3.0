import { useId, type ReactNode } from "react";

interface Props {
  title?: string;
  /** The small teal label above the title (the earlier prototype's `eyebrow`). */
  eyebrow?: string;
  /** Right-hand side of the header: tags, buttons. */
  actions?: ReactNode;
  tight?: boolean;
  className?: string;
  /** Names the region when the title alone is not the right name. */
  label?: string;
  children?: ReactNode;
}

/** The earlier prototype's panel(): n-panel > n-panel-head (eyebrow + title, actions) > n-panel-body. The title is a real heading. */
export default function Panel({ title, eyebrow, actions, tight, className, label, children }: Props) {
  const headId = useId();
  const cls = `n-panel${tight ? " tight" : ""}${className ? ` ${className}` : ""}`;
  return (
    <section className={cls} aria-label={label} aria-labelledby={label || !title ? undefined : headId}>
      {title || eyebrow || actions ? (
        <div className="n-panel-head">
          {title || eyebrow ? (
            <div className="n-panel-title">
              {eyebrow ? <span className="eyebrow">{eyebrow}</span> : null}
              {title ? <h2 id={headId}>{title}</h2> : null}
            </div>
          ) : null}
          {actions ? <div className="n-panel-actions">{actions}</div> : null}
        </div>
      ) : null}
      <div className="n-panel-body">{children}</div>
    </section>
  );
}
