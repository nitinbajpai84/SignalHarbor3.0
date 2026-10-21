# Backup and restore policy

Status: draft (W7). Owner: Nitin Bajpai.

## What exists
- `tools/backup.py --company <id> --out <folder> --key-env <NAME>` writes `<company>-<UTC time>.shbk`: the company's whole data plane, gzip-tarred with a manifest of file hashes, encrypted (Fernet, key derived with scrypt from the passphrase in the named environment variable). The passphrase is never on the command line or in the file.
- `tools/restore_test.py <file> --key-env <NAME>` decrypts into a temporary folder, checks every file hash and every figure record against the manifest, deletes the folder, and exits non-zero on any difference.
- Tests: `tests/v1/test_g_security.py`.

## Rules
1. Back up each live company daily and before every release; keep 30 daily and 12 monthly copies.
2. The backup passphrase is held in the host's secret store and in a second place Nitin controls (password manager); never in the repository.
3. Copy backups to a different location from the data volume (another account or region).
4. Run `restore_test.py` on the newest backup every month and after any change to the backup tool; record the date and result.
5. Targets: lose at most 24 hours of data; restore within 1 working day.

## Open
- Backups are not scheduled yet: someone (or a Railway cron) must run the tool.
- Off-site copy and retention pruning are manual.
- Postgres state in production mode is not covered by this tool (use the host's database backup).
- The archive is built in memory: fine for office-size planes, stream it for very large ones.
