---
description: Deep pre-deploy test, then deploy carterpape.com to S3 and push to the git remote
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Deploy (carterpape.com)

Ship the current working tree to production: carterpape.com on S3, fronted by Cloudflare, with the matching commit pushed to GitHub.

This command touches shared state (live site, remote git). **Always confirm with the user before running the push step**, even in auto mode.

Work through steps in order; stop on the first failure.

## Steps

### 1. Preflight: working tree state

Run `git status` and `git log --oneline -5`.

- If there are uncommitted changes, stop and ask the user whether to commit them first (usually via `/wrap-up`) or discard/stash them. Do not deploy a dirty tree silently — the S3 bundle will include uncommitted work, but the git push won't, leaving live and `main` out of sync.
- If there are unpushed commits ahead of `origin/main`, note them — they're about to go live. That's usually expected.

### 2. Deep test

Run the dry-run pipeline to catch issues before we touch production:

```sh
scripts/main test
```

This runs, in order:
1. `JEKYLL_ENV=production bundle exec jekyll build` — the real production build (minification on, etc.), which is stricter than the dev build `/wrap-up` runs.
2. `htmlproofer` against `_site/` — checks `Links,Images,Scripts,Favicon,OpenGraph`, with a 2-week external-link cache. This is slow the first time; subsequent runs within the cache window are fast.
3. `aws sso login` — may prompt in the browser.
4. `rclone sync --dry-run` to `s3-for-carterpape-com:carterpape.com` — shows exactly what would change on S3. Read this output. Unexpected deletions or a surprisingly large diff are signals to stop and investigate.

If anything fails or the dry-run diff looks wrong, stop and surface it to the user. Do not proceed to step 3.

### 3. Confirm with the user

Summarize what the dry-run will do: commits about to be pushed, rough size of the S3 diff, anything notable from htmlproofer. Then ask explicitly: "Proceed with deploy?" Wait for an affirmative answer. This is a hard gate even in auto mode — deploying to a live personal site is not routine low-risk work.

### 4. Deploy

Run:

```sh
scripts/main push
```

This re-runs production build + htmlproofer (should be cached/fast), re-prompts `aws sso login` if needed, does the real `rclone sync` to S3, then `git pull && git push`.

If git-lfs prompts for credentials during the push, relay the script's instructions to the user: create/refresh a GitHub personal access token at `https://github.com/settings/tokens` and supply it. Do not attempt to mint or paste tokens on the user's behalf.

### 5. Post-deploy notes

Surface any known gaps so the user can handle them manually:

- **Cloudflare cache purge is not automated.** `scripts/main push` has TODOs for this. If the change modifies existing URLs (as opposed to adding new ones), the user may want to purge the Cloudflare cache manually so visitors see the update promptly.
- **Caching headers on S3 objects** are also a pending TODO in the script.
- **Redirects**: `_site/redirects` is not yet turned into a Cloudflare bulk redirect list automatically.

Mention these only if they're relevant to what changed this session — don't recite the list every deploy.
