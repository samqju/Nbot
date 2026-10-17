#!/usr/bin/env bash
# Fresh, dedicated Ubuntu 22.04/24.04 VPS only. Installs official Docker Engine
# and the Compose plugin; never launches NBOT or modifies project files.
set -Eeuo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run: sudo bash scripts/install_docker_ubuntu.sh"
  exit 1
fi

source /etc/os-release
if [[ "${ID:-}" != "ubuntu" || ! "${VERSION_ID:-}" =~ ^(22\.04|24\.04)$ ]]; then
  echo "STOP: supported by this script only on Ubuntu 22.04 or 24.04."
  echo "See https://docs.docker.com/engine/install/ubuntu/"
  exit 1
fi

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    echo "Docker Engine/Compose are already installed. No changes made."
    docker --version
    docker compose version
    exit 0
  fi
  echo "STOP: Docker is present without Compose. Review your existing installation."
  echo "See https://docs.docker.com/compose/install/linux/"
  exit 1
fi

echo "Installing Docker from Docker's official Ubuntu apt repository..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL --connect-timeout 10 --max-time 30 \
  https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
codename="${UBUNTU_CODENAME:-${VERSION_CODENAME}}"
architecture="$(dpkg --print-architecture)"
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${codename}
Components: stable
Architectures: ${architecture}
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y \
  docker-ce docker-ce-cli containerd.io \
  docker-buildx-plugin docker-compose-plugin
docker --version
docker compose version
echo "Docker installed; NBOT remains stopped. Continue with VPS_SETUP.md."
