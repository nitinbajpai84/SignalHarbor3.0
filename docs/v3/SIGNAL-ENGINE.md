# Signal engine: a decision schema that fires

Plan: https://claude.ai/artifact/XnUEvbsi8nJMwUh7cPUZDB. First library: the five signals of UC01 (docs/v3/use-cases/UC01-CAPITAL-CALL.md).
Code: `sh_platform/v1/v3_signals.py`, `v3_signals_routes.py`, `v3_signals.permissions.yaml`. Library: `packs/family_office/1/signals/*.yaml`.

## What a signal is
One row of a use case: **what arrives or already exists -> the signal Harbor catches -> the one person who acts, and how little they do.**
It is declared, not coded. It names its inputs, a condition, the role that acts and the one thing they do. When it fires it becomes an Action card
for that role, carrying its receipts (figure versions, quoted document lines, the signed rule). Pack signals are suggestions; the office edits,
replaces or switches them off. Nobody is ever named in a signal, only a role from `role_builds.yaml`; the person is whoever holds that job in the office.

## When the engine runs
| Event | Source |
|---|---|
| `file_arrived` | a PDF that loaded (v3_pdf.load_files calls `on_document`), with `kind` (the layout name as a slug, e.g. `capital_call_notice`) and `doc` ({field: {value, page, quote}}) |
| `run` | the end of every chain (A, B, C, M ...) (`on_run`) |
| `action_done` | a person acted on a card: the signals that follow it start, with the same document and facts |
| `schedule` / `date_passed` | the daily tick (`tick`, once a day per office from the scanner thread). `date_passed` signals need `items` from whatever watches dates |
| `figure_changed` | a caller passes `{"trigger": "figure_changed", "figure": id}` |

Each fired signal is idempotent: the same signal for the same subject fires once (also after the card was acted or dismissed).
A signal whose input is not there yet is skipped with the reason (never guessed); `evaluate()` returns `{fired, skipped}`.

## The yaml
```yaml
suggestion: true                      # pack signals are suggestions; an office file with the same id overrides key by key
id: uc01-bank-changed
title: Bank details changed, payment held
pain_points: [PP-02]                  # ids in painpoints_sample.yaml
trigger: {on: file_arrived, kind: capital_call_notice}   # on: file_arrived | figure_changed | date_passed | schedule | run | action_done
inputs:                               # what the condition may read
  - {kind: doc, fields: [fund, bank_account, call_no]}    # document fields, each with page and quote -> names doc.fund ...
  - {kind: figure, id: standing_instructions, as: si, by: {fund: doc.fund}}   # a figure (or the recipe it is built from: recipe: cash_by_entity); `by` picks the one row
  - {kind: rule, id: changed_bank_details, as: callback_rule}                 # a signed office rule
let: {gap: a - b}                     # optional named numbers, in order; usable in condition and message
condition: last4(doc.bank_account) != last4(si.account)
subject: "{doc.fund} call {doc.call_no}"      # the thing it is about; with the signal id it is the once-only key
severity: problem                     # info | needs | problem (colours: docs/v3/COLOURS.md)
route_to: ops_lead                    # a role id in role_builds.yaml
action: {verb: call_back, options: [Record the call-back]}   # verb: log | record | approve | call_back | see
hold: {blocks: prepare_payment, scope: "{doc.fund}", until: the call-back is recorded}   # exception signals only
message: "Bank details for {doc.fund} changed since {si.since}: account ending {si.account} on file ... The payment is held."
evidence: [doc.bank_account, si, callback_rule]   # which receipts go on the card (default: all inputs)
```
Conditions: numbers, text, `+ - * /`, `== != < <= > >= in`, `and or not`, dotted names, and `abs min max round last4 num same_fund`.
They are parsed with `ast`, checked against a whitelist and walked by the engine; there is no `eval`. `same_fund(a, b)` ignores case, punctuation
and words such as "L.P." and "Fund"; if the names still differ it asks the two-model check (v3_judge `fund_match`), and a pair that disagrees is not the same.
Messages take `{name}` or `{name:,.0f}`.

## The five UC01 signals
| File | Row of the story | Fires when | Role, action | Numbers it must give |
|---|---|---|---|---|
| uc01-call-arrives | 1 | a capital call notice loads | ops_clerk, log | USD 1,250,000 due 23 Oct |
| uc01-call-fits | 2 | the call is logged (action_done) and amount <= commitment - called | fund_accountant, record | unfunded 2,750,000 |
| uc01-cash-shortfall | 3 | the record is done and amount + buffer > cash | cfo, approve (Approve / Change / Fund from another entity) | short 270,000, convert SGD 361,800 |
| uc01-bank-changed | 4, red | the account on the notice differs from the standing instructions | ops_lead, call_back (a note is required), **holds prepare_payment** | 2209 -> 4471 |
| uc01-paid-matched | 5 | a bank statement line matches the approved call's amount and date | fund_accountant, record | call 7 paid |

## Cards, holds and the record
- `fired.json` (per office, `<company>/v3/signals/`) holds every card: status `open | acted | dismissed`, who and when, the receipts (`evidence`), the hold.
- A card is an Action card on the Desk (`H.desk()["needs"]`, kind `signal`, severity colour from COLOURS.md).
- `held(plane, "prepare_payment", fund)` lists the open cards that hold that action. Whatever prepares a payment must refuse while it is not empty.
  The hold lifts when the card is acted (the call-back note is mandatory); dismissing it as wrong also lifts it and counts as a miss.
- Record per signal and office: `fired`, `acted` (hit), `dismissed` (miss), `open`, `hit_rate = acted / (acted + dismissed)`. A signal that keeps missing is a candidate to edit or switch off.

## Facts
The condition reads facts, in this order: `signals.PROVIDER(plane, kind, ref, event)` if set; `event["facts"]`; the figure record's current version `value`
(v3_figstore); the signed rule from `e3_rules.current`. The figure record does not hold values yet, so the chain steps that build a figure's ready table should
pass them as `facts` (or set PROVIDER). That wiring is the next step.

## Adding a signal
1. Copy a file in `packs/family_office/1/signals/` (pack suggestion) or into `<company>/v3/signals/office/<id>.yaml` (the office's own; `disabled: true` switches a pack signal off).
2. Pick the trigger, list the inputs, write the condition and the message in plain words, name the role and the one action.
3. `GET /api/v3/signals` shows it with `error` if the definition cannot run (unknown role, unreadable condition). Add a test with the exact numbers.
4. Judge it by its record: a signal earns its place when its hit rate stays high.

## Next (not built): Harbor drafts a signal from a repeated human action
When a person does the same thing twice after the same kind of arrival (the `about` mark Harbor already keeps for a repeated step, v3_skills.write_skill),
Harbor drafts a signal yaml: trigger from the file kind, inputs from the figures the person looked at, condition from what they compared, route_to from their
role, action from what they did. It is kept as a suggestion with status waiting; a person admits it (signed, version + 1) or rejects it, exactly like an office skill.

## API
- `GET /api/v3/signals` the library with stats; `GET /api/v3/signals/fired?status=` the cards with receipts;
  `POST /api/v3/signals/{fired_id}/act {choice?, note?, dismiss?}` (403 unless the card's role, or a company admin, when jobs are set; 409 with a plain message when the choice or the note is missing).
