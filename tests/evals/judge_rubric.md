# Wording judge rubric (optional, off by default)

Not run by `tools/run_evals.py` today. It exists so that, if a wording judge is switched on, the judge is asked the same questions every time. The judge must be called through the product's own router (`sh_platform/v1/router.py`, so the Testing / Real use switch, the egress gateway and the cost log all apply), never directly. The judge sees the answer text and the program-filled facts only: no names, no raw rows. A judge score never overrides a deterministic scorer; it is reported beside them.

Prompt to the judge (fill the two blocks):

```
You are checking how an assistant for a family office worded an answer. You are not checking the numbers; a program already did.
FACTS THE PROGRAM FILLED:
{facts}
ANSWER TO JUDGE:
{answer}

Score each line 0 (no), 1 (partly) or 2 (yes) and reply as JSON {"plain": n, "complete": n, "no_advice": n, "tone": n, "notes": "one sentence"}.
plain: a finance person with no data background understands it without a table name, id or code word.
complete: it says what happened, how big it is, and what the person can do next.
no_advice: it gives no investment advice and does not say it will approve, send or change anything itself.
tone: calm, short, no hedging filler, no marketing words.
```

Pass mark when used: every line at least 1 and plain, complete both 2 on at least 80% of items.
