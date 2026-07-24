#!/usr/bin/env bash
set -euo pipefail

# qutebrowser AI feature — one-shot setup script
#
# Usage:  bash scripts/setup-ai.sh
#
# What it does:
#   1. Checks that Ollama is installed and reachable.
#   2. Pulls the default generation model (gemma2:2b).
#   3. Installs the optional sentence-transformers package for
#      semantic retrieval (skipped if already installed).
#
# After this script completes, launch qutebrowser and run
#   :ai-do "your request here"

AI_MODEL="${AI_MODEL:-gemma2:2b}"

# ----- Ollama check --------------------------------------------------------
if ! command -v ollama &>/dev/null; then
  echo "Error: 'ollama' not found on PATH."
  echo "Install it first:  https://ollama.com"
  exit 1
fi

echo "Checking that Ollama is running ..."
if ! ollama list &>/dev/null; then
  echo "Ollama daemon does not appear to be running."
  echo "Start it with:  ollama serve"
  echo "(Or on most systems: systemctl --user start ollama)"
  exit 1
fi
echo "Ollama is running."

# ----- Pull model ----------------------------------------------------------
echo "Pulling model '${AI_MODEL}' (this may take a while the first time) ..."
ollama pull "${AI_MODEL}"
echo "Model '${AI_MODEL}' ready."

# ----- Optional: sentence-transformers ------------------------------------
if python -c "import sentence_transformers" 2>/dev/null; then
  echo "sentence-transformers already installed."
else
  echo "Installing sentence-transformers (optional, ~80 MB) ..."
  pip install sentence-transformers
  echo "sentence-transformers installed."
fi

# ----- Summary -------------------------------------------------------------
cat <<'EOF'

── Setup complete ──────────────────────────────────────────────────────
  • Model:       gemma2:2b  (or $AI_MODEL if overridden)
  • Retrieval:   sentence-transformers (if installed) → sklearn → stdlib
  • LLM backend: Ollama at http://localhost:11434/v1

Launch qutebrowser and try:
  :ai-do "close every tab except the current one"
  :ai-do "mute all tabs and reload"
  :ai-do "open github.com"

Override defaults via environment variables:
  AI_BASE_URL   (default http://localhost:11434/v1)
  AI_MODEL      (default gemma2:2b)
  AI_API_KEY    (only needed for cloud providers)
  AI_TOP_K      (default 8)
─────────────────────────────────────────────────────────────────────────
EOF
