#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

step() {
    echo ""
    echo "==> $1"
}

step "Checking for Homebrew"
if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is not installed. Installing it now (you may be asked for your password)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo "Homebrew is already installed."
fi

step "Installing ffmpeg, ollama, and uv"
brew install ffmpeg ollama uv

step "Starting Ollama and downloading the local AI model (this can take a few minutes the first time)"
brew services start ollama >/dev/null 2>&1 || true
sleep 2
ollama pull qwen3:4b-instruct

step "Setting up Mynah's Python environment"
if [ ! -d ".venv" ]; then
    uv venv --python 3.12
fi
uv pip install -r requirements.txt -r requirements-dev.txt

step "Building the system audio listener"
swiftc tools/system_audio_recorder/main.swift \
    -o tools/system_audio_recorder/system_audio_recorder \
    -framework ScreenCaptureKit -framework AVFAudio -framework CoreMedia

step "Setting up the 'mynah' command"
mkdir -p "$HOME/.local/bin"
chmod +x run.py
ln -sf "$REPO_ROOT/run.py" "$HOME/.local/bin/mynah"

SHELL_PROFILE=""
if [ -n "${ZSH_VERSION:-}" ] || [ "${SHELL:-}" = "/bin/zsh" ]; then
    SHELL_PROFILE="$HOME/.zshrc"
elif [ -n "${BASH_VERSION:-}" ] || [ "${SHELL:-}" = "/bin/bash" ]; then
    SHELL_PROFILE="$HOME/.bash_profile"
fi

if [ -n "$SHELL_PROFILE" ] && [ -f "$SHELL_PROFILE" ] && ! grep -q '.local/bin' "$SHELL_PROFILE" 2>/dev/null; then
    echo '' >> "$SHELL_PROFILE"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$SHELL_PROFILE"
    echo "Added ~/.local/bin to your PATH in $SHELL_PROFILE"
fi

echo ""
echo "=========================================="
echo " Mynah is installed!"
echo "=========================================="
echo ""
echo "Close this window and open a new Terminal window, then try:"
echo ""
echo "    mynah record"
echo ""
echo "The first time you record, macOS will ask for Screen Recording"
echo "permission — this lets Mynah hear the other people on your call,"
echo "not just your own microphone. Just click Allow."
