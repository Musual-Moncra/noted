#!/usr/bin/env bash
# Noted Installer for macOS and Linux
# Usage: curl -fsSL https://raw.githubusercontent.com/Musual-Moncra/noted/main/install.sh | bash

set -euo pipefail

REPO="Musual-Moncra/noted"
GITHUB_URL="https://github.com/${REPO}"

# Colors
if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
    BOLD="\033[1m"
    BLUE="\033[38;2;122;162;247m"
    GREEN="\033[38;2;158;206;106m"
    YELLOW="\033[38;2;224;175;104m"
    RED="\033[38;2;247;118;142m"
    RESET="\033[0m"
else
    BOLD=""
    BLUE=""
    GREEN=""
    YELLOW=""
    RED=""
    RESET=""
fi

log_info() {
    printf "${BLUE}${BOLD}==>${RESET} ${BOLD}%s${RESET}\n" "$1"
}

log_success() {
    printf "${GREEN}${BOLD}✓${RESET} %s\n" "$1"
}

log_warn() {
    printf "${YELLOW}${BOLD}!${RESET} %s\n" "$1"
}

log_error() {
    printf "${RED}${BOLD}✗ Error:${RESET} %s\n" "$1" >&2
}

# 1. Detect Operating System
OS="$(uname -s)"
case "$OS" in
    Darwin)
        OS_TYPE="macos"
        ;;
    Linux)
        OS_TYPE="linux"
        ;;
    *)
        log_error "Unsupported operating system: $OS. Noted currently supports macOS, Linux, and Windows."
        exit 1
        ;;
esac

# 2. Detect CPU Architecture
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64|amd64)
        ARCH_TYPE="x64"
        ;;
    arm64|aarch64)
        ARCH_TYPE="arm64"
        ;;
    *)
        log_error "Unsupported CPU architecture: $ARCH"
        exit 1
        ;;
esac

log_info "Detected system: ${OS_TYPE}-${ARCH_TYPE}"

# 3. Target Install Directory
INSTALL_DIR="${BIN_DIR:-$HOME/.local/bin}"
mkdir -p "$INSTALL_DIR"

# 4. Resolve Asset URL
ASSET_NAME="noted-${OS_TYPE}-${ARCH_TYPE}.tar.gz"
VERSION="${1:-latest}"

if [ "$VERSION" = "latest" ]; then
    DOWNLOAD_URL="${GITHUB_URL}/releases/latest/download/${ASSET_NAME}"
else
    DOWNLOAD_URL="${GITHUB_URL}/releases/download/${VERSION}/${ASSET_NAME}"
fi

log_info "Downloading ${ASSET_NAME} from ${GITHUB_URL}..."

# Setup temporary scratch space
TMP_DIR="$(mktemp -d 2>/dev/null || mktemp -d -t 'noted-install')"
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT INT TERM

ARCHIVE_PATH="$TMP_DIR/$ASSET_NAME"

# Download with curl or wget
if command -v curl >/dev/null 2>&1; then
    if ! curl -fSL --progress-bar "$DOWNLOAD_URL" -o "$ARCHIVE_PATH"; then
        log_error "Failed to download $DOWNLOAD_URL. Please verify your internet connection or check the release page."
        exit 1
    fi
elif command -v wget >/dev/null 2>&1; then
    if ! wget -q --show-progress "$DOWNLOAD_URL" -O "$ARCHIVE_PATH"; then
        log_error "Failed to download $DOWNLOAD_URL. Please verify your internet connection or check the release page."
        exit 1
    fi
else
    log_error "Neither 'curl' nor 'wget' was found on your system. Please install curl or wget."
    exit 1
fi

# 5. Extract Archive
log_info "Extracting executable..."
tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"

if [ ! -f "$TMP_DIR/noted" ]; then
    # Look for binary recursively inside temp dir
    FOUND_BIN="$(find "$TMP_DIR" -type f -name "noted" | head -n 1)"
    if [ -n "$FOUND_BIN" ]; then
        mv "$FOUND_BIN" "$TMP_DIR/noted"
    else
        log_error "Could not find 'noted' binary in archive."
        exit 1
    fi
fi

# 6. Install Binary & Create Symlink
mv "$TMP_DIR/noted" "$INSTALL_DIR/noted"
chmod +x "$INSTALL_DIR/noted"
ln -sf "$INSTALL_DIR/noted" "$INSTALL_DIR/note"

log_success "Installed binary to ${INSTALL_DIR}/noted"
log_success "Created alias symlink ${INSTALL_DIR}/note"

# 7. Ensure INSTALL_DIR is in PATH
PATH_UPDATED=0
case ":$PATH:" in
    *":$INSTALL_DIR:"*)
        # Already in PATH
        ;;
    *)
        CURRENT_SHELL="$(basename "${SHELL:-bash}")"
        PROFILE_FILE=""
        if [ "$CURRENT_SHELL" = "zsh" ]; then
            PROFILE_FILE="$HOME/.zshrc"
        elif [ "$CURRENT_SHELL" = "fish" ]; then
            PROFILE_FILE="$HOME/.config/fish/config.fish"
        elif [ "$CURRENT_SHELL" = "bash" ]; then
            if [ "$OS_TYPE" = "macos" ] && [ -f "$HOME/.bash_profile" ]; then
                PROFILE_FILE="$HOME/.bash_profile"
            else
                PROFILE_FILE="$HOME/.bashrc"
            fi
        fi

        LINE_TO_ADD="export PATH=\"\$HOME/.local/bin:\$PATH\""
        if [ "$CURRENT_SHELL" = "fish" ]; then
            LINE_TO_ADD="fish_add_path \$HOME/.local/bin"
        fi

        if [ -n "$PROFILE_FILE" ] && [ -f "$PROFILE_FILE" ]; then
            if ! grep -q '\.local/bin' "$PROFILE_FILE" 2>/dev/null; then
                printf "\n# Added by Noted installer\n%s\n" "$LINE_TO_ADD" >> "$PROFILE_FILE"
                log_success "Added ${INSTALL_DIR} to PATH in ${PROFILE_FILE}"
                PATH_UPDATED=1
            fi
        fi

        if [ "$PATH_UPDATED" -eq 0 ]; then
            log_warn "${INSTALL_DIR} is not in your \$PATH."
            printf "  Please add it to your shell configuration:\n"
            printf "    %s\n\n" "$LINE_TO_ADD"
        else
            log_warn "Restart your terminal or run: %s\n" "$LINE_TO_ADD"
        fi
        ;;
esac

# 8. Print Finish Banner
printf "\n${GREEN}${BOLD}✨ Noted installed successfully!${RESET}\n"
printf "Type ${BLUE}${BOLD}noted${RESET} or ${BLUE}${BOLD}note${RESET} to start writing.\n\n"
