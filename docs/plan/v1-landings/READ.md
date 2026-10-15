# READ: agents search and read the documents

1. `sh_platform/v1/doc_index.py`: per-company SQLite FTS5 index at `data/<company>/index/docs.sqlite` (passages of 800-1,200 characters, BM25, line numbers as the source viewer counts them). Built lazily and idempotently on first use of a file; re-indexed when its size or time changes.
2. `sh_platform/v1/doc_tools.py`: `search_documents(query, max)` and `read_document(file, from_line, to_line)`, registered per reply. Only files ticked for the conversation that the person may read (C4 `selected`, K1, G1); at most 6 calls a reply; read capped at 60 lines or 3,000 characters; results are strings marked as quoted document text; figures in them are appended to the context's `facts` so the reply guard lets the model repeat them.
3. Wired into North (`i6_chat.ask`), Span (`a1_chat.ask`), Flow (`f1_chat.ask`), Lumen (`c3_chat.ask`) with `DT.PROMPT_LINE`; the JSON reply contract is unchanged.
4. North's reply to a dropped document starts with "I read X: N pages/lines; it covers ...; it defines ..." (`i6_chat._ack`, local digest, no model call).
5. Chips under North's reply (`ui/src/v1/i6/SourceChips.tsx`, one line added in `ConversationPage.tsx`) open `/centre/build/:iid/source?file=&line=`; turn records carry `sources`.

Not touched: k1_classify, ocr_local, c4_library. The index is built on first search, not at upload (no hook added in c4_library); the first search of a big PDF pays the read once.
Limits: arguments must all be passed (the registry demands exact keys), so the prompt says "pass max"; the chips are the passages whose file the reply names, else what was read on purpose.

## Test
- `SH_MODEL_PROVIDER=off python -m pytest tests/v1/test_doc_read.py` (8 tests: index idempotent, unticked/restricted/private never returned, caps, six calls, facts, stub model with tool calls, acknowledgement).
- By hand: tick `13-access-policy.md` in the Context box of a North conversation, ask "what does the access policy say about restricted files?"; the reply quotes a line and shows a chip; click it to open the document at that line. Drop a document in the chat: North opens with "I read ...".
