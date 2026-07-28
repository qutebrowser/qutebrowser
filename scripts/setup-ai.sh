#!/usr/bin/env bash
set -euo pipefail

# qutebrowser AI feature — dependency installer
#
# Usage:  bash scripts/setup-ai.sh
#
# What it does:
#   1. Installs Python dependencies from misc/requirements/requirements-ai.txt.
#   2. Pre-downloads the all-MiniLM-L6-v2 embedding model into the huggingface
#      cache so no network requests happen at runtime.
#
# What it does NOT do:
#   - It does NOT install or manage Ollama or any LLM backend.
#   - The LLM endpoint is configured separately via environment variables
#     (AI_BASE_URL, AI_MODEL, AI_API_KEY) — see .env.example.
#   - Without a configured LLM endpoint the feature still runs in mock
#     mode (degraded but functional).

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

IMPORTANT: You still need an LLM endpoint. This script does NOT install
Ollama or any other LLM backend. The AI feature works in mock mode
without one, but for real translations you need either:

  a) Local Ollama → ollama pull gemma4:e4b  (see https://ollama.com)
  b) A cloud provider → set AI_BASE_URL / AI_MODEL / AI_API_KEY

See .env.example for all available options.

Examples once an LLM endpoint is available:
  :ai-do close every tab except the current one
  :ai-do mute all tabs and reload
  :ai-do open github.com
─────────────────────────────────────────────────────────────────────────
EOF
