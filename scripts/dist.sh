#!/usr/bin/env bash
# Build the release archives for all platforms.
#
# Usage: scripts/dist.sh [version]
#
# The archive names use the OS and architecture words that the mise asset
# matcher knows (darwin, linux, windows, x64, arm64). Thus
# "mise use -g github:TudorAndrei/ste-cli" finds the correct asset with no
# configuration.
set -euo pipefail

VERSION="${1:-${VERSION:-}}"
if [ -z "$VERSION" ]; then
	VERSION="$(git describe --tags --always --dirty 2>/dev/null || echo dev)"
fi
VERSION="${VERSION#v}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/dist"
rm -rf "$OUT"
mkdir -p "$OUT"

# GOOS GOARCH arch-label archive-format
TARGETS=(
	"darwin arm64 arm64 tar.gz"
	"darwin amd64 x64 tar.gz"
	"linux arm64 arm64 tar.gz"
	"linux amd64 x64 tar.gz"
	"windows amd64 x64 zip"
)

sha256() {
	if command -v sha256sum >/dev/null 2>&1; then
		sha256sum "$@"
	else
		shasum -a 256 "$@"
	fi
}

for target in "${TARGETS[@]}"; do
	read -r goos goarch label format <<<"$target"
	name="ste-${VERSION}-${goos}-${label}"
	work="$OUT/.work"
	rm -rf "$work"
	mkdir -p "$work"

	exe="ste"
	if [ "$goos" = "windows" ]; then
		exe="ste.exe"
	fi

	echo "building $name"
	CGO_ENABLED=0 GOOS="$goos" GOARCH="$goarch" go build \
		-trimpath \
		-ldflags "-s -w -X main.Version=${VERSION}" \
		-o "$work/$exe" "$ROOT/cmd/ste"

	# The binary stays at the root of the archive, thus mise finds it
	# with no bin_path option.
	if [ "$format" = "zip" ]; then
		(cd "$work" && zip -q "$OUT/${name}.zip" "$exe")
	else
		tar -czf "$OUT/${name}.tar.gz" -C "$work" "$exe"
	fi
	rm -rf "$work"
done

(cd "$OUT" && sha256 ./*.tar.gz ./*.zip | sed 's|\./||' >checksums.txt)

echo
ls -l "$OUT"
