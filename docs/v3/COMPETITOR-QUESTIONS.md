# Questions for competitor demos and user calls

These questions find out what Addepar, Masttro and similar platforms really do, and where they still leave work to people. The aim is to find out how they get accuracy and what buyers still struggle with, not to copy their product.

How to use this:
- Pick 10 to 15 questions per call; don't run the whole list.
- Ask for numbers and examples ("show me", "how many", "how long"), not opinions.
- Write down the exact words people use for their pain. That language goes into our pitch.

---

## Part A: Sales demos (you are a prospective family office)

Introduce yourself as a family office evaluating platforms, which is true. Don't sign an NDA or a trial agreement that restricts what you can do with what you learn.

### A1. Getting data in
1. Which custodians and banks do you connect to directly? How many in Singapore and Asia?
2. How do you handle a bank or custodian you don't have a feed for? Who keys it in, and how quickly?
3. What happens with private fund statements, capital call notices and K-1-type documents that arrive as PDFs by email?
4. Do you read PDFs automatically? Which fields? What share needs a human to fix?
5. How long does onboarding take for an office like ours (about 8 entities, 30 funds, 4 banks, 2 custodians)? Who does the work, us or you?
6. When a new fund or account appears, how does it get set up?

### A2. Accuracy and reconciliation
7. How do you reconcile positions and cash against the custodian? Daily? Automatically?
8. When a feed and a statement disagree, what happens? Show me the exception screen.
9. Do you have a data operations team checking our data? What do they check, and what's the service level?
10. What is your typical break rate (exceptions per 1,000 positions)? How fast are breaks cleared?
11. How do you handle corporate actions, restated statements and late or missing statements?
12. Where do prices for private assets come from? How do you show a valuation is stale?
13. Can I see, for any number on a report, exactly where it came from? Show me the audit trail for one figure.

### A3. Ownership and structure
14. How do you model trusts, holding companies and partial ownership? Show a look-through for an entity owned 60/40.
15. Can each family member see only their own share?

### A4. Performance and reporting
16. Which return methods (TWR, IRR, money-weighted)? How do you handle cash flows mid-period?
17. How are benchmarks blended and assigned?
18. How long does month-end reporting take with your platform? What is still manual?
19. Can the board pack or investment committee pack be produced in one click? Show one.

### A5. Workflow and action
20. Does the system tell anyone to do anything (approve a payment, chase a statement), or is it reporting only?
21. If a capital call's wire instructions change, does the system catch it?
22. Are there tasks, approvals and sign-off rules (for example, payments over 500k need the Head of Finance)?

### A6. AI features
23. What AI features have you shipped, not announced? Show me one live.
24. Can I ask a question in plain words and get a number? How do you stop it making numbers up?
25. Is my data used to train models? Where are the models hosted?

### A7. Commercials and security
26. How is pricing calculated (assets, entities, users)? What would our office pay per year? What's the implementation fee?
27. SOC 2 Type II, ISO 27001? Where is data stored? Can it stay in Singapore?
28. Contract length and exit terms: can we export everything if we leave?

**Watch for:** what the salesperson avoids showing, what needs "our services team", and anything marked "on the roadmap".

---

## Part B: User calls (people who use or used Addepar, Masttro or similar)

Target COOs, CFOs, fund accountants, operations leads and consultants who implement these platforms. Ask for 20 minutes. Promise not to name them or their office.

### B1. Context
1. What platform do you use, for how long, and for what size of office?
2. What did you use before, and why did you switch?

### B2. Where time still goes
3. Walk me through your last month-end close. Which steps are still manual?
4. What do you still do in Excel alongside the platform? Why?
5. How many hours a week does your team spend fixing or checking data in it?
6. What's the most annoying recurring task in your week?

### B3. Accuracy and trust
7. When did the platform last show a wrong number? How did you find out, and what caused it?
8. How long does a break or a wrong number take to fix, and who fixes it, you or the vendor?
9. Do you trust the numbers enough to send them to the family without checking?
10. How are private fund statements and capital calls handled? Is it reliable?
11. Has a change of bank details or a suspicious payment instruction ever slipped through? How was it caught?

### B4. Onboarding and support
12. How long did onboarding take compared with what was promised?
13. How good is their data operations or support team? Response times?
14. What surprised you after signing?

### B5. Value and price
15. What do you pay roughly? Is it worth it? What would make you switch?
16. If a new tool did one thing perfectly, what should that one thing be?
17. Would you pay for:
    - (a) automatic reading of every statement and notice, with a receipt for each number;
    - (b) a system that tells the right person what to do;
    - (c) asking questions in plain words?

    Rank them.

### B6. Close
18. Who else should I talk to?
19. Would you look at what we're building for 15 minutes in a few weeks?

---

## After each call: write down
- Their top 3 pains, in their own words.
- Every number they gave (hours, break rate, price, onboarding time).
- Anything that confirms or kills one of our assumptions (docs/v3/ASSUMPTIONS.md).
- Which of our top 20 use cases it touches (docs/v3/USE-CASES-100.md).

Keep the notes in `docs/v3/research/` (one file per call, no real names; use "COO, SG office, ~USD 400m").
