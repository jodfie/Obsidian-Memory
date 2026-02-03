# Branch Cleanup

This repo is standardized on **two branches**:

- **main** – default / production
- **dev** – development

All other remote branches (e.g. `master`, `cursor/*`, `claude/*`) can be removed.

## Before you delete

1. **Default branch on GitHub**  
   - Go to [Settings → General → Default branch](https://github.com/jodfie/Obsidian-Memory/settings).  
   - If it’s currently **master**, switch it to **main** (create **main** from **master** first if needed, then set **main** as default).

2. **Merge master into main (if you keep main)**  
   - Locally: `git checkout main && git pull origin main && git merge origin/master && git push origin main`  
   - Or on GitHub: open a PR from **master** into **main**, merge it, then proceed.

3. **Ensure dev is up to date**  
   - `git checkout dev && git pull origin dev`

## Run the cleanup

From the repo root:

```bash
# Dry run: list branches that would be deleted (keeps only main + dev)
./scripts/cleanup-branches.sh

# Actually delete those branches on origin
./scripts/cleanup-branches.sh --delete
```

The script keeps **main** and **dev** and deletes every other remote branch (e.g. **master**, **cursor/***, **claude/***).  
You need push access to the repo; deletions are done with `git push origin --delete <branch>`.

## After cleanup

- **main** – default branch, use for production / releases.  
- **dev** – development; merge into **main** when ready.  
- CI runs on pushes/PRs to **main** and **dev** only (see `.github/workflows/ci.yml`).
