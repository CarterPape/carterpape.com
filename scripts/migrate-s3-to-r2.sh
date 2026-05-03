#!/usr/bin/env bash
# 🚚 One-shot migration: copy the public site bucket from AWS S3 to Cloudflare R2.
# Re-runnable: rclone sync only copies objects missing or differing on the
# destination, so this script is safe to run pre-cutover, again at cutover for
# any drift, and one final time post-cutover.
#
# Source AWS creds come from your active SSO session. If `aws sts
# get-caller-identity` works, this script works.
#
# R2 creds come from `.env` (gitignored). Required keys:
#   R2_ACCESS_KEY_ID
#   R2_SECRET_ACCESS_KEY
#   R2_ACCOUNT_ID

set -euo pipefail

cd "$(dirname "$0")/.."

# shellcheck source=/dev/null
set -o allexport
source .env
set +o allexport

if [[ -z "${R2_ACCESS_KEY_ID:-}" || -z "${R2_SECRET_ACCESS_KEY:-}" || -z "${R2_ACCOUNT_ID:-}" ]]; then
    echo "❌ R2 credentials missing in .env (need R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_ACCOUNT_ID)" >&2
    exit 1
fi

aws sts get-caller-identity >/dev/null 2>&1 || {
    echo "❌ AWS SSO session not active. Run: aws sso login" >&2
    exit 1
}

src_bucket="carterpape.com"
dst_bucket="carterpape-com-public"

# Use a temporary rclone config (deleted on exit) so creds never persist on disk.
config=$(mktemp -t rclone-migrate.XXXXXX.conf)
trap 'rm -f "$config"' EXIT
cat >"$config" <<EOF
[src]
type = s3
provider = AWS
env_auth = true
profile = site-generator.carterpape.com
region = us-west-2

[dst]
type = s3
provider = Cloudflare
access_key_id = ${R2_ACCESS_KEY_ID}
secret_access_key = ${R2_SECRET_ACCESS_KEY}
endpoint = https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com
no_check_bucket = true
# R2 only supports the STANDARD class. Source objects in S3 use
# INTELLIGENT_TIERING; without this override, rclone replicates the source
# class and R2 rejects every PutObject with InvalidStorageClass.
storage_class = STANDARD
EOF

echo
echo "📦 ${src_bucket}  ➜  ${dst_bucket}"
rclone --config "$config" sync \
    "src:${src_bucket}" \
    "dst:${dst_bucket}" \
    --transfers 16 \
    --checkers 16 \
    --progress \
    --stats 5s

echo
echo "✅ Migration complete."
