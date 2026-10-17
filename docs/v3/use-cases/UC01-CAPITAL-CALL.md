# Use case 1: a capital call arrives, can we pay it, and should we?

Synthetic office: Evergreen Office. All names, funds, banks and figures are invented.

## In one line
A fund asks for money. Within two days the office has logged the call, checked it against the commitment, found the cash, converted currency, caught a changed bank account, paid safely, and everyone can see the updated position. Each person does only their own part, and Harbor carries the rest.

## The people
| Person | Role in this story |
|---|---|
| Sam Lee, Operations Clerk | first to see the notice |
| Helen Foo, Fund Accountant | records the call against the commitment |
| Daniel Foo, Head of Finance | decides how to fund it and approves the payment |
| Grace Ong, Operations Lead | checks the payment instructions before money moves |
| Raj Patel, CIO | needs the updated commitments for the investment committee |
| Mei Chen, Principal | sees it in her morning note |

## What already exists (built by earlier use cases over April to September)
- **Cash by entity**, a verified figure. Daniel built it in July, and it has run daily since.
- **Commitments**: each fund's commitment, called to date, and unfunded amount. Helen built it from the subscription documents in April.
- **Bank standing instructions** for each fund, kept from the April and July calls.
- **The FX rate feed** (USD/SGD daily), from Mei's report build.
- **Office rules, signed:** a payment over 500,000 USD needs Daniel's approval; changed bank details need a call-back before payment; keep a 250,000 USD cash buffer per entity.

## What arrives
**Tuesday 13 Oct, 09:12.** An email from Cedarpoint Capital to ops@ with a PDF, *Cedarpoint Ventures III, Capital Call Notice No. 7*:
- Investor: Evergreen Holdings
- Amount: **USD 1,250,000**
- Due: **Friday 23 Oct 2026**
- Purpose: new investments 900,000; management fee 350,000
- Wire to: Harbour Bank (synthetic), account **ending 4471** (the account on file ends 2209)

## The story, step by step

**1. The notice arrives (Action, no one has to look for it).**
- Harbor watches the drop folder and the inbox. It recognises the PDF as a capital call notice of a layout it has seen before (calls 5 and 6, in April and July). It reads the investor, amount, due date, purpose and bank details, each with its page and quoted line.
- Two checks agree on every field.
- Sam's Action list shows: **"Capital call from Cedarpoint Ventures III: USD 1,250,000, due 23 Oct, for Evergreen Holdings. Log it?"** Sam taps Log.
- *Skills used:* recognise file, read PDF fields, two-check judge.

**2. It is checked against the commitment (Action, Helen).**
- Harbor reuses the **Commitments** figure. Evergreen Holdings committed 10,000,000 to Cedarpoint Ventures III. Called before this notice: 6,000,000. After it: **7,250,000 called, 2,750,000 unfunded**.
- The call does not exceed the unfunded amount, so it is within the commitment. The fee part (350,000) matches the fee rate in the fund terms.
- Helen's card: **"Call 7 fits the commitment. Unfunded after this call: 2,750,000. Record it?"** Helen records it, and the commitments figure updates.
- *Reused:* the Commitments figure. *New:* nothing.

**3. Can we pay it? (Consume, Daniel asks in his own words).**
- Daniel types: *"Can Holdings pay the Cedarpoint call on the 23rd?"*
- Harbor answers in about a second from the verified **Cash by entity** figure and the calls due:
  > Evergreen Holdings has USD 1,230,000 and SGD 1,600,000 (USD 1,194,030 at today's 1.3400). Calls due by 23 Oct: USD 1,250,000. Keeping the 250,000 buffer, Holdings is **short USD 270,000** in US dollars. It can cover this by converting about **SGD 361,800**. Where this number comes from →
- *Reused:* Cash by entity, the FX rate feed, the buffer rule. *New:* the figure **"Cash after calls due, by entity"**, built from those three. It is recorded with its receipts, and the next time anyone asks a "can we pay" question, it is reused.

**4. Daniel decides (Action, the one human decision about money).**
- Harbor proposes: convert SGD 361,800 to USD on Thursday 22 Oct, then pay on the 23rd.
- Daniel can choose **Approve**, **Change**, or **Fund from another entity**. He approves. It is over 500,000, so the office rule needs his approval, and the record shows his name and time.

**5. Something is wrong with the bank account (Action, Grace).**
- Before the payment is prepared, Harbor compares the wire details with the fund's standing instructions. The account changed from ending 2209 to ending 4471.
- Harbor holds the payment and does not suggest the new account. Grace's card reads: **"Bank details for Cedarpoint changed since July. Office rule: call back on a known number before paying."**
- Grace calls Cedarpoint on the number from the April subscription pack. It is confirmed: they moved banks. She records **"Confirmed by call-back, 13 Oct, 15:40, spoke to fund operations"** and attaches her note.
- The standing instructions update, with the old ones kept in the history.
- This is a classic fraud pattern, and the step exists to catch it.

**6. FX and payment (Action, Thursday and Friday).**
- **Thursday:** the FX trade is done with the bank. The confirmation PDF arrives, and Harbor matches it to the approved conversion (rate 1.3405, SGD 361,935, within 0.1% of the plan). The match goes green on its own.
- **Friday:** the payment instruction is prepared for the bank portal. Daniel releases it. The bank statement on Monday shows USD 1,250,000 out, and Harbor matches it to call 7, so the call is closed.

**7. Everyone sees the new picture.**
- **Raj (Consume):** *"What's our unfunded commitment across all funds?"* returns the updated total, with Cedarpoint at 2,750,000.
- **Mei's morning note on Monday:** "Cedarpoint Ventures III call 7 paid (USD 1,250,000). Holdings cash after calls: USD 1.17m. Unfunded across all funds: USD 14.6m."
- **Knowledge:** the Cedarpoint fund page now shows calls 5, 6 and 7, the bank change with its call-back, and the three figures that use it.

## Figures and how the test checks them (computed from the generated data)
| Figure | Expected | How the key is computed |
|---|---|---|
| Unfunded after call 7 | 2,750,000 | commitment 10,000,000 minus called 7,250,000 |
| Holdings USD shortfall after buffer | 270,000 | 1,250,000 + 250,000 buffer − 1,230,000 USD cash |
| SGD to convert | 361,800 | 270,000 × 1.3400 |
| Bank details changed | yes (2209 → 4471) | notice versus standing instructions |
| Call 7 status after the Monday statement | Paid | statement line matches amount and date |

## What the office's picture gains from this one use case
- **Reused:** Cash by entity, Commitments, FX rates, three office rules.
- **New:**
  - one figure: Cash after calls due, by entity;
  - one record type: standing instructions with history;
  - one Action pattern: changed-bank-details hold;
  - one layout learned: Cedarpoint notice;
  - one link in Knowledge: fund → bank → people who confirmed it.
- **Who acted:** six people. Five of them clicked once or twice, and Grace made one phone call. The time from notice to approved plan was under an hour of human time across two days.

## What Harbor assumed (shown in "What I assumed")
- The fee part is checked against the fee rate in the fund terms on file.
- The buffer is 250,000 per entity, from the signed office rule.
- The rate for planning is today's WMR 4pm fixing. The trade rate is what the confirmation says.

## How this use case passes the test
It passes when all of these hold:
- each of the five figures above matches its key;
- the bank-change hold appears;
- no payment is proposed to the new account before the call-back;
- the payment is matched to the statement.
