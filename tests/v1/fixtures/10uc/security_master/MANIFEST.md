# security_master fixtures (synthetic)

Generator: `tools/gen_10uc/security_master.py` (deterministic, no random). Source: `docs/test/10uc_universe.json`.

| File | Holds |
|---|---|
| `EG_security_master_20261008.xlsx` | Sheet "Security master": 29 rows (20 listed/bond/convertible securities, 9 funds A-E, H1, H2, L1, L2) with internal id, synthetic ISIN (ZZ prefix, Luhn check), name, type, asset class, currency, trading code, administrator code, manager, portfolio, quantity at 30 Sep 2026. Sheet "Alias map": 93 rows mapping tickers, administrator codes and manager naming variants to the internal id. Title, as-of date, row count and page footer on both sheets. |

Planted facts carried:
- P19: Pacific Rim Convertible 2029 note (SEC-PRC29) has a blank asset class, status "Active - asset class missing".
- P13: "KR Macro Fund Ltd - Class B USD" and "Kestrel Ridge Macro Fund" both map to FND-H1 (administrator code 4481); "Fund B - Evergreen Liquid Book" and "Evergreen Income II" both map to FND-B.
- Other name variants (Fund A x3, C, D, E, H2) map one-to-one to their fund; administrator codes 4471-4475, 4481, 4482, 4491, 4492 and 5001-5020.

Notes: ISINs and the L1/L2 unit counts are not in the universe (ISINs are synthetic codes; units 50000 and 40000 come from it). The Evergreen Liquid Book (LIQ) has no identifiers in the universe and is not a row.
