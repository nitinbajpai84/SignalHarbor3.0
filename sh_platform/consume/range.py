"""The one range rule for the product: feeds and the Ops screen both call this. Gold marts are read by period."""
import logging
import re
from statistics import mean, stdev

import duckdb

log = logging.getLogger(__name__)
PERIODS = 9      # newest periods read
MIN_EARLIER = 6  # earlier periods needed before a break can be called
SPREADS = 3.0    # a break is more than this many sample spreads from the mean
TINY = 0.01      # a spread under this share of the mean is "tiny": the spreads rule would flag noise
SHARE = 0.25     # when the spread is tiny, a break is more than this share of the mean
CODE = re.compile(r"[a-z0-9_]+")


def trend(con, code: str) -> list[dict]:
    """Newest nine periods of gold.<code> as oldest-first {period, value}. The period is column 1 and the value the last numeric
    column; rows that share a period (a dimension column in between) are summed. [] when there is no mart."""
    table = code.lower()
    if con is None or not CODE.fullmatch(table):
        return []
    try:
        cols = [c[0] for c in con.execute(f"describe gold.{table}").fetchall()]
        if len(cols) < 2:
            return []
        rows = con.execute(f'select "{cols[0]}", sum(try_cast("{cols[-1]}" as double)) from gold.{table} '
                           f'group by 1 order by 1 desc limit {PERIODS}').fetchall()
    except duckdb.Error:
        return []
    return [{"period": str(r[0]), "value": float(r[1])} for r in reversed(rows) if r[1] is not None]


def breaks(trend: list[dict]) -> dict:
    """{"break", "basis"}: the latest value against the mean of the earlier periods; the basis says which test applied."""
    before = [t["value"] for t in trend[:-1]]
    if len(before) < MIN_EARLIER:
        return {"break": False, "basis": f"fewer than {MIN_EARLIER} earlier periods, so no range is set yet"}
    m, s = mean(before), stdev(before)
    gap = abs(trend[-1]["value"] - m)
    if s < TINY * abs(m):
        out = gap > SHARE * abs(m)
        return {"break": out, "basis": f"spread is tiny, so {'more' if out else 'no more'} than {SHARE:.0%} from the mean of the earlier periods"}
    out = gap > SPREADS * s
    return {"break": out, "basis": f"{'more than' if out else 'within'} {SPREADS:g} spreads {'from' if out else 'of'} the mean of the earlier periods"}
