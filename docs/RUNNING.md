# Running Signal Harbor locally

Everything runs on your machine. All data is synthetic and marked "Illustrative".

## Steps

Run these from the repo root, in order.

1. `python tools/doctor.py` checks your set-up (ports, data folder, keys, packs, UI install).
   It prints PASS or FAIL for each check and "Ready." when all is well. It never prints a key.
   Fix any FAIL line using the action shown next to it.
2. `python tools/seed.py` creates three illustrative companies and their people in your data folder
   (`SH_DATA_ROOT` in `.env`, default `data/`). Safe to run again: nothing is deleted or changed.
3. `python tools/dev.py` starts the backend on port 8200 and the UI on port 8201.
   Open http://127.0.0.1:8201 and sign in.

## Sign-in details

The seed writes one line per person to `<data folder>/_control/seed_credentials.txt`:
email, password, roles, company. The command prints only the file path and a count, never a password.
The data folder is git-ignored. Do not copy or share the file.

- Running the seed again keeps existing accounts and passwords as they are.
- `python tools/seed.py --reset-credentials` issues new passwords for the seeded accounts and rewrites the file.

## What is seeded

- Illustrative Harbor Mutual (insurance, Discover package, modules 1 to 3)
- Illustrative Tidewater Capital (asset management, Build package, modules 1 to 5)
- Illustrative Solo Studio (no industry pack, no package, no modules): one person who is both
  company admin and sponsor
- One platform account (super admin) with no company

The two full companies each have one person per role: company admin, sponsor, analyst, participant,
approver and owner. Use one account per person or agent when testing; never a real person's account.

## Models and speech

North and Nira use a model; speech is optional. Everything here is set by name in `.env` or the environment
(values are never printed by the doctor or the screens).

- Model switch: `SH_MODEL_PROVIDER=off` (in `.env` or the environment) turns North and Nira off; the screens say so
  and typing and saving notes keep working. An environment variable that is set but empty (for example
  `GOOGLE_API_KEY=`) overrides `.env` for that provider and switches it off.
- Speech is on the Gemini free tier: development and demos only. It uses the existing `GOOGLE_API_KEY`, and the free
  tier uses content to improve Google's products, so it must not be used for real client conversations. It runs only
  when `SH_MODE=dev`, and dev is the default: production must set `SH_MODE=prod`, otherwise Gemini speech would
  run. With `SH_MODE=prod` speech is off and the screens use typing. Use synthetic demo data only:
  speech sent for transcription cannot have names replaced, so the recording leaves the machine as it is. Spoken
  replies have registered names replaced by a neutral word first, and every speech call is logged before it is sent
  (host, size and a hash, never audio or text). Audio is not stored anywhere.
- Switch the speech provider with a setting, no code change: `SH_SPEECH_PROVIDER` (or `SPEECH_PROVIDER`) set to
  `gemini`, `stub` or `off`. Unset means Gemini when `GOOGLE_API_KEY` is set, otherwise typing only. At production
  switch to the paid tier or to a local open-source engine in the customer's container: that adds a provider choice,
  not new screens. The model names and limits are in `modules/m1_intent/contracts/speech.yaml`.
- Typing keeps working with no speech provider. `python tools/doctor.py` prints "Speech provider in use" with the
  provider's name, and the free-tier note when Gemini is selected.

## Stop

Press Ctrl+C in the window running `tools/dev.py`. It stops both servers.

## Rules

- Use ports 8200 to 8299 only.
- Synthetic data only. Never put real client data in the data folder.
- If `ui/node_modules` is missing, run `npm install` in the `ui` folder.
