#!/usr/bin/env bash
#
# Prepare a fresh Amazon Linux 2023 host to run the Corelantic stack.
#
# Installs Docker and the Compose plugin, adds swap, and generates the two secrets compose
# needs. Idempotent — every step checks first, so re-running is safe. Starts nothing: bring the
# stack up yourself once you have reviewed .env.
#
#   ./deploy/bootstrap.sh                                        # prompts for the proxy login
#   PROXY_USER=aaron PROXY_PASSWORD=... ./deploy/bootstrap.sh    # non-interactive

set -euo pipefail

readonly COMPOSE_VERSION=v2.32.4
readonly SWAP_SIZE=2G
readonly ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
skip() { printf '    already done: %s\n' "$1"; }
die()  { printf '\033[31merror:\033[0m %s\n' "$1" >&2; exit 1; }

# ---------------------------------------------------------------- preflight
# Everything below mutates the host, so anything that could stop us runs first: a run that dies
# halfway leaves swap added and no proxy login, which is worse than not starting.

# Under sudo, $USER is root — adding *that* to the docker group would leave the real account
# unable to talk to the daemon, and the generated secrets root-owned.
readonly TARGET_USER="${SUDO_USER:-${USER:-$(id -un)}}"
[ "$TARGET_USER" != "root" ] || die "run as the login user (the script sudos where needed), not as root"

if [ ! -f "$ROOT/deploy/htpasswd" ] \
   && { [ -z "${PROXY_USER:-}" ] || [ -z "${PROXY_PASSWORD:-}" ]; } \
   && [ ! -t 0 ]; then
  die "no terminal to prompt on: set PROXY_USER and PROXY_PASSWORD, or run interactively"
fi

# ---------------------------------------------------------------- swap
# Under 2GB of RAM and the Next build is the memory-hungry step; without swap it is killed
# rather than slowed. Low swappiness keeps this as headroom, not routine paging.
step "Swap"
if [ "$(swapon --show --noheadings | wc -l)" -gt 0 ]; then
  skip "swap active ($(free -m | awk '/Swap:/{print $2}')MB)"
else
  sudo fallocate -l "$SWAP_SIZE" /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile >/dev/null
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
  echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swappiness.conf >/dev/null
  sudo sysctl -q vm.swappiness=10
  echo "    added ${SWAP_SIZE} swap"
fi

# ---------------------------------------------------------------- docker
step "Docker"
if command -v docker >/dev/null 2>&1; then
  skip "$(docker --version)"
else
  sudo dnf install -y docker >/dev/null
  echo "    installed $(docker --version)"
fi

# Enabled, not just started: containers carry `restart: unless-stopped`, so this is what brings
# the whole stack back after a reboot — no unit of our own required.
sudo systemctl enable --now docker >/dev/null 2>&1
sudo usermod -aG docker "$TARGET_USER"

# ---------------------------------------------------------------- compose plugin
step "Compose plugin"
readonly PLUGIN_DIR=/usr/libexec/docker/cli-plugins
if docker compose version >/dev/null 2>&1; then
  skip "$(docker compose version)"
else
  sudo mkdir -p "$PLUGIN_DIR"
  sudo curl -fsSL \
    "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
    -o "$PLUGIN_DIR/docker-compose"
  sudo chmod +x "$PLUGIN_DIR/docker-compose"
  echo "    installed compose ${COMPOSE_VERSION}"
fi

# ---------------------------------------------------------------- daemon defaults
# compose.yaml caps its own services; this catches anything else that ever runs here, so an
# unbounded log cannot fill the disk out from under the stack.
step "Docker log limits"
if [ -f /etc/docker/daemon.json ]; then
  skip "/etc/docker/daemon.json exists"
else
  sudo mkdir -p /etc/docker
  sudo tee /etc/docker/daemon.json >/dev/null <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
  sudo systemctl restart docker
  echo "    capped container logs at 10m x 3"
fi

# ---------------------------------------------------------------- secrets
step "Compose environment"
if [ -f "$ROOT/.env" ]; then
  skip ".env exists (left untouched)"
else
  cp "$ROOT/.env.example" "$ROOT/.env"
  sed -i "s|^INTERNAL_API_KEY=.*|INTERNAL_API_KEY=$(openssl rand -hex 32)|" "$ROOT/.env"
  # Read by `docker compose` as the login user, so owner-only is both safe and sufficient.
  chown "$TARGET_USER" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  echo "    wrote .env with a generated INTERNAL_API_KEY"
fi

step "Proxy credentials"
if [ -f "$ROOT/deploy/htpasswd" ]; then
  skip "deploy/htpasswd exists (left untouched)"
else
  proxy_user="${PROXY_USER:-}"
  proxy_password="${PROXY_PASSWORD:-}"
  [ -n "$proxy_user" ] || read -rp "    proxy username: " proxy_user
  if [ -z "$proxy_password" ]; then
    read -rsp "    proxy password: " proxy_password
    echo
  fi
  [ -n "$proxy_user" ] && [ -n "$proxy_password" ] || die "proxy username and password are both required"

  # apr1 rather than bcrypt: nginx-alpine links musl's crypt, which has no bcrypt, so a
  # `htpasswd -B` hash is rejected at login with no useful error. Piped, not passed as an
  # argument, so the password never appears in the process list.
  printf '%s:%s\n' \
    "$proxy_user" \
    "$(printf '%s' "$proxy_password" | openssl passwd -apr1 -stdin)" \
    > "$ROOT/deploy/htpasswd"
  chown "$TARGET_USER" "$ROOT/deploy/htpasswd"
  # World-readable on purpose: nginx workers drop privileges and read this per request, and they
  # are not the host user that owns it. The file holds a hash, never the password.
  chmod 644 "$ROOT/deploy/htpasswd"
  echo "    wrote deploy/htpasswd for '$proxy_user'"
fi

# ---------------------------------------------------------------- next steps
cat <<EOF

$(printf '\033[1mReady.\033[0m')

  Data source : $(grep '^CORELANTIC_API_DATA_SOURCE=' "$ROOT/.env" | cut -d= -f2)
  Memory      : $(free -m | awk '/Mem:/{print $2}')MB RAM + $(free -m | awk '/Swap:/{print $2}')MB swap
  Disk        : $(df -h / | awk 'NR==2{print $4}') free

Start it:

  docker compose up -d --build

If docker says "permission denied", your shell predates the docker group — run
'newgrp docker' or reconnect, then retry.
EOF
