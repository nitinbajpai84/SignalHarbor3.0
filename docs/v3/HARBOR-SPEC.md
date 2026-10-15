# Signal Harbor 3.0: Harbor, one thread, three decisions (local prototype)

This folder is a LOCAL copy of Repo 1.0. No git, no push. Reuse the 2.0 engine (sh_platform/v1, agents, pipelines, guards); add a thin 3.0 layer.
Design (read the artboards' intent, match wording): https://claude.ai/artifact/MAWLiABUiUvV5MQNRyDXku — local copies of the artboards:
D:/Temp/claude/D--Projects-01-Project-Signal-Harbor/7fe02e29-00ec-496a-a5ad-5bbc0d58c219/scratchpad/sh3/project/*.dc.html
(Main = Desk, Thread, Decision = Decision 2 review, Monthly = files and exceptions, Workbench).

Run: `python tools/serve_test.py --port 8630 --data-root D:/Temp/sh3-data --scheduler` (unset DATABASE_URL/REDIS_URL; simple mode).
Never touch ports 8530/8811/8812, D:/Temp/sh-local, or "Repo 1.0".

## The flow (one person: Anita, head of data, company "evergreen")
1. Person types an intent on the Desk -> a thread is created -> Harbor (North underneath) drafts the brief.
2. **Decision 1** "Is this what you want?": the brief (question, files, read by, refresh, cases when). One Confirm. Harbor signs/hands over on the person's behalf (single-signer office).
3. Harbor works with no person: architecture, design pack, approve pack (as the data owner), intake of the dropped files, mappings accepted when confident, load, run on a copy, compare with last month. Each step becomes a chip event.
4. **Decision 2** "Here is what I understood": files -> where each goes (reused/new), confidence, and the open questions (from Span's questions / low-confidence mappings) as inline one-click answers. One "This is right, carry on".
5. **Decision 3** "Numbers match. Go live?": per-entity check vs the benchmark/answer key, breaks listed. Go live -> live run, Lumen starter board accepted and published, morning note.
6. Monthly: files dropped later -> run -> only exceptions become "Needs you" cards.
Anything that fails becomes a question card in the thread (never a silent failure).
REUSE: docs/test/uc-live/uc6-scripts/*.py already chain every 2.0 API call in order (m1_01 north ... r3_m1_07 approve, r3_builder, r3_run, r3_bench, r3_lumen, r3_tiles). Call the same functions/routes in-process.

## API contract (all under /api/v3, company from the session, permissions file v3.permissions.yaml, routes in sh_platform/v3_routes.py or sh_platform/v1/v3_*_routes.py so discovery picks them up)
- `GET /api/v3/desk` -> `{needs:[Card], note:{text, figures:[{label,value,change}]}|null, threads:[ThreadSummary], files:{arrived,recognised,waiting}}`
- `POST /api/v3/threads {text}` -> `Thread`
- `GET /api/v3/threads` -> `{threads:[ThreadSummary]}`; `GET /api/v3/threads/{tid}` -> `Thread`
- `POST /api/v3/threads/{tid}/say {text}` -> `Thread` (free talk; routed to the right specialist; reply appended)
- `POST /api/v3/threads/{tid}/decide {n:1|2|3, answer:"confirm"|"carry_on"|"go_live"|"not_yet", answers?:{qid:value}}` -> `Thread`
- `POST /api/v3/files` multipart or `{name,data(base64)}`, and the drop folder `<data_root>/<company>/dropbox/` scanned every 30 s -> `GET /api/v3/files` -> `{files:[{name,arrived_at,status:"recognised"|"loaded"|"waiting"|"question",source,thread}]}`
- `GET /api/v3/threads/{tid}/workbench` -> `{steps:[{n,at,agent,action,ok,run_id?,detail}], tables:[{layer,name,rows,state:"reused"|"new"}], rules:[str]}`
Types:
- `ThreadSummary {id,title,stage:"drafting"|"decision1"|"working"|"decision2"|"decision3"|"live"|"question", needs:int, next_run?:str}`
- `Thread = ThreadSummary + {events:[Event], decision:Decision|null, asked:int, harbor_steps:int}`
- `Event {at, kind:"person"|"harbor"|"chips"|"decision_done"|"question", text?, chips?:[str], by?}`
- `Decision {n, title, brief?:{question,files:[str],read_by,refresh,cases_when}, files?:[{name,read_as,goes_to,state,confidence}], questions?:[{id,text,options:[str],assumed?}], checks?:[{label,value,ok,note}], summary?:str}`
- `Card {kind:"decision"|"exception"|"question", thread, title, text, actions:[{label,answer}]}`

## UI (ui/src/v3/*, routes /v3/desk, /v3/thread/:id, /v3/thread/:id/review, /v3/files, /v3/thread/:id/workbench; after sign-in, Anita lands on /v3/desk)
Look: the canvas (warm paper #F4F0E8, ink #1B1915, green #1F6F5B, amber #B8641F, Fraunces headings, Instrument Sans body, JetBrains Mono numbers).
API client: ui/src/v3/api.ts (owned by the Desk/Thread agent; others import its types).

## Added 14 Oct: day one, the industry model, connections, trust (contracts for the build wave)

**Day one (how a new office is set up).** 1 pick the industry pack (family_office, insurance, ...) -> the office starts with that pack's **industry model**; 2 connect sources (drop folder, mailbox, SFTP, shared folder; database/API shown as "coming"); 3 Harbor reads the history files and maps every column to the industry model, asking only about what it cannot place; 4 people and who decides; 5 first thread. Same pack = same model for every family office; each office's additions live in its own data plane and never leak; an addition may be proposed back to the pack only by a reviewer, with no client data.

**Industry model** = `packs/<industry>/1/model.yaml`: `objects: [{name, label, table, properties: [{name, label, type, synonyms: [str], derived?: str}], relations: [{to, label}]}]`. Built from the pack's glossary/column_synonyms and docs/v2/family-office-data-model-slim.dbml for family_office; insurance gets its own (Policy, Claim, Premium, Reserve, Reinsurer, Broker, Product, Policyholder). Office layer: `<data_root>/<company>/v3/model.json` (additions, admissions, versions).

API (each group adds its own `sh_platform/v1/v3_<area>_routes.py` + `v3_<area>.permissions.yaml`):
- `GET /api/v3/model` -> `{pack:{id,label,version}, objects:[{name,label,table,from:"industry"|"office"|"proposed",count,properties:[{name,label,column?,derived?}],relations:[{to,label}]}], coverage:{pct,unmapped:[str]}, proposals:[{id,text,object,property?}], versions:[{v,at,by,change}]}`
- `POST /api/v3/model/proposals/{pid} {answer:"admit"|"reject"}` -> model; `GET /api/v3/packs` -> `{packs:[{id,label,objects:int,questions:int}], current}`
- `GET /api/v3/language` -> `{words:[{word,means,by,used}], corrections:[{id,text}], golden:[{q,a,by}], taught:[{name,books,on,version}]}`; `POST /api/v3/language/words {word,means}`; `POST /api/v3/language/corrections/{id} {answer:"admit"|"reject"}`
- `GET /api/v3/people` -> `{people:[{name,role:"decides"|"does"|"reads"}], second_signer:bool, autonomy:[{thread,level:"assist"|"auto"|"silent"}], ask_rules:[{id,text,on,value?}], usage:{questions,builds,mode:"testing"|"real"}}`; `POST /api/v3/people/autonomy {thread,level}`
- `GET /api/v3/runs` -> `{runs:[{run_id,thread,kind:"copy"|"live",started,files,checks_passed,checks_total,result,signed_by}]}`
- `GET /api/v3/connections` -> `{connections:[{id,kind:"folder"|"mailbox"|"sftp"|"http"|"database"|"api",name,target,schedule,last_pull,state:"ok"|"failing"|"coming"}]}` (wraps c5_connect; folder = the dropbox)
- `GET /api/v3/setup` -> `{steps:[{id,label,done,detail}], pack}`; `POST /api/v3/setup {pack}`
- `GET /api/v3/board` -> `{title,as_at,figures:[{label,value,change}],tiles:[...2.0 tile shape]}`; `POST /api/v3/ask {text}` -> `{answer,figure?,understood?,trace:[{kind,label}],used:[str]}`; `GET /api/v3/note` -> `{text,figures,history:[{at,headline}]}`
- `GET /api/v3/cases/{cid}` -> 2.0 case (Tally) reshaped: `{id,title,status,owner,due,thread,what,evidence:[{source,row}],steps:[{label,answer}],history:[{at,text}]}`

UI page files (one owner each; ui/src/v3/routes.tsx imports exactly these): desk/DeskPage, setup/WelcomePage, setup/StartPage, setup/SetupPage, thread/ThreadPage (all three decisions + working), files/FilesPage, board/BoardPage, board/AnswerPage, board/NotePage, case/CasePage, trust/OntologyPage, trust/ModelPage, trust/LanguagePage, trust/PeoplePage, trust/ProofPage, trust/WorkbenchPage, trust/ConnectionsPage. Routes: /v3/desk /v3/welcome /v3/start /v3/setup /v3/thread/:id /v3/files /v3/board /v3/ask /v3/note /v3/case/:id /v3/trust/{ontology,model,language,people,proof,workbench,connections}. Shared: v3/api.ts (types + calls above; DecisionFile.confidence is "high"|"medium"|"low"), v3/Frame.tsx (top nav Desk·Threads·Board·Files·Trust), v3/TrustTabs.tsx, v3/v3.css.

## Added 15 Oct: skills, the three centres and Knowledge (contracts for the build wave)

Design: canvas boards Build2, Knowledge (round 4), Action, Consume, ConsumePhone, Desk2 (round 2), SkillsHow, Skills, SkillNew (round 3), in
D:/Temp/claude/D--Projects-01-Project-Signal-Harbor/7fe02e29-00ec-496a-a5ad-5bbc0d58c219/scratchpad/sh3/project/. Catalogue: docs/v3/SKILLS-CATALOGUE.md.
Nav: Action · Build · Consume · Knowledge; logo = Desk. Routes (stubs exist): /v3/action, /v3/skill/:id (review a skill Harbor wrote),
/v3/build, /v3/build/:id (one use case), /v3/consume, /v3/knowledge, /v3/knowledge/skills. Every older /v3 route stays (never drop a page).

**Skills** (`skills/<id>/SKILL.md` front matter: id, name, goal, when, centre: intent|build|action|consume|knowledge, source: core|industry|office,
tier: fast|strong|tools, version, status: in_use|waiting|retired, from; body sections Inputs, Output, Steps, Tools, Checks, Never; `tests.jsonl`.
Office skills live in `<data_root>/<company>/skills/<id>/` and override a core one of the same id.)
- `GET /api/v3/skills` -> `{skills:[{id,name,goal,when,centre,source,tier,version,status,tested:{passed,total}|null,used:int,last_changed:{by,at}|null}]}`
- `GET /api/v3/skills/{id}` -> the row + `{inputs,output,steps:[str],tools:[str],checks:[str],never:[str],history:[{v,at,by,change}],why?:str,evidence?:[{at,text}],tests?:[{input,expected,got,ok}],cache?:{answers:int,golden:int}}`
- `POST /api/v3/skills/{id}/edit {field,value}` (a waiting skill only) ; `POST .../try` re-runs its tests ; `POST .../admit` (signs in the person's name, version+1, status in_use) ; `POST .../reject {reason}`
- `GET /api/v3/skills/usage?thread=<tid>` -> `{runs:[{at,skill,name,ms,ok,detail}]}` ; Thread gains `now: {skill,name,text} | null` while drafting or working
**Consume**
- `POST /api/v3/ask {text}` -> today's shape + `{cached:bool, ms:int, as_of:str|null}` (cache key: normalised question + data version = latest live run id)
- `GET /api/v3/consume` -> `{as_of, figures:[{label,value,change,stale}], watchlist:[{label,value,change,stale}], boards:[{id,title}], note:{headline}|null, reports:[{name,href}], golden:[{q}]}`
**Knowledge** (this company only; built from records: threads, signed briefs, files, people, entities, funds, ready figures, decisions)
- `GET /api/v3/knowledge` -> `{nodes:[{id,kind:"person"|"entity"|"fund"|"source"|"figure"|"usecase"|"decision"|"file",label,facts:[{text,source,at}]}], edges:[{from,to,label}], processes:[{title,lanes:[str],steps:[{lane,text}]}], things:[{name,count,new:bool}]}`
