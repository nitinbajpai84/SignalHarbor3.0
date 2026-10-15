"""CRITIC-M1 defect 6 and 10: Nira answers a privacy question from the session's privacy facts, and a time warning says
minutes, not seconds."""
from m1_kit import BASE
from modules.m1_intent.agent import nira
from test_m1_briefing_kit import make_world, session_at, use_model
from test_m1_nira import Spy, ask


def test_the_privacy_facts_reach_nira_and_her_instructions_answer_privacy_questions_directly(tmp_path):
    w = make_world(tmp_path)
    org = w.login("org", "co-a")
    sid = session_at(w, org, "co-a", "briefing", purpose="Find our shared worries")
    spy = use_model(w, Spy("No. Only you can read your private room."))
    r = ask(org, sid, question="Can the family council see my chat with North?")
    assert r.status_code == 200 and "Only you" in r.json()["text"]
    facts = spy.context["privacy"]
    assert "can be read only by you" in facts and "anonymous shows no name" in facts and "until the private rooms close" in facts
    assert "without saying that the organiser would know" in spy.system


def test_the_time_warning_says_minutes():
    assert nira.minutes_not_seconds("332 seconds are left in this stage.") == "about 5 minutes are left in this stage."
    assert nira.minutes_not_seconds("75 seconds left") == "about 1 minute left"
    assert nira.minutes_not_seconds("40 seconds left") == "less than a minute left"
    cfg = nira.load_rules()
    text = nira.ask_nira(None, None, None, "co", "Co", "x", stage="private_rooms", rules=[], kind="warning",
                         extra="332 seconds are left in this stage.")
    assert "about 5 minutes are left" in text and "332" not in text and cfg["messages"]["warning"].split("{")[0].strip() in text
