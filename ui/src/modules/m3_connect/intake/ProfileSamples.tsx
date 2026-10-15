import { useState } from "react";

import { ApiError } from "../../../api/client";
import Panel from "../../../components/Panel";
import { placeSample, uploadAuto, uploadChosen, type Candidate, type FromProfile, type ToConfirm } from "./api";
import { m3Intake as T } from "./copy";
import FilePicker from "./FilePicker";
import ProfileView from "./ProfileView";

interface Pending {
  file: string;
  data: string;
  candidates: Candidate[];
}

/** LI-M3: samples the company profile already holds (shown with where they came from), the ones Lens could not place, and a drop box that files itself. */
export default function ProfileSamples({ assessmentId, fromProfile, toConfirm, onChanged }:
  { assessmentId: string; fromProfile: FromProfile[]; toConfirm: ToConfirm[]; onChanged: () => void }) {
  const [filed, setFiled] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  async function run(go: () => Promise<void>) {
    setProblem(null);
    try {
      await go();
    } catch (e) {
      setProblem(e instanceof ApiError && e.message ? e.message : T.actionFailed);
    }
  }
  const choose = (s: Candidate[], label: string, pick: (sourceId: string) => void) => (
    <select aria-label={label} defaultValue="" onChange={(e) => e.target.value && pick(e.target.value)}>
      <option value="">{T.chooseSource}</option>
      {s.map((c) => (
        <option key={c.source_id} value={c.source_id}>
          {c.source_name}
        </option>
      ))}
    </select>
  );

  return (
    <>
      {fromProfile.length > 0 ? (
        <Panel title={T.fromProfileTitle}>
          <p className="n-muted">{T.fromProfileHelp}</p>
          {fromProfile.map((f) => (
            <div key={f.source_id}>
              <h4>{f.source_name}</h4>
              <p className="n-muted">{T.from(f.from)}</p>
              {f.profile ? <ProfileView profile={f.profile} /> : null}
            </div>
          ))}
        </Panel>
      ) : null}
      {toConfirm.length > 0 ? (
        <Panel title={T.placeTitle}>
          <p className="n-muted">{T.placeHelp}</p>
          {toConfirm.map((c) => (
            <p key={c.key}>
              <strong>{c.file}</strong> <span className="n-muted">{T.from(c.from)}</span>{" "}
              {choose(c.candidates, T.placeFor(c.file), (sid) => void run(async () => (await placeSample(assessmentId, c.key, sid), onChanged())))}
            </p>
          ))}
        </Panel>
      ) : null}
      <Panel title={T.dropTitle}>
        <p className="n-muted">{T.dropHelp}</p>
        <FilePicker label={T.dropLabel} button={T.dropSend}
          send={async (name, data) => {
            setFiled(null);
            setPending(null);
            const got = await uploadAuto(assessmentId, name, data);
            if (got.filed) {
              setFiled(got.filed.source_name);
              onChanged();
            } else if (got.needs_confirm) {
              setPending({ file: name, data, candidates: got.needs_confirm.candidates });
            }
          }} />
        {filed ? <p role="status">{T.filedAs(filed)}</p> : null}
        {pending ? (
          <p>
            <strong>{T.placeTitle}</strong> {pending.file}{" "}
            {choose(pending.candidates, T.placeFor(pending.file), (sid) =>
              void run(async () => {
                const got = await uploadChosen(assessmentId, sid, pending.file, pending.data);
                setPending(null);
                setFiled(pending.candidates.find((c) => c.source_id === sid)?.source_name ?? got.filed?.source_name ?? null);
                onChanged();
              }))}
          </p>
        ) : null}
        {problem ? (
          <p role="alert" className="state state-error">
            {problem}
          </p>
        ) : null}
      </Panel>
    </>
  );
}
