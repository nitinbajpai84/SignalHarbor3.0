"""The ownership register of the Evergreen Office (W3, assumption A61) and the answer key of the look-through card uc-101-ownership.
Synthetic: the trust holds 60 percent of Evergreen Holdings (55 until 30 Jun 2026, when the principal moved 5 points to it), Mei Chen the rest, Holdings owns all of Entity B,
and the four beneficiaries hold the trust by the shares of the deed. Look-through is the product of the percentages down every path, summed."""
import datetime as dt
from decimal import Decimal as D

from .keys import Q, uc
from .more import TRUST_DEED
from .world import ENT, FUND, PRIVATE, TERMS, d
from .files import pname

DEED = "evergreen_family_trust_deed.pdf"
REGISTER = "Share register of Evergreen Holdings, 15 Jul 2026"
SINCE, MOVED = "2021-03-15", "2026-07-01"
# owner_kind, owner, owned entity, percent, valid_from, valid_to ("" = still in force), source
ROWS = ([["entity", ENT["EG-TRUST"], ENT["EG-HOLD"], 55, SINCE, "2026-06-30", REGISTER], ["entity", ENT["EG-TRUST"], ENT["EG-HOLD"], 60, MOVED, "", REGISTER],
         ["family_member", "Mei Chen", ENT["EG-HOLD"], 45, SINCE, "2026-06-30", REGISTER], ["family_member", "Mei Chen", ENT["EG-HOLD"], 40, MOVED, "", REGISTER],
         ["entity", ENT["EG-HOLD"], ENT["EG-B"], 100, SINCE, "", "Share register of Entity B"]]
        + [["family_member", n, ENT["EG-TRUST"], v, SINCE, "", f"Deed of settlement ({DEED})"] for n, v in TRUST_DEED["shares"].items()])
HEAD = ["owner_kind", "owner", "owned_entity", "ownership_pct", "valid_from", "valid_to", "source"]


def shares(asat, rows=ROWS):
    """{holder: {owned entity: fraction}} by walking every path from each owner down, as at the date (a period is in force from valid_from to valid_to, both days included)."""
    live = [(o, e, D(p) / 100) for k, o, e, p, f, t, s in rows if f <= asat.isoformat() and (not t or asat.isoformat() <= t)]
    out = {}

    def walk(holder, node, frac, seen):
        for o, e, p in live:
            if o == node and e not in seen:
                out.setdefault(holder, {}).setdefault(e, D(0))
                out[holder][e] += frac * p
                walk(holder, e, frac * p, seen | {e})
    for o in {o for o, _, _ in live}:
        walk(o, o, D(1), {o})
    return out


@uc("uc-101-ownership", ["reference/ownership_register.csv", "reference/fund_terms.csv", "*/trust_deed/evergreen_family_trust_deed.pdf"])
def k101(w):
    now, before = d("2026-10-13"), d("2026-06-30")
    c = next(f for f in PRIVATE if pname(f).startswith("Cedarpoint Ventures III"))
    amount, home = D(TERMS[c][0]), ENT[FUND[c]["legal_entity"]]
    s, b = shares(now), shares(before)
    mei = lambda sh: float(sh["Mei Chen"][home])
    return Q("What is Mei Chen's share of Cedarpoint Ventures III, and what does the Trust hold indirectly?",
             dict(fund=pname(c), commitment=amount, held_by=home, as_at=now.isoformat(), mei_effective_pct=mei(s) * 100, mei_share=float(amount) * mei(s),
                  mei_effective_pct_at_30_jun=mei(b) * 100, mei_share_at_30_jun=float(amount) * mei(b),
                  trust_effective_pct_of_holdings=float(s[ENT["EG-TRUST"]][ENT["EG-HOLD"]]) * 100, trust_share=float(amount) * float(s[ENT["EG-TRUST"]][ENT["EG-HOLD"]]),
                  trust_beneficiaries=[dict(person=n, effective_pct=float(s[n][home]) * 100, share=float(amount) * float(s[n][home])) for n in TRUST_DEED["shares"]],
                  holders_of_entity_b=sorted(h for h in s if ENT["EG-B"] in s[h])),
             "the commitment of the fund (reference/fund_terms.csv) times the share of every owner down the chain of ownership_register.csv as at the date: Mei Chen holds 40 percent of Holdings since 1 Jul 2026 (45 before), "
             "the Trust 60 percent (55 before), a beneficiary the deed's share of the Trust's part")
