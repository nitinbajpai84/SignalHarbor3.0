"""UC6 through Harbor 3.0, resumable: each run takes the liquidity thread one step further and screenshots it.
sh py.sh v3_e2e.py [month]   (UC6_BASE=http://127.0.0.1:8630 UC6_ENV=D:/Temp/sh3-data UC6_SHOTS=<dir>)"""
import json, shutil, sys, time
from pathlib import Path
from uc6 import ENV, REPO, Person, dump

INTENT = ("I want to know every morning whether each entity can meet its capital calls from cash: cash by entity, "
          "calls due in 30 and 60 days, and uncalled commitments. Mei and Daniel read it; I decide. Monthly refresh.")
MONTH = sys.argv[1] if len(sys.argv) > 1 else "2026-07"
import os
STATE = Path(os.environ.get("V3_STATE", "D:/Temp/sh3-e2e.json"))


def drop(month: str) -> None:
    box = ENV / "evergreen" / "dropbox"
    box.mkdir(parents=True, exist_ok=True)
    for f in (REPO / "docs" / "demo" / "uc6" / "sources" / month).iterdir():
        shutil.copy2(f, box / f.name)
    print("dropped", month)


def wait(p: Person, tid: str, busy=("drafting", "working"), limit=900) -> dict:
    t0 = time.time()
    while True:
        st, th = p.get(f"/api/v3/threads/{tid}")
        if th.get("stage") not in busy or time.time() - t0 > limit:
            return th
        time.sleep(5)


def last(th: dict, n=4) -> None:
    for e in th.get("events", [])[-n:]:
        print(" ", e.get("kind"), "|", (e.get("text") or ", ".join(e.get("chips") or []))[:300])


if __name__ == "__main__":
  with Person("anita") as p:
      s = json.loads(STATE.read_text()) if STATE.exists() else {}
      if not s.get("tid"):
          for u in ("desk", "setup", "welcome", "start"):
              p.shot(f"/v3/{u}", f"v3-01-{u}")
          drop(MONTH)
          st, th = p.post("/api/v3/threads", {"text": INTENT})
          print("create", st)
          s["tid"] = th["id"]
          STATE.write_text(json.dumps(s))
      tid = s["tid"]
      th = wait(p, tid)
      stage = th.get("stage")
      print("stage", stage, "| asked", th.get("asked"), "| harbor steps", th.get("harbor_steps"))
      last(th)
      dump(f"v3_thread_{stage}", th)
      p.shot(f"/v3/thread/{tid}", f"v3-thread-{stage}")
      d = th.get("decision") or {}
      if stage == "decision1" and d.get("gaps"):
          print("GAPS", d["gaps"]); st = "gaps"
      elif stage == "decision1":
          st, th = p.post(f"/api/v3/threads/{tid}/decide", {"n": 1, "answer": "confirm"})
      elif stage == "decision2":
          answers = {q["id"]: q.get("assumed") or q["options"][0] for q in d.get("questions") or [] if q.get("options")}
          for q in d.get("questions") or []:  # Anita's one real answer: the administrator's statement is the check
            if q["id"] == "check:file":
              answers[q["id"]] = next((o for o in q["options"] if "administrator" in o), "No check this time")
          print("answers", answers)
          st, th = p.post(f"/api/v3/threads/{tid}/decide", {"n": 2, "answer": "carry_on", "answers": answers})
      elif stage == "decision3":
          for c in d.get("checks") or []:
              print("  check", c)
          st, th = p.post(f"/api/v3/threads/{tid}/decide", {"n": 3, "answer": "go_live"})
      elif stage == "live":
          for u in ("desk", "board", "note", "files", "ask", "trust/ontology", "trust/model", "trust/language",
                    "trust/people", "trust/proof", "trust/connections", f"trust/workbench?thread={tid}"):
              p.shot(f"/v3/{u}", "v3-live-" + u.replace("/", "-").split("?")[0])
          st = "done"
      else:  # question: show it; a retry is a separate, deliberate run
          st = "question"
      print("action ->", st, "| new stage", th.get("stage") if isinstance(th, dict) else "")
