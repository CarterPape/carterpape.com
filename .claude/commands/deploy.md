---
description: Deep pre-deploy test, then deploy carterpape.com to R2 and push to the git remote
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Deploy (carterpape.com)

Ship the current working tree to production: carterpape.com on R2, fronted by Cloudflare, with the matching commit pushed to GitHub.

This command touches shared state (live site, remote git). **Always confirm with the user before running the push step**, even in auto mode.

Work through steps in order; stop on the first failure.

## Steps

### 1. Preflight: working tree state

Run `git status` and `git log --oneline -5`.

- If there are uncommitted changes, stop and ask the user whether to commit them first (usually via `/wrap-up`) or discard/stash them. Do not deploy a dirty tree silently — the R2 bundle will include uncommitted work, but the git push won't, leaving live and `main` out of sync.
- If there are unpushed commits ahead of `origin/main`, note them — they're about to go live. That's usually expected.

### 2. Deep test

Run the dry-run pipeline to catch issues before we touch production:

```sh
scripts/main test
```

This runs, in order:
1. `JEKYLL_ENV=production bundle exec jekyll build` — the real production build (minification on, etc.), which is stricter than the dev build `/wrap-up` runs.
2. `check_transform_sources` — HEADs every Cloudflare Image Transformation source URL through the production zone; fails the deploy if any source isn't on the dashboard's allowed list.
3. `htmlproofer` against `_site/` — checks `Links,Images,Scripts,Favicon,OpenGraph`, with a 2-week external-link cache. This is slow the first time; subsequent runs within the cache window are fast.
4. `rclone sync --dry-run` to `r2-for-carterpape-com:carterpape-com-public` — shows exactly what would change on R2. Read this output. Unexpected deletions or a surprisingly large diff are signals to stop and investigate.
5. `sync_cloudflare_redirects.py --dry-run` — diffs `_site/redirects.json` against the `intrasite_redirects` bulk redirect list and prints what would change at the edge.

If anything fails or the dry-run diff looks wrong, stop and surface it to the user. Do not proceed to step 3.

### 3. Confirm with the user

Summarize what the dry-run will do: commits about to be pushed, rough size of the R2 diff, anything notable from htmlproofer, any redirect adds/removes. Then ask explicitly: "Proceed with deploy?" Wait for an affirmative answer. This is a hard gate even in auto mode — deploying to a live personal site is not routine low-risk work.

### 4. Deploy

Run:

```sh
scripts/main push
```

This re-runs production build + transform-source check + htmlproofer (should be cached/fast), does the real `rclone sync` to R2, syncs the bulk redirect list, purges the Cloudflare cache for changed paths, then `git pull && git push`.

If git-lfs prompts for credentials during the push, relay the script's instructions to the user: create/refresh a GitHub personal access token at `https://github.com/settings/tokens` and supply it. Do not attempt to mint or paste tokens on the user's behalf.

### 5. Post-deploy notes

Surface any known gaps so the user can handle them manually:

- **Caching headers on R2 objects** are a pending TODO in the script.

Mention these only if they're relevant to what changed this session — don't recite the list every deploy.
