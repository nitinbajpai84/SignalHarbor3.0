"""Embed every indexed document of a company at once (the first search does a few at a time).
Usage: python tools/reindex_vectors.py <company> [--all]   (--all drops existing vectors first; use after changing SH_EMBED_MODEL)
Local only; prints counts, never content. Stop the server first, or expect one "database is locked" retry under load: this script
does not share the server's in-process file locks. If the model cannot load, a warning is logged and the count reads 0."""
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sh_platform.plane import PlaneStore  # noqa: E402
from sh_platform.v1 import doc_index as DI  # noqa: E402

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    plane = PlaneStore(ROOT / "data").plane_for(sys.argv[1])
    con = DI._db(plane)
    with con:
        if "--all" in sys.argv:
            con.execute("delete from vectors")
            con.execute("delete from vec_files")
    paths = [r[0] for r in con.execute("select path from files")]
    con.close()
    for i, p in enumerate(paths, 1):
        DI._embed_file(plane, p, (str(plane.root), "vec:" + p))
        print(f"{i}/{len(paths)}", flush=True)
    con = DI._db(plane)
    print("files with vectors:", con.execute("select count(*) from vec_files").fetchone()[0], "passages:", con.execute("select count(*) from vectors").fetchone()[0])
