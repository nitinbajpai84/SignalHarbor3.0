import { m2Pre } from "../copy";
import PersonalNotice from "./PersonalNotice";

export interface WaitingDoc {
  doc_id: string;
  title: string;
  personal_words: string[];
  restrict_path: string;
}

/** "N documents wait for your decision before I can use them", each with the words found and the two buttons. Shown to the company admin only. */
export default function WaitingDocuments({ baselineId, docs, onDecided }: { baselineId: string; docs: WaitingDoc[]; onDecided: () => void }) {
  if (docs.length === 0) return null;
  return (
    <section aria-label={m2Pre.waiting(docs.length)}>
      <p role="status"><strong>{m2Pre.waiting(docs.length)}</strong></p>
      {docs.map((x) => (
        <PersonalNotice key={x.doc_id} baselineId={baselineId} docId={x.doc_id} title={x.title} words={x.personal_words} restrictPath={x.restrict_path} onDecided={onDecided} />
      ))}
    </section>
  );
}
