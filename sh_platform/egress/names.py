"""Which names go into the egress vault, decided in ONE place (module 1 and module 2 both use it).

A name in the vault is blocked from every outgoing text, also glued inside other words. So the vault must hold real
names only: a person's full name and each part of it, an organisation or system by its full name, and never a generic
word ("Finance", "Market data vendor API", "illustrative"), or nearly every business sentence is refused.
"""
import re

MIN_NAME_PART = 3  # shorter name parts would blank out ordinary words
_PAREN = re.compile(r"\([^)]*\)|\[[^\]]*\]")  # "Mei Tan (illustrative)": the suffix is not part of the name
_EDGE = "()[]{},.;:!?\"'"
# Business, role and generic opener words: a name made only of these is a team, role or system, never registered; they
# are never registered as a part or first word on their own.
STOP_WORDS = frozenset("""illustrative sponsor admin administrator analyst owner approver participant guest finance officer
team data market vendor api index provider committee managers manager payroll custody custodian services service office
family company fund group desk operations investments investment risk treasury hr the and of for platform system
systems department board review reporting performance bank banks broker auditor auditors advisor adviser
lawyer lawyers accountant accountants client clients investor investors trustee trustees legal compliance tax accounting
support it management executive director head lead assistant coordinator reviewer
global national international united general first capital equity prime premier royal standard private public asset
wealth partners holdings""".split())
# Words that make a multi-word "person" an organisation or team ("Northgate Custody", "Bluewater Fund Services"); a surname such as
# "Bank" or "Finance" is not here, so "Grace Bank" stays a person.
ORG_WORDS = frozenset("custody custodian services service fund funds relations administrator administrators vendor provider committee team department desk group".split())
ORG_FIRST_WORD = 6  # an organisation's first word is registered alone from this many letters ("Northgate")
# AQ1 (ER-01): everyday words that are never a name on their own. A case title, fund or report name passed as a "person" ("Entity B",
# "September investment report", "Evergreen Growth I") used to register each word alone, and a single word in the vault blocks every
# text that holds it, glued forms included ("portfolio_id"). These are never registered alone, whatever list they arrive in.
GENERIC_WORDS = STOP_WORDS | frozenset("""january february march april may june july august september october november december
jan feb mar apr jun jul aug sep sept oct nov dec monday tuesday wednesday thursday friday saturday sunday today yesterday tomorrow
week month quarter year daily weekly monthly quarterly yearly annual entity entities report reports portfolio portfolios statement
statements growth income liquid liquidity logistics ventures venture operating operations opportunities opportunity real assets estate
cash bond bonds equities stock stocks shares share note notes book books ledger account accounts holding holdings position positions
valuation valuations value values total totals net gross nav fee fees price prices rate rates trade trades transaction transactions
infrastructure credit hedge index macro long short class series tranche draft final version case cases issue issues break breaks limit
limits rule rules table tables file files source sources check checks match matches figure figures amount amounts balance balances
north south east west new old main core other open closed pending signed approved sent received missing late due trust family office
holdings partners capital advisors advisers associates group fund funds real-assets plan plans project projects dashboard tile tiles
meeting call update letter newsletter memo committee council investment investments
ask please send see thanks thank dear hello hi re fw fwd attn cc note check confirm sent
chase contact tell remind ping synthetic sample demo example internal sweep paying agent desk""".split())  # RC2-1: payees are registered too


def _words(name: str) -> list[str]:
    return [w for w in (p.strip(_EDGE) for p in _PAREN.sub(" ", str(name or "")).split()) if w]


def _is_generic(words: list[str]) -> bool:
    return not words or all(w.casefold() in STOP_WORDS for w in words) or (len(words) == 1 and is_generic_word(words[0]))


EVERYDAY_WORDS = GENERIC_WORDS - STOP_WORDS  # the vault refuses these alone (a stop word may still be a registered company name, say "Company")


def is_everyday_word(word: str) -> bool:
    return str(word or "").strip(_EDGE).casefold() in EVERYDAY_WORDS


def is_generic_word(word: str) -> bool:
    """A single word that is never a name alone: a stop word, an everyday business word, a month or day, a short word or a number."""
    w = str(word or "").strip(_EDGE).casefold()
    return len(w) < MIN_NAME_PART or w in GENERIC_WORDS or not any(c.isalpha() for c in w)


def _parts(words: list[str]) -> list[str]:
    """The parts of a 2 to 4 word name worth registering alone: not a stop or everyday word, 3+ letters, not an all-capitals code."""
    if not 2 <= len(words) <= 4 or any(c.isdigit() for w in words for c in w):
        return []
    return [w for w in words if not is_generic_word(w) and not w.isupper()]


def looks_like_person(words: list[str]) -> bool:
    """2 to 4 capitalised words, no digits, at least one not a business or role word."""
    return (2 <= len(words) <= 4 and all(w[0].isupper() and not any(c.isdigit() for c in w) for w in words)
            and not all(w.casefold() in STOP_WORDS for w in words))


def protected_names(company: str, people: list[str], organisations=()) -> list[tuple[str, str]]:
    """(kind, name) pairs for the vault. The company and each organisation (custodian, vendor, fund, system): the full
    name, and for 2+ words the first word when it is distinctive (not a stop word, 6+ letters). A person, or an
    organisation that looks like one ("Sam Lee" written as a `who`): the full name and each non-stop part. Generic
    words alone are not registered at all. When in doubt, protect."""
    out: list[tuple[str, str]] = []
    mine = {w.casefold() for w in _words(company)}
    people, organisations = list(people), list(organisations)
    for name in list(people):  # CRITIC-M2 P6: a "person" that is a title plus the company's own word is nobody; one with an organisation word is a team or organisation
        w = _words(name)
        low = [x.casefold() for x in w]
        if len(w) >= 2 and all(x in STOP_WORDS or x in mine for x in low) and any(x in STOP_WORDS and x not in mine for x in low):
            people.remove(name)  # needs a real title word ("Sponsor"): "Grace Bank" in "Grace Bank Ltd" is a person
        elif len(w) >= 2 and any(x in ORG_WORDS for x in low):
            people.remove(name)
            organisations.append(name)
        elif len(w) >= 2 and (not looks_like_person(w) or all(is_generic_word(x) for x in w if len(x) >= MIN_NAME_PART)):
            people.remove(name)  # AQ1: "September investment report", "Entity B": a thing, not a person; its words are never parts
            organisations.append(name)
    for is_org, name in [(False, company), *((True, o) for o in organisations)]:
        w = _words(name)
        if _is_generic(w):
            continue
        out.append(("company", " ".join(w)))
        if len(w) >= 2 and not is_generic_word(w[0]) and len(w[0]) >= ORG_FIRST_WORD and not w[0].isupper():
            out.append(("company", w[0]))
        if is_org and looks_like_person(w) and not any(is_generic_word(x) for x in w):
            # a "who" written like a person ("Sam Lee"): its parts too. TAQ-S1: a name with a business word in it ("Kestrel Ridge Advisors",
            # "Evergreen Administrator", "Cedarpoint Custody") is an organisation, never split into person parts ("Ridge", "Evergreen")
            out += [("person", p) for p in _parts(w)]
    for name in people:
        w = _words(name)
        if _is_generic(w):
            continue
        out.append(("person", " ".join(w)))
        out += [("person", p) for p in _parts(w)]
    return list(dict.fromkeys(out))


ORG_SUFFIX = frozenset("capital partners advisors advisers ventures holdings associates managers group trust fund office assets bank".split())
_CANDIDATE = re.compile(r"\b[A-Z][a-z][\w'-]*(?:[ \t]+(?:[A-Z][\w'-]*|of)){1,3}\b")


def names_in_text(text: str, limit: int = 40) -> list[str]:
    """AQ1 (ER-02/NAV-3): names a document or note mentions ("Kestrel Ridge Advisors", "Thomas Lindqvist"): runs of 2 to 4 capitalised
    words with at least one that is not an everyday word. A heuristic (ponytail: no NER model; a name in lower case or a one-word name is missed,
    and a capitalised title such as "Annual General Meeting" is caught only if two of its words are unusual). Returned for registration
    as full names only, never as single words."""
    out: list[str] = []
    for m in _CANDIDATE.finditer(str(text or "")):
        w = _words(m.group(0))
        while w and (w[-1] == "of" or (is_generic_word(w[-1]) and w[-1].casefold() not in ORG_SUFFIX)):
            w.pop()
        while w and is_generic_word(w[0]):
            w.pop(0)
        if len(w) >= 2 and any(not is_generic_word(x) for x in w) and not any(c.isdigit() for x in w for c in x):
            out.append(" ".join(w))
        if len(out) >= limit:
            break
    return list(dict.fromkeys(out))
