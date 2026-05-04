# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Carter Pape's personal website, a Jekyll site deployed as a static bundle to a Cloudflare R2 bucket bound directly as a Custom Domain on the `carterpape.com` zone. Originally derived from the Minimal theme; now heavily customized.

## Common commands

All day-to-day operations go through `scripts/main` (a zsh dispatcher). It sources `.env` (which provides `DEV_HOST_NAME`, `DEV_PORT`, `DEV_LIVERELOAD_PORT`, and — for the cache-purge step — `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ZONE_ID`) and prepends Homebrew's Ruby to `PATH`.

- `scripts/main dev` — `jekyll serve` with `--incremental --drafts` and livereload. Drafts under `the-blog/_drafts/` are rendered in dev.
- `scripts/main init_env` — first-time setup: `bundle config` to vendor gems into `vendor.noindex/` and `bundle install`.
- `scripts/main reset_ruby` — nuclear reset of `vendor.noindex/`, `Gemfile.lock`, `bin/`; then reinstalls bundler and runs `init_env`.
- `scripts/main production_build` is not a subcommand, but `test` and `push` invoke `JEKYLL_ENV=production bundle exec jekyll build` internally.
- `scripts/main proof_html` — runs `htmlproofer` against `_site/` with a real-browser UA, checks `Links,Images,Scripts,Favicon,OpenGraph`, 2-week external cache, and swaps `carterpape.com` URLs for local ones. On failure, hands the captured output to `scripts/check_external_links.py`, which retries each flagged URL through the self-hosted FireCrawl at `localhost:3002` and prompts via macOS dialog for anything still unresolved. Verified-alive answers cache for 2 weeks in `tmp/link-verification-cache.json`.
- `scripts/main check_transform_sources` — scans `_site/` for `/cdn-cgi/image/<opts>/<absolute-url>` references, dedupes to unique external sources, and HEADs each through Cloudflare's transformation endpoint at `carterpape.com`. Fails the deploy if any return non-200 (i.e., the source isn't in the Cloudflare dashboard's allowed list), grouping rejected sources by origin in markdown bullets and offering to open the dashboard. The dashboard is the single source of truth — no in-repo allowlist. Each run uses a random `width=` to bust Cloudflare's transformation cache.
- `scripts/main check_path_periods` — walks `_site/` for any *directory* whose name contains a period. The "add trailing slash" dynamic-redirect rule (see §"Cloudflare edge ruleset") skips paths containing `.`, so a generated URL like `/foo.bar/baz/` would 404 if a visitor stripped the trailing slash. Jekyll's pretty permalinks map URL path 1:1 to disk location, so dot-bearing directories under `_site/` are exactly the failure surface. Files with extensions (`style.css`, `feed.xml`) are fine — Cloudflare serves them directly. Hand-written links to non-existent dot-shaped paths are caught by htmlproofer's broken-link check, not here. Runs inside `test` and `push` between `check_transform_sources` and `proof_html`.
- `scripts/main check_path_uppercase` — walks `_site/` for any *directory* whose name contains an ASCII uppercase letter. URL convention here is lowercase-only path components, and there's intentionally no edge rule to normalize case (see §"Cloudflare edge ruleset" — Apple/NYT both 404 on case-typo'd URLs, so a blanket lowercase redirect isn't worth the cost). Asset *filenames* like `IMG_6686.jpg` are intentionally exempt — they're files, not directories, and uppercase there is meaningful (camera output, proper nouns). To fix a flagged path, rename the source file/directory in the repo to lowercase. Runs inside `test` and `push` immediately after `check_path_periods`.
- `scripts/main test` — production build + check_transform_sources + check_path_periods + check_path_uppercase + htmlproofer + `rclone sync --dry-run` to the R2 bucket.
- `scripts/main push` — production build + check_transform_sources + check_path_periods + check_path_uppercase + htmlproofer + real `rclone sync` (with `-v --log-file=tmp/rclone.log`) to `r2-for-carterpape-com:carterpape-com-public`, then Cloudflare cache purge for just the synced paths, then `git pull && git push`. git-lfs uses a self-hosted Cloudflare Worker (`~/Developer/git-lfs-self-host/`); credentials are cached in the macOS Keychain for the Worker host.
- `scripts/main purge_cache` — runs just the Cloudflare purge against whatever's in `tmp/rclone.log`. Useful if the post-push purge failed and you need to retry without re-syncing.

There is no test suite; `htmlproofer` is the closest thing to CI. There is no CI workflow — deployment is manual via `scripts/main push`.

Bundler is configured to install gems under `vendor.noindex/` (the `.noindex` suffix keeps Spotlight out).

## Architecture

### Content model: collections-as-portfolio + one blog

Each of the non-blog top-level pages (`journalism.html`, `apps.html`, `awards.html`, `drone-work.md`, `photography.md`, `references.html`, `audio.md`) is a **browsing index** backed by a Jekyll collection in `_journalism/`, `_apps/`, `_awards/`, `_drone-work/`, `_photography/`, `_references/`. All of these collections set `output: false` in `_config.yml` — the items are never rendered as standalone pages, only embedded into the index via the card-list layout. The `order:` list under each collection in `_config.yml` controls display order.

The blog is the exception. Posts live in `the-blog/_posts/` (plus `the-blog/_drafts/` for unpublished drafts and `the-blog/unlisted/` for reachable-but-hidden posts), are rendered as pages, and are categorized by subdirectory (`making-carterpape-com`, `decompiling-facebook`, `making-write`, `april-2022-photo-dump`). `_config.yml` maps those directory names to pretty `category_display_names`.

### Layouts and two reading modes

`_layouts/` has two stems:

- `browsing/` — card-list indexes (the collection pages). Default `layout` for all pages is `browsing/card-list`, set via `defaults` in `_config.yml`.
- `reading/` — post/article view. Default `layout` for posts is `reading/post`. `reading/podcast.html` exists for audio posts.

Both inherit from `default.html`, which pulls in `_includes/head/head.html`, site content, `_includes/head/icons.svg` (inline SVG sprite), and `_includes/analytics.html`.

Per-post chrome (header, author block, featured image, "filing" category badge, footer, previews) lives in `_includes/post/`. Authoring helpers — figures, image/photo dumps, Kuula/Vimeo/YouTube embeds, code snippets, quotes, screenshots — live in `_includes/authoring/` and are meant to be `{% include %}`-ed from post Markdown.

### Plugins and forks

Jekyll plugins are declared in the `:jekyll_plugins` group of `Gemfile`. Two are forks maintained under Carter's GitHub:

- `jekyll-reduce-title-redundancy` — strips duplicate titles (configured via `reduce_title_redundancy.strip_title: true`).
- `jekyll-xmp` — XMP sidecar metadata handling, paired with the `xmpr` gem (also a fork).

Other notable plugins in use: `jekyll-feed`, `jekyll-seo-tag`, `jekyll-redirect-from`, `jekyll-target-blank`, `jekyll-image-size`, `jekyll-optional-front-matter`, `jekyll-minifier` (CSS/JS minification is disabled in config — only HTML is minified).

Liquid is in `error_mode: strict` with `strict_filters: true`; `strict_front_matter: true` is also set. Expect build-time failures rather than silent fallbacks.

### Styling

SCSS source in `_scss/`, compiled with `sass-embedded`, `style: compressed`. Assets (favicons, JS, images per-post under `assets/posts/`) live in `assets/`.

## Cloudflare edge ruleset

Reference for what runs at the edge between visitor and R2. Inspect with `GET /zones/$CLOUDFLARE_ZONE_ID/rulesets` (filter to `kind == "zone"` for the entrypoint rulesets) and `GET /accounts/$CLOUDFLARE_ACCOUNT_ID/rulesets` for the account-level bulk-redirect ruleset. Phase order on a request is: dynamic redirect → URL rewrite → bulk redirect → origin (R2). Each redirect rule, if matched, terminates the request with a 301 — the browser starts over and the chain re-runs on the new URL.

1. **Dynamic redirect — "Redirect from WWW to apex"** (phase `http_request_dynamic_redirect`). When `http.request.full_uri wildcard r"https://www.*"`, 301 to `https://${1}` with query preserved. Hosts `www.carterpape.com` traffic on the apex.
2. **Dynamic redirect — "Add trailing slash to extension-less paths"** (phase `http_request_dynamic_redirect`). When path doesn't end with `/` AND doesn't contain `.`, 301 to `https://carterpape.com<path>/` with query preserved. Catches `/journalism` → `/journalism/`. The "doesn't contain `.`" guard is what stops the rule from accidentally redirecting asset URLs like `/style.css` (which Cloudflare serves directly from R2). Side effect: a generated URL like `/foo.bar/baz` won't get redirected — `check_path_periods` is the build-time guard against generating that shape.
3. **URL rewrite — "Rewrite trailing-slash paths to index.html"** (phase `http_request_transform`). When path ends with `/`, rewrite to `<path>index.html`. R2 with Custom Domain doesn't do S3-website-style directory-index resolution, so this is what makes `/journalism/` actually serve `_site/journalism/index.html` from R2. (Without this rule, both `/journalism` and `/journalism/` would 404 — the dynamic-redirect rule above only solves the no-slash case; this one solves the slash case.)
4. **Bulk redirect — "carterpape.com intrasite redirects"** (account-level phase `http_request_redirect`, list `intrasite_redirects`). Synced from `_site/redirects.json` on every `scripts/main push` via `scripts/sync_cloudflare_redirects.py`. List items are stored with `https://carterpape.com<path>/index.html` source URLs because the bulk-redirect phase runs *after* the URL rewrite has already appended `index.html` to the path.

Also active on the zone: a legacy "Cache Everything" Page Rule on `carterpape.com/*`, carried over from before the R2 migration. (The `.env` token doesn't have Page Rules read scope, so verify in the dashboard if you need to.)

The jekyll-redirect-from plugin still emits per-alias meta-refresh HTML stubs into `_site/`, and rclone uploads them to R2 alongside everything else. They're a redundant origin-side fallback for any path not caught by the bulk-redirect ruleset at the edge.

## Conventions

- Permalinks: `pretty` (no `.html`).
- Timezone: `America/Denver`. Date format: `%b. %-d, %Y`.
- When adding a new item to a collection (`_journalism/`, `_apps/`, etc.), add its filename to the corresponding `order:` list in `_config.yml` — otherwise it won't appear in the index.
- Pages with a `last_updated` front matter field (e.g. `awards.html`, `résumé.md`) should get that date bumped whenever their content — or the collection content they index — changes meaningfully.
- When adding a new blog category (subdirectory under `the-blog/`), add a human-readable name to `category_display_names` in `_config.yml`.
- Markdown lint: `.markdownlint.yml` extends a parent config and disables `no-bare-urls`.
- `pape-docs/` is a personal scratchpad convention and should stay gitignored if created.
