# Rounds brief (shared by the four feature agents, 15 Oct)

Read docs/v3/TEAM-OF-TEN-RESULTS.md (what failed and why), docs/v3/TEAM-OF-TEN.md, packs/family_office/1/role_builds.yaml,
docs/v3/HARBOR-SPEC.md, docs/v3/SKILLS-CATALOGUE.md and sh_platform/v1/v3_harbor.py (chains A, B, C, M; `Ctx.api`, `Q`, `record`).

Rules for all four:
- The repo is git: never commit or push. Never start or stop servers on 8630-8632, 8640 or 8701-8710. You MAY start your own
  server for diagnosis on your own port (A 8721, B 8722, C 8723, D 8724) with
  `python tools/serve_test.py --port <p> --data-root <a COPY of a team office>` (copy, never edit, D:/Temp/sh3-team-env-<role>-1).
- New logic goes in YOUR new module. In sh_platform/v1/v3_harbor.py make only small hook edits with the Edit tool (exact string
  replacement), never rewrite the file: three other agents edit it at the same time. Re-read the lines right before each edit.
- Reuse the 2.0 code (sh_platform/v1: b10_*, b11_builder, b6_*, e2_*, x5_extract, e0c_*, k8_sop, i4_sow, seats). Never invent a
  business rule, threshold or figure; every number shown must come from a tool; a missing figure says "Not available yet".
- Every new behaviour records its skill run with v3_skills.record(...) using a catalogue id.
- Tests: your own test file plus `python -m pytest tests/v1/test_v3_harbor.py tests/v1/test_v3_skills.py -q --basetemp=D:/Temp/pyt-<you> -p no:cacheprovider` must stay green.
- Final reply, short: files, what changed, test results, what you could not do.
