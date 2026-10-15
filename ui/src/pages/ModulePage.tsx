import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { listModules, Refused, type ModuleInfo } from "../api/client";
import AppShell from "../components/AppShell";
import ScreenState, { type ScreenStateName } from "../components/ScreenState";
import { copy } from "../copy";
import IntentModule from "../modules/m1_intent/IntentModule";
import BaselineModule from "../modules/m2_baseline/BaselineModule";
import ConnectModule from "../modules/m3_connect/ConnectModule";

// Module 1 has its screens; the others stay placeholders until their phase. The server's list decides what the company owns.
export default function ModulePage() {
  const { id } = useParams();
  const [state, setState] = useState<ScreenStateName>("loading");
  const [mod, setMod] = useState<ModuleInfo | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    listModules()
      .then((all) => {
        if (!live) return;
        const found = all.find((m) => m.id === id) ?? null;
        setMod(found);
        setState(found ? "populated" : "refused");
      })
      .catch((e: unknown) => live && setState(e instanceof Refused ? "refused" : "error"));
    return () => {
      live = false;
    };
  }, [id, attempt]);

  const retry = useCallback(() => {
    setState("loading");
    setAttempt((a) => a + 1);
  }, []);

  return (
    <AppShell>
      <p>
        <Link to="/">{copy.module.back}</Link>
      </p>
      {state === "refused" ? <h1 className="n-page-title">{copy.states.refusedHeading}</h1> : null}
      <ScreenState state={state} onRetry={retry}>
        {mod?.id === "m1_intent" ? (
          <IntentModule />
        ) : mod?.id === "m2_baseline" ? (
          <BaselineModule />
        ) : mod?.id === "m3_connect" ? (
          <ConnectModule />
        ) : (
          <>
            <h1 className="n-page-title">{mod?.name}</h1>
            <p>{copy.module.placeholder}</p>
          </>
        )}
      </ScreenState>
    </AppShell>
  );
}
