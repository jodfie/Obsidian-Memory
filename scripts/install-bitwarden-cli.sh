#!/bin/bash
# Install Bitwarden Secrets Manager CLI (bws)

set -euo pipefail

echo "=========================================="
echo "Installing Bitwarden Secrets Manager CLI"
echo "=========================================="
echo ""

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)
        BWS_ARCH="linux"
        ;;
    aarch64|arm64)
        BWS_ARCH="linux-arm64"
        ;;
    *)
        echo "Error: Unsupported architecture: $ARCH" >&2
        exit 1
        ;;
esac

# Get latest release URL
LATEST_RELEASE=$(curl -s https://api.github.com/repos/bitwarden/sdk/releases/latest)
BWS_VERSION=$(echo "$LATEST_RELEASE" | grep -oP '"tag_name": "\K[^"]+' | head -1)
BWS_URL="https://github.com/bitwarden/sdk/releases/download/${BWS_VERSION}/bws-${BWS_ARCH}"

echo "Detected architecture: $ARCH"
echo "Downloading bws version: $BWS_VERSION"
echo "URL: $BWS_URL"
echo ""

# Download and install
INSTALL_DIR="/usr/local/bin"
TEMP_FILE=$(mktemp)

echo "Downloading bws CLI..."
curl -L "$BWS_URL" -o "$TEMP_FILE"

echo "Installing to $INSTALL_DIR/bws..."
sudo mv "$TEMP_FILE" "$INSTALL_DIR/bws"
sudo chmod +x "$INSTALL_DIR/bws"

# Verify installation
if "$INSTALL_DIR/bws" --version > /dev/null 2>&1; then
    VERSION=$("$INSTALL_DIR/bws" --version)
    echo ""
    echo "✅ Bitwarden Secrets Manager CLI installed successfully!"
    echo "   Version: $VERSION"
    echo "   Location: $INSTALL_DIR/bws"
    echo ""
    echo "You can now run:"
    echo "  bws --version"
    echo "  ./scripts/setup-bitwarden.sh"
else
    echo ""
    echo "⚠️  Installation completed but verification failed"
    echo "   Please check: $INSTALL_DIR/bws"
    exit 1
fi
