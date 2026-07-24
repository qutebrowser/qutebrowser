#!/usr/bin/env bash
set -euo pipefail

# qutebrowser AI feature — one-shot setup script
#
# Usage:  bash scripts/setup-ai.sh
#
# What it does:
#   1. Installs Python dependencies from misc/requirements/requirements-ai.txt.
#   2. Pre-downloads the all-MiniLM-L6-v2 embedding model into the huggingface
#      cache so no network requests happen at runtime.
#
# The LLM endpoint (Ollama, cloud provider, etc.) is configured via
# environment variables — see .env.example.

REQUIREMENTS_FILE="misc/requirements/requirements-ai.txt"

# ----- Install Python dependencies -----------------------------------------
echo "Installing Python dependencies from ${REQUIREMENTS_FILE} ..."
pip install -r "${REQUIREMENTS_FILE}"
echo "Python dependencies installed."

# ----- Pre-download sentence-transformers model ----------------------------
echo "Pre-downloading all-MiniLM-L6-v2 embedding model to cache ..."
python3 -c "
from sentence_transformers import SentenceTransformer
SentenceTransformer('all-MiniLM-L6-v2')
print('Embedding model cached.')
"
echo "Pre-download complete — no network requests at runtime."

# ----- Summary -------------------------------------------------------------
cat <<'EOF'

── Setup complete ──────────────────────────────────────────────────────
  • Embeddings:   all-MiniLM-L6-v2 (cached)
  • Retrieval:    sentence-transformers → sklearn → stdlib

Set AI_BASE_URL to point to your LLM endpoint (Ollama, cloud provider,
etc.) and launch qutebrowser. For example:

  export AI_BASE_URL="http://localhost:11434/v1"
  export AI_MODEL="gemma4:e4b"
  qutebrowser

Then try:
  :ai-do "close every tab except the current one"
  :ai-do "mute all tabs and reload"
  :ai-do "open github.com"

See .env.example for all available options.
─────────────────────────────────────────────────────────────────────────
EOF
