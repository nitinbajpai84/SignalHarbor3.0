import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../../api/client";
import WizardFrame from "../../components/WizardFrame";
import { copy } from "../../copy";
import { createDraft, deleteDraft, saveTemplate, updateDraft, type Lists, type SessionView, type TemplateRow } from "./api";
import CharterPaper from "./CharterPaper";
import { m1, m1Lean, m1Room } from "./copy";
import DraftedSession from "./DraftedSession";
import {
  blankForm, CUSTOM, formFrom, formFromDraft, lengthOrZero, lengthProblem, splitProblem, toPreparation, withLength, type Form,
} from "./form";

const W = m1.wizard;
const STEPS = (["purpose", "charter", "people", "north", "video", "approver", "review"] as const).map((id) => ({
  id,
  label: W.steps[id],
}));

interface Props {
  lists: Lists;
  templates: TemplateRow[];
  /** The saved draft being edited, or null for a new one. */
  existing: SessionView | null;
  onDeleted: () => void;
  /** Tells the page whether the form holds changes that are not saved (so "Start the room" can say to save first). */
  onUnsaved?: (unsaved: boolean) => void;
}

/** M1-01 and M1-02: the Prepare wizard. Saves a draft the organiser can come back to until the session starts. */
export default function PrepareWizard({ lists, templates, existing, onDeleted, onUnsaved }: Props) {
  // LI-M1: a new session opens drafted from the company profile when it holds a purpose; "Change something" opens the wizard with those values
  const drafted = !existing && Boolean(lists.profile_draft?.available && lists.profile_draft.fields.purpose);
  const [showDraft, setShowDraft] = useState(drafted);
  const [form, setForm] = useState<Form>(() => (existing ? formFrom(existing.preparation, lists) : drafted ? formFromDraft(lists) : blankForm(lists)));
  const [step, setStep] = useState(0);
  const [savedId, setSavedId] = useState<string | null>(existing?.id ?? null);
  // what the server holds, in the form's own shape: the form is "unsaved" while it differs
  const [savedForm, setSavedForm] = useState<string | null>(() => (existing ? JSON.stringify(toPreparation(form)) : null));
  const unsaved = savedForm === null || savedForm !== JSON.stringify(toPreparation(form));
  useEffect(() => onUnsaved?.(unsaved), [unsaved, onUnsaved]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [templateName, setTemplateName] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  const set = (patch: Partial<Form>) => {
    setForm((f) => ({ ...f, ...patch }));
    setNotice(null);
  };
  const splitMsg = splitProblem(form, lists);
  const badLength = lengthProblem(form, lists);
  const lengthMsg = badLength ? W.lengthRange(lists.custom_length_minutes.min, lists.custom_length_minutes.max) : null;
  const purposeOk = form.purpose.trim() !== "";
  const canSave = purposeOk && !badLength && splitMsg === null && !busy;
  const stepId = STEPS[step]?.id ?? "purpose";
  const ready = stepId === "purpose" ? purposeOk : stepId === "people" ? !badLength && splitMsg === null : true;

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : copy.errors.server);
    } finally {
      setBusy(false);
    }
  }

  const save = () =>
    run(async () => {
      const prep = toPreparation(form);
      const s = savedId ? await updateDraft(savedId, prep) : await createDraft(prep);
      setSavedId(s.id);
      setSavedForm(JSON.stringify(prep));
      setNotice(W.saved);
    });
  const makeTemplate = () =>
    run(async () => {
      if (!savedId) return;
      await saveTemplate(templateName, savedId);
      setTemplateName("");
      setNotice(W.templateSaved);
    });
  const remove = () =>
    run(async () => {
      if (!savedId) return;
      await deleteDraft(savedId);
      onDeleted();
    });

  const fromTemplate = (id: string) => {
    const t = templates.find((x) => x.id === id);
    if (t) setForm(formFrom(t.preparation, lists));
  };

  const chosen = lists.charter_templates.find((t) => t.id === form.charter_template);
  const north = lists.north;
  const suggestion = stepId === "north" && (north.problem_library_available || north.industry_practice_available)
    ? W.northSuggestion
    : undefined;

  if (showDraft) return <DraftedSession lists={lists} onChange={() => setShowDraft(false)} />;
  return (
    <WizardFrame
      title={STEPS[step]?.label ?? W.title}
      agent={stepId === "north" ? "North" : undefined}
      steps={STEPS}
      current={step}
      ready={ready}
      onBack={() => setStep((s) => Math.max(0, s - 1))}
      onNext={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
      suggestion={suggestion}
    >
      {stepId === "purpose" ? (
        <>
          {!existing && templates.length > 0 ? (
            <label>
              {W.fromTemplate}
              <select defaultValue="" onChange={(e) => fromTemplate(e.target.value)}>
                <option value="">{W.noTemplate}</option>
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {!existing && templates.length === 0 ? <p className="n-muted">{W.noTemplates}</p> : null}
          <label>
            {W.purpose}
            <textarea rows={3} value={form.purpose} onChange={(e) => set({ purpose: e.target.value })} />
            <span className="m1-help">{W.purposeHelp}</span>
          </label>
          <label>
            {W.outcome}
            <textarea rows={2} value={form.outcome} onChange={(e) => set({ outcome: e.target.value })} />
            <span className="m1-help">{W.outcomeHelp}</span>
          </label>
        </>
      ) : null}

      {stepId === "charter" ? (
        <>
          <fieldset className="m1-fieldset">
            <legend>{W.charter}</legend>
            {lists.charter_templates.map((t) => (
              <label key={t.id} className="m1-choice">
                <input
                  type="radio"
                  name="charter"
                  checked={form.charter_template === t.id}
                  onChange={() => set({ charter_template: t.id })}
                />
                <span>
                  <strong>{t.name}</strong>
                  <span className="m1-help">{t.description}</span>
                </span>
              </label>
            ))}
          </fieldset>
          <CharterPaper
            purpose={form.purpose}
            outcome={form.outcome}
            templateName={chosen?.name ?? ""}
            approver={form.approver}
          />
        </>
      ) : null}

      {stepId === "people" ? (
        <>
          <label>
            {W.seats}
            <select value={form.seats} onChange={(e) => set({ seats: Number.parseInt(e.target.value, 10) })}>
              {Array.from({ length: lists.seats.max - lists.seats.min + 1 }, (_, i) => lists.seats.min + i).map((n) => (
                <option key={n} value={n}>
                  {n === 1 ? W.seatsSolo : W.seatsMany(n)}
                </option>
              ))}
            </select>
          </label>
          <fieldset className="m1-fieldset">
            <legend>{W.length}</legend>
            {[...lists.time_presets_minutes.map(String), CUSTOM].map((c) => (
              <label key={c} className="m1-choice">
                <input
                  type="radio"
                  name="length"
                  checked={form.lengthChoice === c}
                  onChange={() => setForm((f) => withLength(f, c, f.customLength, lists))}
                />
                <span>{c === CUSTOM ? W.custom : W.minutes(Number.parseInt(c, 10))}</span>
              </label>
            ))}
            {form.lengthChoice === CUSTOM ? (
              <label>
                {W.customLabel}
                <input
                  type="number"
                  inputMode="numeric"
                  min={lists.custom_length_minutes.min}
                  max={lists.custom_length_minutes.max}
                  value={form.customLength}
                  onChange={(e) => setForm((f) => withLength(f, CUSTOM, e.target.value, lists))}
                />
              </label>
            ) : null}
          </fieldset>
          <fieldset className="m1-fieldset">
            <legend>{W.split}</legend>
            <div className="m1-split">
              {(["briefing", "individual", "together"] as const).map((part) => (
                <label key={part}>
                  {W.splitPart[part]}
                  <input
                    type="number"
                    inputMode="numeric"
                    min={lists.min_stage_minutes}
                    value={form.split[part]}
                    aria-describedby="split-check"
                    onChange={(e) => set({ split: { ...form.split, [part]: e.target.value } })}
                  />
                  <span className="m1-help">{W.splitMinutes}</span>
                </label>
              ))}
            </div>
            <p id="split-check" role={splitMsg || lengthMsg ? "alert" : "status"} className={splitMsg || lengthMsg ? "state state-error" : "n-muted"}>
              {lengthMsg ?? splitMsg ?? W.splitOk(lengthOrZero(form))}
            </p>
          </fieldset>
        </>
      ) : null}

      {stepId === "people" ? (
        <fieldset className="m1-fieldset">
          <legend>{W.names}</legend>
          {(["named", "choice", "anonymous"] as const).map((v) => (
            <label key={v} className="m1-choice">
              <input type="radio" name="names" checked={form.names === v} onChange={() => set({ names: v })} />
              <span>
                <strong>{W.namesOptions[v].label}</strong> <span className="m1-help">{W.namesOptions[v].help}</span>
              </span>
            </label>
          ))}
          <p className="m1-help">{W.namesNote}</p>
        </fieldset>
      ) : null}

      {stepId === "north" ? (
        <>
          <label className="m1-choice">
            <input
              type="checkbox"
              checked={form.practice}
              disabled={!north.industry_practice_available}
              onChange={(e) => set({ practice: e.target.checked })}
            />
            <span>{W.northPractice}</span>
          </label>
          <label className="m1-choice">
            <input
              type="checkbox"
              checked={form.library}
              disabled={!north.problem_library_available}
              onChange={(e) => set({ library: e.target.checked })}
            />
            <span>
              {W.northLibrary}
              {north.problem_library_available ? <span className="m1-help">{W.northOnOffer(north.problem_count)}</span> : null}
            </span>
          </label>
          {!north.problem_library_available && !north.industry_practice_available ? (
            <div className="n-empty">
              <p className="ebody">{north.message ?? W.northNothing}</p>
            </div>
          ) : null}
        </>
      ) : null}

      {stepId === "video" ? (
        <fieldset className="m1-fieldset">
          <legend>{W.video}</legend>
          {lists.briefing_video_options.map((v) => (
            <label key={v} className="m1-choice">
              <input type="radio" name="video" checked={form.video === v} onChange={() => set({ video: v })} />
              <span>{W.videoOptions[v] ?? W.videoOther}</span>
            </label>
          ))}
          <p className="m1-help">{W.videoNote}</p>
        </fieldset>
      ) : null}

      {stepId === "approver" ? (
        <>
          <label>
            {W.approver}
            <input type="text" value={form.approver} onChange={(e) => set({ approver: e.target.value })} />
            <span className="m1-help">{W.approverHelp}</span>
          </label>
          <fieldset className="m1-fieldset">
            <legend>{m1Lean.signers.legend}</legend>
            {([1, 2] as const).map((n) => (
              <label key={n} className="m1-choice">
                <input type="radio" name="signers" checked={form.signers === n} onChange={() => set({ signers: n })} />
                <span>{n === 1 ? m1Lean.signers.one : m1Lean.signers.two}</span>
              </label>
            ))}
            <p className="m1-help">{m1Lean.signers.help}</p>
          </fieldset>
        </>
      ) : null}

      {stepId === "review" ? (
        <>
          <p>{W.reviewIntro}</p>
          <dl className="m1-review">
            <dt>{m1.labels.purpose}</dt>
            <dd>{form.purpose.trim() || W.noValue}</dd>
            <dt>{m1.labels.outcome}</dt>
            <dd>{form.outcome.trim() || W.noValue}</dd>
            <dt>{m1.labels.charter}</dt>
            <dd>{lists.charter_templates.find((t) => t.id === form.charter_template)?.name ?? W.noValue}</dd>
            <dt>{m1.labels.seats}</dt>
            <dd>{form.seats === 1 ? W.seatsSolo : W.seatsMany(form.seats)}</dd>
            <dt>{m1.labels.length}</dt>
            <dd>{W.minutes(lengthOrZero(form))}</dd>
            <dt>{m1.labels.split}</dt>
            <dd>
              {W.splitPart.briefing} {form.split.briefing}, {W.splitPart.individual} {form.split.individual},{" "}
              {W.splitPart.together} {form.split.together}
            </dd>
            <dt>{m1.labels.practice}</dt>
            <dd>{form.practice ? W.yes : W.no}</dd>
            <dt>{m1.labels.library}</dt>
            <dd>{form.library ? W.yes : W.no}</dd>
            <dt>{m1.labels.video}</dt>
            <dd>{W.videoOptions[form.video] ?? W.videoOther}</dd>
            <dt>{m1.labels.names}</dt>
            <dd>{W.namesOptions[form.names].label}</dd>
            <dt>{m1.labels.approver}</dt>
            <dd>{form.approver.trim() || W.noValue}</dd>
          </dl>
          {!purposeOk ? <p className="n-muted">{W.needPurpose}</p> : null}
          {purposeOk && (badLength || splitMsg) ? <p className="n-muted">{lengthMsg ?? splitMsg}</p> : null}
          <p className="m1-actions">
            <button type="button" className="n-btn primary" onClick={() => void save()} disabled={!canSave}>
              {busy ? W.saving : W.save}
            </button>
            {savedId && !unsaved ? (
              // M1-P02: the saved draft leads on to the page where "Start the room" is (the Next button ends here)
              <Link className="n-btn primary" to={`/modules/m1_intent/sessions/${encodeURIComponent(savedId)}`}>
                {m1Room.continueToStart}
              </Link>
            ) : null}
            <Link className="n-btn" to="/modules/m1_intent">
              {W.toHome}
            </Link>
          </p>
          {savedId ? (
            <>
              <div className="m1-template">
                <label>
                  {W.templateName}
                  <input type="text" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
                </label>
                <button type="button" className="n-btn" onClick={() => void makeTemplate()} disabled={busy || templateName.trim() === ""}>
                  {W.saveTemplate}
                </button>
              </div>
              {confirmDelete ? (
                <p className="m1-actions" role="group" aria-label={W.deleteSure}>
                  <span>{W.deleteSure}</span>
                  <button type="button" className="n-btn" onClick={() => void remove()} disabled={busy}>
                    {W.deleteYes}
                  </button>
                  <button type="button" className="n-btn" onClick={() => setConfirmDelete(false)}>
                    {W.deleteNo}
                  </button>
                </p>
              ) : (
                <p>
                  <button type="button" className="n-btn" onClick={() => setConfirmDelete(true)}>
                    {W.delete}
                  </button>
                </p>
              )}
            </>
          ) : (
            <p className="n-muted">{W.saveFirst}</p>
          )}
        </>
      ) : null}

      {error ? (
        <p role="alert" className="state state-error">
          {error}
        </p>
      ) : null}
      {notice ? (
        <p role="status" className="state n-muted">
          {notice}
        </p>
      ) : null}
    </WizardFrame>
  );
}
