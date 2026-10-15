# Reuse first (decision D-031)

Nothing is built before checking whether the earlier product already built it. There are no restrictions on copying code, prompts, tests, screens or content between the earlier repo and this one. The one thing that never moves is real client data (rule 0).

1. **Open `docs/reuse-inventory.md`** for your module and search it for the capability. Then run `graft ask "<need>" --source` inside the earlier repo (`<earlier repo>`) and, for family-office work, the fork worktree named in the inventory.
2. **Port the earlier tests first**, then the code. Run them to see them fail, then make them pass.
3. **Every package brief starts with a "Reuse check"**: the earlier files and line ranges found; for each, copied, reshaped (why) or not used (why); and what is genuinely new. "Nothing exists" must be backed by the searches you ran.
4. **Copy, do not retype.** Change only what the new kernel, the decisions or the rules require (industry words go into the pack; the egress gateway for model calls; the module folder layout).
5. **Reviewers check it.** A package that rebuilt something that exists is rejected, with the earlier file named.
6. If the inventory is wrong or missing something you found, add it to `docs/reuse-inventory.md` in your package.
