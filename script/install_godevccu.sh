#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2021-2026
#
# Download the godevccu simulator binary pinned in .godevccu-version into
# .godevccu/ and verify its checksum. The test fixtures find it there.
#
# Usage: script/install_godevccu.sh

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

version="$(tr -d '[:space:]' < .godevccu-version)"

case "$(uname -s)" in
  Darwin) os="darwin" ;;
  Linux) os="linux" ;;
  *)
    echo "error: unsupported OS $(uname -s); set GODEVCCU_BIN to a godevccu binary instead" >&2
    exit 1
    ;;
esac

case "$(uname -m)" in
  x86_64 | amd64) arch="amd64" ;;
  arm64 | aarch64) arch="arm64" ;;
  *)
    echo "error: unsupported architecture $(uname -m); set GODEVCCU_BIN to a godevccu binary instead" >&2
    exit 1
    ;;
esac

asset="godevccu-${version}-${os}-${arch}"
base="https://github.com/SukramJ/godevccu/releases/download/${version}"

mkdir -p .godevccu
cd .godevccu
curl -fsSL -o "${asset}" "${base}/${asset}"
curl -fsSL -o "${asset}.sha256" "${base}/${asset}.sha256"

if command -v sha256sum > /dev/null 2>&1; then
  sha256sum -c "${asset}.sha256"
else
  shasum -a 256 -c "${asset}.sha256"
fi

chmod +x "${asset}"
ln -sf "${asset}" godevccu
echo "godevccu ${version} installed: ${repo_root}/.godevccu/godevccu"
