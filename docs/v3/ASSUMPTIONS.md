# Assumptions made to resolve open decisions

On 16 Oct Nitin said to go ahead with the recommendations and record each one here. Each line can be reversed. To change one, edit it here and tell Harbor's builder; the "Where it lives" column says what to touch.

| # | Decision | Assumption taken | Why | Where it lives |
|---|---|---|---|---|
| A1 | FX forward confirmations have no table | Add one table to the company model, `fx_confirmations`. It holds trade reference, trade date, value date, currency bought, amount bought, currency sold, amount sold, rate, counterparty, source document and page. | A confirmation is a fact the office must keep and match against the trading desk. Squeezing it into trades loses the second currency leg. | the company model contract (DBML) and the loader; the v3_pdf FX layout loads into it |
| A2 | No home for "which statement we expect from each fund each month" | Add `expected_statements`: fund, period end, due date, frequency, source. It is filled from the commitments and the fund terms the office drops, or from a schedule the person confirms once. | A missing statement can only be counted against what was expected. Working it out from capital calls is not reliable. | company model contract; Span reads it for "missing statements" |
| A3 | Figures stated in an issued report (for example the report total) | Answer them from what Harbor read off the report (`extracted_fields`), always naming the report and its date. Do not create a separate issued-report history yet. | No new table is needed, and the answer stays traceable to the page. | `v3_figures.report_total` |
| A4 | A participant who raised a brief accepts North's drafts on their own brief | Keep it. Only the raiser may do this, only on their own unsigned brief, and only for the intent of work and the process map. The signer still confirms everything at signing. | Without it, a person who may not sign is stuck. The 2.0 control (only a signer makes it binding) is unchanged. | `v3_signoff.accept_drafts` |
| A5 | Sign of cash amounts | Money in is positive and money out is negative. With Debit/Credit columns: amount = credit − debit. | This is how the office's bank files already show it. The model's column did not say. | `e0c_load` debit/credit fold |
| A6 | Which line of a report is "the total" | A line labelled "Total" (or "Total (CCY)") is the report total. If two different totals exist in one currency, Harbor does not answer from the report. | Simple, and it holds for the office's report layout. A model-chosen line is harder to audit. | `v3_figures.report_total` |
| A7 | Same question, different answer each round | A figure is built from a written recipe when the pack has one, not redesigned by the model each run. A model design that passes its checks is saved and reused for the next build of the same figure. | Repeatability and audit: the same data must give the same number. See "Why answers vary" below. | `packs/family_office/1/` recipes; the design store |
| A8 | Which tables a figure may read | Each recipe names the tables its figure may read. For example, net worth reads positions or valuations, never commitments. A design that reads other tables is refused. | This stops two wrong figures seen in testing: "net worth" built on commitments, and a break shown as a plain sum of movements. | the pack recipes; the plan check |

## Why answers vary from round to round

Today Span asks the model to write the SQL for every figure, fresh, in every build. Four things make this vary:
1. **The design differs each time.** The model writes different SQL on each call, so it may read a different table, a different join, or a different grouping.
2. **A failed design call falls back to the simple rules.** When the call fails or times out, the design falls back to plain rules ("Span's design call failed; rules only"). Those can only add things up, which is how a break became a plain sum.
3. **The inputs differ slightly.** The brief North drafts changes wording and figures between runs. Different words lead to a different design.
4. **Nothing is remembered.** A design that gave the right number is not kept, so the next build starts from zero.

## How it is being fixed (rounds 5 to 8)
1. **Recipes first.** For the family-office pack, each common figure (net worth, cash by entity, cash break, missing statements, concentration, change since report, FX confirmation variance) gets a written recipe. A recipe names the tables the figure reads, the formula and the grouping. Span uses the recipe. The model is asked only for a figure with no recipe.
2. **Remember what worked.** A model design that passes the checks and gives rows is saved as an office skill. The next build of the same figure reuses it word for word.
3. **The same call gives the same reply.** Design calls run at temperature 0 and are cached by their input. A retry asks the model again, not the rules.
4. **Check before go-live.** Each recipe carries a tie-out where one exists. For example, net worth equals the sum of positions for the same date. A figure that fails its tie-out is held at Decision 3 with the reason given.
