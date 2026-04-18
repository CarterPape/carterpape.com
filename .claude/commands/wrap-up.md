---
description: End-of-session wrap-up for carterpape.com: build check, site conventions, docs/memory, local commit (no deploy)
allowed-tools: Bash, Read, Edit, Write, Glob, Grep
---

# Wrap up (carterpape.com)

End-of-session checklist for this Jekyll site. This command does **not** deploy and does **not** push to the git remote — it only commits locally. Use `/deploy` when you're ready to ship.

Work through each step in order. Stop if any step fails.

## Steps

### 1. Build check

Run a non-production Jekyll build to catch strict-mode Liquid errors, missing includes, and broken front matter:

```sh
bundle exec jekyll build
```

(Using `bundle exec` directly rather than `scripts/main` so we skip the production-only minifier/SEO work — that belongs in `/deploy`.)

Fix any errors before proceeding. `_config.yml` sets `strict_filters`, `strict_front_matter`, and Liquid `error_mode: strict`, so failures are loud and should be treated as blockers, not warnings.

### 2. Site conventions

Check changes against the conventions documented in `CLAUDE.md`. Common things that trip people up:

- **New collection items**: if you added a file under `_journalism/`, `_apps/`, `_awards/`, `_drone-work/`, `_photography/`, or `_references/`, its filename must appear in the corresponding `order:` list in `_config.yml`, or it won't show up on the index page.
- **New blog category**: if you added a new subdirectory under `the-blog/` for a new category, add a human-readable name to `category_display_names` in `_config.yml`.
- **`last_updated` bumps**: pages with a `last_updated` front matter field (e.g. `awards.html`, `résumé.md`) should have that date bumped when their content — or the collection content they index — changed meaningfully this session. Use today's date in `America/Denver`.

Skim the staged/unstaged diff and apply any missed bumps or registrations before committing.

### 3. Docs

Review `CLAUDE.md` for any sections that describe code or conventions touched this session. Update anything stale or missing. Don't add sections for trivial changes.

### 4. Memory

Find the project memory directory: `~/.claude/projects/-Users-carterpape-Developer-carterpape-com/memory/`.

Review the memory files there. Update any memories that are stale, and add new memories for anything non-obvious learned this session (user preferences, project decisions, surprising behavior). Skip anything that's obvious from the repo or already in `CLAUDE.md`.

### 5. Local commit

Stage modified tracked files and any new files that belong in the repo (remember `pape-docs/`, `_site/`, `vendor.noindex/`, `bin/` are gitignored). Write a commit message that captures the *why*, not just the *what*, matching the existing repo style (short, lowercase-first, no prefixes like `feat:` or `fix:`).

**Do not push.** `/deploy` handles the push as part of shipping to production.
