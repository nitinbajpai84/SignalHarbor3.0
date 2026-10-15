import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { listModules, Refused, type ModuleInfo } from "../api/client";
import AppShell from "../components/AppShell";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import { copy } from "../copy";

type Tile = ModuleInfo & { centre?: string | null; centre_name?: string; centre_description?: string };

// Tiles grouped under their centre's heading, in the order the server sent them; modules with no centre sit in a group with no heading.
function groupByCentre(list: Tile[]) {
  const groups: { id: string; name?: string; description?: string; modules: Tile[] }[] = [];
  for (const m of list) {
    const id = m.centre ?? "";
    let g = groups.find((x) => x.id === id);
    if (!g) groups.push((g = { id, name: m.centre_name, description: m.centre_description, modules: [] }));
    g.modules.push(m);
  }
  return groups;
}

export default function HomePage() {
  const [state, setState] = useState<ScreenStateName>("loading");
  const [modules, setModules] = useState<ModuleInfo[]>([]);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    listModules()
      .then((list) => {
        if (!live) return;
        setModules(list);
        setState(list.length === 0 ? "empty" : "populated");
      })
      .catch((e: unknown) => live && setState(e instanceof Refused ? "refused" : "error"));
    return () => {
      live = false;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setState("loading");
    setAttempt((a) => a + 1);
  }, []);

  const groups = groupByCentre(modules);
  return (
    <AppShell>
      <h1 className="n-page-title">{copy.home.heading}</h1>
      <ScreenState state={state} onRetry={retry} message={state === "empty" ? copy.home.emptyModules : undefined}>
        {groups.map((g) => (
          <section key={g.id}>
            {g.name ? <h2>{g.name}</h2> : null}
            {g.description ? <p className="n-muted">{g.description}</p> : null}
            <ul className="tiles">
              {g.modules.map((m) => (
                <li key={m.id}>
                  <Link to={`/modules/${m.id}`} className="tile n-panel">
                    <span className="tile-number">{m.number}</span>
                    <span className="tile-name">{m.name}</span>
                    <span>{m.description}</span>
                    <span className="tile-agent">
                      {copy.home.guidedBy} {m.agent}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </ScreenState>
    </AppShell>
  );
}
