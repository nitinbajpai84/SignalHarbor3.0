"""What Lens's block shows (M2-AGENTS): the measures and suggestions to refine, what it still needs to ask, and its
three plain sentences (what it did, what it proposes next, what it needs). Pure functions over what the asker may see:
the caller passes only visible measures, so nothing here can leak a restricted one. Every number is a count of records."""
from modules.m2_baseline.domain.triage import ROLES, missing_owners

ROLE_WORDS = {"business": "the business owner", "data": "the data owner", "process": "the process owner"}


def refine_items(kpis: list[dict], suggestions: list[dict], titles: dict[str, str], label: str) -> list[dict]:
    """The measures on the list (what a person may use, edit or tell Lens to change), then the suggestions with their drafts."""
    mine = [{"id": k["id"], "name": k["name"], "kind": "measure", "definition": k["definition"], "label": None,
             "problems": [titles[p] for p in k["problem_ids"] if p in titles]} for k in kpis]
    sug = [{"id": s["id"], "name": s["name"], "kind": "suggestion", "definition": s.get("definition"), "label": label,
            "problems": [titles[p] for p in s["problem_ids"] if p in titles]} for s in suggestions]
    return mine + sug


def asks(kpis: list[dict], attempted: set[str], drafts: dict | None = None) -> list[dict]:
    """Everything Lens still needs from the business, in the order it asks: per measure its definition (once Lens has tried
    and found nothing), the three owners, who produces the data, how it is gathered, then the pack's own questions. Only the
    gaps: a field Lens filled from a document is a draft to review, not a question. A likely owner Lens read is offered as `draft`."""
    out = []
    for k in kpis:
        def add(field, text, role=None, question_id=None, draft=None):
            out.append({"id": ":".join(x for x in (k["id"], field, role or question_id or "") if x), "kpi_id": k["id"], "kpi_name": k["name"],
                        "field": field, "role": role, "question_id": question_id, "text": text, "draft": draft})
        n = k["name"]
        if k["definition"]["mark"] == "unknown" and k["id"] in attempted:
            add("definition", f"What does \"{n}\" mean in your company? Write it in your own words.")
        likely = ((drafts or {}).get(k["id"]) or {}).get("owner")
        for role in ROLES:
            if role in missing_owners(k):
                if role == "business" and likely:
                    add("owner", f"Is {likely['value']} the business owner for \"{n}\"? I read it in {likely['from'] or 'your documents'}.", role=role,
                        draft={"value": likely["value"], "from": likely["from"]})
                else:
                    add("owner", f"Who is {ROLE_WORDS[role]} for \"{n}\"?", role=role)
        if k["producer"]["mark"] == "unknown":
            add("producer", f"Who produces the data for \"{n}\"?")
        if k["gathered"]["mark"] == "unknown":
            add("gathered", f"How is the data for \"{n}\" gathered?")
        for q in k["questions"]:
            if q["answer"]["mark"] == "unknown":
                add("question", q["question"], question_id=q["id"])
    return out


UNSURE = {"nothing": "no document or industry text says what it means", "unreachable": "I could not reach the model",
          "no_model": "no model is set up to read your documents"}


def sentences(*, pack_available: bool, label: str, problems: int, suggested: int, measures: int, drafted: int, pending: int,
              failed: int, nothing: int, available: bool, locked: bool, asking: str | None, documents: int = 0,
              unsure: list[tuple[str, str]] = ()) -> dict:
    """{did, next, need}: Lens's three plain sentences. `documents` counts the company's documents Lens may read (restricted
    ones are not counted); `unsure` is [(measure name, outcome)] for what it could not fill."""
    s = "s" if documents != 1 else ""
    read = f"I read {documents} document{s} you gave me." if documents else "You have not given me any documents yet."
    if not pack_available and not measures and not documents:
        did = "I have no industry knowledge for this company yet and no documents to read, so I have nothing to suggest. I will have to ask you."
    elif not pack_available and not measures:
        did = f"I have no industry knowledge for this company yet, so I have no measures to suggest. {read} Add a measure and I will draft it from them."
    else:
        did = (f"I looked at your {problems} charter problem{'s' if problems != 1 else ''} and suggested {suggested} "
               f"measure{'s' if suggested != 1 else ''} from what others in the industry usually track.") if suggested else \
              f"All the measures I could suggest for your {problems} charter problem{'s' if problems != 1 else ''} are on your list."
        did += f" {read}"
        done = min(drafted, suggested + measures - pending)  # D5: a pack wording already on a measure Lens is still drafting is not "filled"
        if done > 0 or (not pending and suggested + measures):
            did += f" I filled a definition for {max(done, 0)} of {suggested + measures}."
        if pending:
            did += f" I am still drafting {pending}."
        if unsure:
            did += " I am unsure about " + "; ".join(f"{n} ({UNSURE.get(o, o)})" for n, o in list(unsure)[:3]) + (" and more." if len(unsure) > 3 else ".")
    if failed:
        did += f" I could not reach the model for {failed} measure{'s' if failed != 1 else ''}."
    if locked:
        nxt = "This baseline is signed, so nothing can change. Ask me anything about it."
    elif not available and (suggested or measures):
        nxt = "No model is set up for your company, so I can only show what the industry usually uses. Use or edit the definitions."
    else:
        nxt = "Use a definition, edit it, or tell me what to change. Then answer my questions, one at a time."
    if locked:
        need = "Nothing: this baseline is signed."
    elif failed:
        need = f"I could not reach the model for {failed} measure{'s' if failed != 1 else ''}: please try again."
    elif asking:
        need = asking
    elif nothing:
        need = f"I found nothing that says what {nothing} measure{'s' if nothing != 1 else ''} mean{'' if nothing != 1 else 's'}: please write the definition."
    else:
        need = "Nothing right now."
    return {"did": did, "next": nxt, "need": need}
