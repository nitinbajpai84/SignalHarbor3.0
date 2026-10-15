"""Open a page as one person, screenshot it, print text and buttons: python look.py <who> <path> <shot-name|-> [nchars]"""
from lib import *
w = W(sys.argv[1]); w.go(sys.argv[2], 5000)
if sys.argv[3] != "-": w.shot(sys.argv[3])
print(w.pg.url); print(w.text()[: int(sys.argv[4]) if len(sys.argv) > 4 else 3000]); print("BUTTONS", w.buttons()[:60]); w.close()
