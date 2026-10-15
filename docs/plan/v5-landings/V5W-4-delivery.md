# V5W-4 Delivery: security review

Main landing note: `V5W-4.md`. This file holds the review only.

## Review (security, 11 Oct)

**Verdict: pass after fixes.** Egress, default deny and the rule that a maker never approves their own channel hold. I fixed four defects. Nothing was dropped: the code lives in new files, and the changes to `gateway.py` and `policy.py` only add to them.

**Checked and sound**
- **Default deny:** all 12 routes are listed in `d1.permissions.yaml`, and a test proves the yaml matches the router exactly. Settings is for `company_admin` only, and the code checks that again. Participants only reach the Morning Note lines, which are filtered by dashboard access.
- **Maker never approves:** approval is refused for whoever made the channel or sent it for approval, both in the route check and inside `can_approve`. Go live sends nothing.
- **Egress:** every send goes through `send_email` or the new `send_webhook`.
  - Only https and port 443, and the host must be on that company's webhook list. No credentials or fragment are allowed in the address.
  - The path is checked for private content. Names are tokenised. A message is blocked if it still holds a protected name or a raw record.
  - The log keeps the host only. The webhook address is read from the environment when the message is sent and is never stored.
- **Figures:** they come from the dashboard's rows only. A tile with no rows is never shown as zero. Alert limits are compared as Decimals.
- **Outbox:** a channel that is not set up is held with a reason, and so is a message that egress refuses. Nothing fails without saying so.

**Fixed** (backup: `.sh-tmp/d1_delivery.py.bak-v5-review`, `.sh-tmp/test_d1_delivery.py.bak-v5-review`)
1. **A maker could deliver a dashboard they may not open.** `create_channel` read the dashboard without checking the person. It now also calls `cx_dash.get_published(viewer)`, which returns 403.
2. **Approving blind, and figures shown to the wrong people.** Approval now needs dashboard access. In `view()`, previews and outbox rows only appear for dashboards the person may open, and `can.approve` is false otherwise. Before this, a sponsor or approver outside the audience saw the figures in previews and in the outbox.
3. **The secret name could point at any environment variable**, for example `ANTHROPIC_API_KEY` or `SH_SECRET_KEY`. That variable's value would then be used as the delivery address, and the Settings page showed whether it existed.
   - The name must now be `SH_..._WEBHOOK`, `SH_..._HOOK` or `SH_..._WEBHOOK_URL`.
   - The value is only used when it starts with `https://`.
   - IP-address hosts such as `169.254.169.254` and `127.0.0.1` are refused, which stops the webhook list being used to reach internal addresses.
4. **Two smaller fixes:**
   - `create_channel` now saves under the lock, so two people adding channels at once no longer lose one.
   - One unreadable project no longer stops the Morning Note lines for every other project.

**Tests:**
- `pytest tests/v1/test_d1_delivery.py -q`: 15 passed. That includes one new review test. The fixture now sets a dashboard audience, and the reader and an outsider are left out of it.
- `npx vitest run src/v1/d1`: 8 passed.
- The egress suite was not re-run because egress was not changed in this review.

**Open items (not security)**
- Compared with D4:
  - The preview is behind a toggle, where D4 shows it as a side panel.
  - The "Where is this from?" link is missing.
  - There is no benchmark-aware sentence or "BEFORE THIS" context block.
  - The step rail still reads "dashboards".
- A weekly or monthly send always uses day 1 of the period.
- The Settings page should say that the secret name must start with `SH_` and end with `_WEBHOOK`. The placeholder already shows a valid name.
- Integration: the dashboard maker and the channel approvers must be in the dashboard's audience, or be an admin.
