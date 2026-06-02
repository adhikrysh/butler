#!/usr/bin/env bash
# Reproduce the Butler profile on a fresh box. Run AFTER installing Hermes:
#   curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
# Secrets are PROMPTED, never stored in git.
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROFILE_HOME="$HOME/.hermes/profiles/butler"

hermes profile create butler 2>/dev/null || true
mkdir -p "$PROFILE_HOME"

# config.yaml — OpenAI key via an OpenAI-compatible "custom" provider.
cat > "$PROFILE_HOME/config.yaml" <<YAML
model:
  default: "gpt-5.4-mini"
  provider: "custom"
  base_url: "https://api.openai.com/v1"

terminal:
  backend: "local"
  cwd: "."
  timeout: 180

skills:
  external_dirs:
    - $REPO_DIR/modules

# MCP servers. tinyfish (web agent) authenticates with OAuth 2.1 — tokens are
# acquired interactively on first connect, NOT stored here. After bootstrap, run:
#   hermes -p butler mcp login tinyfish   # opens browser / paste-back over SSH
mcp_servers:
  tinyfish:
    url: "https://agent.tinyfish.ai/mcp"
    auth: oauth
    connect_timeout: 300   # headroom for the interactive OAuth approve step
    timeout: 300
YAML

cp "$REPO_DIR/bootstrap/SOUL.md" "$PROFILE_HOME/SOUL.md"

# Secrets + Telegram allowlist (default-deny: only this ID may talk to Butler).
umask 077
read -rsp 'OPENAI_API_KEY: ' OPENAI_API_KEY; echo
read -rsp 'TELEGRAM_BOT_TOKEN: ' TELEGRAM_BOT_TOKEN; echo
read -rp  'Your Telegram numeric user ID (allowlist): ' TG_USER_ID
{
  printf 'OPENAI_API_KEY=%s\n' "$OPENAI_API_KEY"
  printf 'TELEGRAM_BOT_TOKEN=%s\n' "$TELEGRAM_BOT_TOKEN"
  printf 'TELEGRAM_ALLOWED_USERS=%s\n' "$TG_USER_ID"
} > "$PROFILE_HOME/.env"
chmod 600 "$PROFILE_HOME/.env"

echo
echo "Profile 'butler' configured. Next steps:"
echo "  TG_USER_ID=$TG_USER_ID $REPO_DIR/bootstrap/register_cron.sh   # register schedules"
echo "  hermes -p butler gateway install                              # install 24/7 service (answer Y)"
echo "  loginctl enable-linger \"\$USER\"                               # survive logout/reboot"
