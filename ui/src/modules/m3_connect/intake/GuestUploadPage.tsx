import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../../api/client";
import GuestShell from "../../../components/GuestShell";
import ScreenState from "../../../components/ScreenState";
import { Pill, SideCard } from "../../../design";
import { useLoad } from "../../m1_intent/useLoad";
import { linkForm, linkUpload, type IntakeRequest, type Profile } from "./api";
import AskedTables from "./AskedTables";
import { m3Intake as T } from "./copy";
import FilePicker from "./FilePicker";
import ProfileView from "./ProfileView";

const linkProblem = (e: unknown): string =>
  e instanceof ApiError ? (e.status === 429 ? T.ownerTooMany : e.status !== 0 && e.status < 500 && e.message ? e.message : T.ownerNoPage) : T.ownerNoPage;

type Form = IntakeRequest & { profile: Profile | null };

/** The page behind /intake/<token>: no sign-in and no module chrome. A source owner sees what is asked of their source and sends a file. */
export default function GuestUploadPage() {
  const { token = "" } = useParams();
  const { state, data, message } = useLoad<Form>(() => linkForm(token).catch((e: unknown) => Promise.reject(new ApiError(linkProblem(e), 404))), "m3-intake-link");
  return (
    <GuestShell title={T.ownerTitle}>
      <ScreenState state={state} message={message}>
        {data ? <Send token={token} form={data} /> : null}
      </ScreenState>
    </GuestShell>
  );
}

function Send({ token, form }: { token: string; form: Form }) {
  const [now, setNow] = useState<Form>(form);
  const send = (kind: "source" | "benchmark") => async (name: string, data: string) => {
    try {
      setNow(await linkUpload(token, name, data, kind));
    } catch (e) {
      throw new ApiError(linkProblem(e), 422);
    }
  };
  return (
    <>
      <p className="ds-soft" style={{ margin: 0 }}>
        {T.ownerHelp} {T.period(now.period.label)}
      </p>
      <SideCard title={now.source_name}>
        {now.state === "arrived" ? <p role="status"><Pill tone="ok">{T.ownerThanks}</Pill></p> : null}
        <AskedTables tables={now.tables} />
        <FilePicker label={T.chooseFile} button={T.upload} send={send("source")} />
        <p className="ds-muted">{T.stays}</p>
      </SideCard>
      {now.benchmarks.length > 0 ? (
        <SideCard title={T.ownerBench}>
          <ul>
            {now.benchmarks.map((b) => (
              <li key={b.measure_id}>{b.ask}</li>
            ))}
          </ul>
          <FilePicker label={T.chooseFile} button={T.benchUpload} send={send("benchmark")} />
        </SideCard>
      ) : null}
      {now.profile ? <SideCard title={T.profile}><ProfileView profile={now.profile} /></SideCard> : null}
    </>
  );
}
