#!/usr/bin/env node
// Signal Harbor guard (PreToolUse). Blocks forbidden actions deterministically.
// Exit code 2 + stderr = block (Claude Code hook contract). Exit 0 = allow.
// Adapted from the earlier repo's guard; package scopes come from docs/ledger/active.json.
'use strict';
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(process.env.CLAUDE_PROJECT_DIR || process.cwd());

const COMMAND_RULES = [
  [/\bgit\s+push\b/i, 'git push is not allowed; Nitin pushes.'],
  [/\bgit\s+reset\s+--hard\b/i, 'git reset --hard is destructive; use a new commit instead.'],
  [/\bgit\s+clean\s+-[a-z]*f/i, 'git clean -f deletes untracked work.'],
  [/\bgit\s+stash\b(?!\s+list)/i, 'git stash is shared across worktrees; use a WIP commit.'],
  [/\b(railway|vercel|fly)\s+(up|deploy|redeploy)\b/i, 'Deploys are not authorised.'],
  [/(--port[ =]|:|port=)\s*80(10|20)\b/i, 'Ports 8010 and 8020 belong to other processes; use 8200-8299.'],
  [/\bchat\.postMessage\b|hooks\.slack\.com/i, 'No real Slack messages.'],
];

const DESTRUCTIVE_SQL = /\b(drop\s+(table|schema|database|view)|truncate\s+table|truncate\s+\w|delete\s+from)\b/i;
const DESTRUCTIVE_FS = /(\brm\s+-[a-z]*r[a-z]*f|\brm\s+-[a-z]*f[a-z]*r|Remove-Item\b[^|;]*-Recurse|\brmdir\s+\/s)/i;
const DISPOSABLE = /(\.sh-tmp|[\\/]tmp[\\/]|pytest-of-|Temp[\\/]+claude|scratchpad|node_modules|__pycache__|\.pytest_cache|ui[\\/]dist)/i;

const SECRET_PATTERNS = [
  /sk-ant-[A-Za-z0-9_-]{20,}/, /sk-or-v1-[A-Za-z0-9]{20,}/, /sk-[A-Za-z0-9]{40,}/,
  /AIza[0-9A-Za-z_-]{35}/, /xox[bpas]-[A-Za-z0-9-]{10,}/, /dapi[0-9a-f]{32}/,
  /-----BEGIN (RSA |EC )?PRIVATE KEY-----/,
];

const PROTECTED_WRITE = [
  [/(^|[\\/])\.env(\.(?!example$)|$)/i, '.env files hold secrets; never write them.'],
  [/[\\/]\.claude[\\/]hooks[\\/]/i, 'The hooks are tool configuration; only Nitin changes them.'],
  [/[\\/]data[\\/]/i, 'data/ holds company data planes; write through the platform, not by hand.'],
];

function block(msg) {
  process.stderr.write('[sh-guard] BLOCKED: ' + msg + '\n');
  process.exit(2);
}

function activeScopes() {
  try {
    const data = JSON.parse(fs.readFileSync(path.join(ROOT, 'docs', 'ledger', 'active.json'), 'utf8'));
    return Array.isArray(data.packages) ? data.packages : [];
  } catch (_) { return []; }
}

function globToRe(g) {
  const esc = g.replace(/\\/g, '/').replace(/[.+^${}()|[\]]/g, '\\$&')
    .replace(/\*\*/g, '\u0000').replace(/\*/g, '[^/]*').replace(/\u0000/g, '.*');
  return new RegExp('^' + esc + '$', 'i');
}

function checkCommand(cmd) {
  for (const [re, msg] of COMMAND_RULES) if (re.test(cmd)) block(msg);
  if (DESTRUCTIVE_SQL.test(cmd) && !DISPOSABLE.test(cmd)) block('Destructive SQL outside a disposable database needs human approval.');
  if (DESTRUCTIVE_FS.test(cmd) && !DISPOSABLE.test(cmd)) block('Recursive delete outside a disposable path needs human approval.');
}

function checkWrite(filePath, content) {
  const abs = path.resolve(ROOT, filePath || '');
  const rel = path.relative(ROOT, abs).replace(/\\/g, '/');
  if (rel.startsWith('..')) return; // outside the repo: the harness's own isolation applies
  for (const [re, msg] of PROTECTED_WRITE) if (re.test('/' + rel)) block(msg);
  if (content) for (const re of SECRET_PATTERNS) if (re.test(content)) block('Content looks like a secret; use an environment variable name.');
  const scopes = activeScopes();
  if (!scopes.length) return; // no package active: orchestrator-level work
  if (/^docs\/ledger\//i.test(rel)) return; // reports and reviews are always writable
  const ok = scopes.some(p => (p.owns || []).some(g => globToRe(g).test(rel)));
  if (!ok) block(`${rel} is outside every active package's OWNS list (docs/ledger/active.json).`);
}

let raw = '';
process.stdin.on('data', d => { raw += d; });
process.stdin.on('end', () => {
  let ev;
  try { ev = JSON.parse(raw || '{}'); } catch (_) { process.exit(0); }
  const tool = ev.tool_name || '';
  const inp = ev.tool_input || {};
  if (tool === 'Bash' || tool === 'PowerShell') checkCommand(String(inp.command || ''));
  else if (tool === 'Write') checkWrite(inp.file_path, String(inp.content || ''));
  else if (tool === 'Edit') checkWrite(inp.file_path, String(inp.new_string || ''));
  else if (tool === 'MultiEdit') checkWrite(inp.file_path, (inp.edits || []).map(e => e.new_string).join('\n'));
  process.exit(0);
});
