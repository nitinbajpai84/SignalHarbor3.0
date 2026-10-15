import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { getPulse } from "../e5/api";
import TodayPage from "../e5/TodayPage";
import { WhereFrom } from "./TrailHost";

/** The old Today page (Needs me, Worth a look, Not for me, Viewing as) with "Where is this from?" on every card that comes from a case; folded at the bottom of Action. */
export default function PulseFull() {
  const box = useRef<HTMLDivElement>(null);
  const [byHeadline, setBy] = useState<Record<string, string>>({});
  const [hosts, setHosts] = useState<{ el: HTMLElement; id: string }[]>([]);
  useEffect(() => { getPulse("").then((d) => setBy(Object.fromEntries(d.items.filter((i) => i.case_id).map((i) => [i.headline, i.case_id as string])))).catch(() => undefined); }, []);
  useEffect(() => {
    const root = box.current;
    if (!root) return;
    const scan = () => {
      const next: { el: HTMLElement; id: string }[] = [];
      root.querySelectorAll("li.ds-card").forEach((li) => {
        const id = byHeadline[li.querySelector("h2")?.textContent ?? ""];
        if (!id) return;
        let el = li.querySelector<HTMLElement>("[data-trail]");
        if (!el) { el = document.createElement("div"); el.dataset.trail = id; li.appendChild(el); }
        next.push({ el, id });
      });
      setHosts((old) => (old.length === next.length && old.every((o, i) => o.el === next[i]?.el) ? old : next));
    };
    scan();
    const mo = new MutationObserver(scan);
    mo.observe(root, { childList: true, subtree: true });
    return () => mo.disconnect();
  }, [byHeadline]);
  return <div ref={box}><TodayPage framed skipKinds={["assignment"]} />{hosts.map((h) => createPortal(<WhereFrom kind="case" id={h.id} />, h.el))}</div>;
}
