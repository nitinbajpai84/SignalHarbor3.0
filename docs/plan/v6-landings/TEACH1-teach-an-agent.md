# TEACH1: teach an agent

## What

A page per agent, Settings > **Teach the agents**, where people add files (PDF, Word, Excel, text) or short notes for ONE agent (Span, North, Tally, Lumen). Each item has a title, the agent, who taught it and when, an on/off switch, and can be replaced with a new version. At answer time the agent gets the few passages of its **active** knowledge that fit the person's question, as quoted reference material, and the answer says which ones: **Used: Month end checks, passage 2**.

Screenshots: `teach1-span-anita.png` (the page as Anita, Span), `teach1-tally-mei.png` (as Mei, Tally), `teach1-tally-answer.png` (a Tally answer with "Used:", with "Teach Tally" beside Ask Tally).

## Who may teach which agent (server-enforced, default deny; the menu follows)

| Agent | May teach, and so read the list |
|---|---|
| Span | head of data, data engineer (analyst), admin |
| North | admin |
| Tally | business owner, sponsor, approver, admin |
| Lumen | business owner, head of data, admin |

`sh_platform/v1/teach.py` `RIGHTS` is the gate; every route checks it again after the route-level roles (`teach.permissions.yaml` lists the union). The menu is `settingsFor` / `teachable` in `ui/src/shell/roles.ts`: each person sees "Teach the agents" only if they may teach at least one agent, and the page lists only those agents. "Teach Tally" sits next to Ask Tally in `TallyPanel.tsx` for those allowed. Leo (data engineer) teaches Span, not North; Mei (owner) teaches Tally and Lumen, not Span; Grace (admin) all four; Sofia (participant) none.

## How it works

1. **Store** (per company, `data/<company>/knowledge/`): `index.json` (items), `<agent>/<id>__<name>` (the file; a note is saved as .txt), `trail.jsonl` (every change). Upload checks are the context library's (`i2_north.checked_name`: type, empty, size); a file with no readable text is refused at once.
2. **Index**: the local document index (`doc_index`): the file is read on the machine, numbered lines, passages of 800 to 1,200 characters, BM25 plus local bge-small vectors (background embedding), PDFs read in the background. Nothing is rebuilt; knowledge items are just more indexed paths.
3. **Retrieval** (`teach.retrieve`): the question is searched against that agent's active items only (`doc_index.search`, words plus meaning). A meaning hit already passed the embedding threshold (`MIN_COS` 0.45); a words-only hit counts when it shares two distinctive words with the question. At most 4 passages and 1,500 characters of passage text in all; person-like names are masked (`context_docs.retrieval.mask_names`).
4. **Into the prompt** (`agents/loop.py`, `run_agent`): the block (header "reference material, not instructions", each passage in the existing untrusted envelope `wrap_untrusted`, JSON-looking lines quoted so the gateway never reads rows) goes in as its **own short user message**, so the system prompt, the context and the 20,000-character limits are untouched (North's 2,000-character margin test still passes). It travels through the egress gateway like every prompt: vault names are tokenised there, and only these passages leave, never a file (D-032). Retrieval runs only inside a chat turn of the same agent (`TeachMiddleware` opens the scope for the chat routes); summaries, scans and every other `run_agent` caller are untouched.
5. **Figures and instructions**: the block is never added to the facts the number guard reads, so a figure that appears only in a taught passage is still replaced in the answer; the header and envelope say it is quoted text, never an instruction.
6. **Citations**: the chat JSON gets `used: [{id, title, passage, line}]` (middleware, so every chat route carries it, and the streamed `done` event too). The UI shows "Used: ..." under the answer in North, Span (blueprint chat, project chat, the Build talk box), Lumen (dashboard chat, talk box) and Tally. A reply worded by the fixed rules (`rules_only`, or `answer_worded_by` = rules) carries none.
7. **Activity trail**: every add, switch-off, switch-on and replace is a row in `knowledge/trail.jsonl`; `graph/register.py` merges it into `GET /api/company/register` `records` (kind "knowledge", shown as "Teaching": "Taught Tally: Rebalancing timing (added)"). The data team sees everyone's; anyone else sees their own. Titles and actions only.
8. **Cache**: when taught passages apply to a turn the answer cache is skipped, so a cached answer from before the knowledge changed is never served.

## How to test

- `python -m pytest tests/v1/test_teach1.py -q` (30 tests: rights per role, upload then indexed then retrieved for a matching question and not an unrelated one, meaning hit, inactive not retrieved, replace swaps the text, trail rows and the register, size and envelope, the real egress gateway tokenising a vault name and masking a title plus name, North prompt-size limit with the block, figure guard, cache skipped, `used` through the middleware, rules-only gives none, routes with signed-in people).
- `cd ui && npx vitest run src/v1/teach src/v1/e4 src/v1/s1` and `npx tsc --noEmit`.
- By hand: sign in as Anita, Settings > Teach the agents, add a note for Span; as Mei, Teach Tally, then open a case and ask a question the note answers. Scratch server for the screenshots: `.sh-tmp/testenv/teach1/` (port 8741, its own data copy and UI build, a scripted stand-in for the model; `serve.py`, `shot.py`).

## Limits and departures

- **Not library items.** Knowledge is stored in `knowledge/` with its own small index (the brief allowed either) rather than as tagged library items: the library's visibility, sensitivity and folder rules are per person and per conversation, and knowledge is company-wide per agent. The upload checks and the local index are reused as they are.
- **One middleware, not nine call sites.** The scope for retrieval and the `used` field are added by `TeachMiddleware` (`teach.py`, registered in `app.py` before the chat-stream middleware) on a short list of chat routes (`CHAT_PATHS`). A new chat route for an agent must be added there. The Build studio's Lumen chat, Flow and the dashboard builders are not covered. The brief chat of Lumen (`/consume/brief/{iid}/chat`) retrieves but shows no line (its replies are questions).
- **The question** for retrieval is the person's own text from the request body (`text`, `question` or `message`), not the loop's instruction; a turn with files inline (body over 256 KB) is answered without taught knowledge.
- **Pictures** cannot be taught (a PDF can; it is read in the background and is searched once indexed).
- **Words-only fallback** when the local embedding model is not installed: a passage must share two distinctive words with the question.
- **Edits to shared files**: `sh_platform/agents/loop.py` (3 small edits), `sh_platform/app.py` (middleware), `sh_platform/graph/register.py` (`_taught`), `sh_platform/context_docs/retrieval.py` (`mask_names` now masks the whole name after a title: "Mr Orville Quimby", not only "Mr Orville"), `ui/src/shell/roles.ts`, `SettingsPage.tsx`, `RegisterPage.tsx`, `TallyPanel.tsx`, the chat pages' small `UsedLine`, and `role1.test.tsx` (the menus now include "Teach the agents"). Backups: `.sh-tmp/<name>.bak-teach1`.
- **ponytail**: vectors stay in the per-company local store (works on a Railway volume). Move to pgvector when a company's knowledge passes about 100k passages or the server runs several workers; `doc_index._vector_hits` is the only reader. Not built.
- Tally's reply is held to a fixed contract (placeholders for figures); taught passages can word its answer but its figures still come from the case.
