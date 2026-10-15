"""Open a page as a person, print its text and the visible buttons/inputs, optional screenshot. Usage: probe.py who path [shotname]"""
import sys
from uc5lib import W
w = W(sys.argv[1]); w.go(sys.argv[2], 4000)
print(w.pg.url); print(w.text()[:3000])
print("BUTTONS:", [b.inner_text()[:40] for b in w.pg.query_selector_all("button") if b.is_visible()])
print("INPUTS:", [(e.evaluate("e=>e.tagName"), e.get_attribute("aria-label"), e.get_attribute("placeholder")) for e in w.pg.query_selector_all("input,textarea,select") if e.is_visible()])
if len(sys.argv) > 3: print(w.shot(sys.argv[3]))
