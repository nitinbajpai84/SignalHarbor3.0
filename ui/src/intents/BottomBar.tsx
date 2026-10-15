import type { ReactNode } from "react";

import "./phone.css";

/** File 17's fixed bottom bar: at most two actions (one primary, one secondary). Render it on phone only and give the page `ic-bar-pad`. */
export default function BottomBar({ children, label = "Actions" }: { children: ReactNode; label?: string }) {
  return <nav aria-label={label} className="ic-bar">{children}</nav>;
}
