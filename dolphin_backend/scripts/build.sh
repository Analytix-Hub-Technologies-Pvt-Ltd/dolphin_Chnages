#!/usr/bin/env bash

# Exit on error
set -e

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

STORAGE_DIR="${PROJECT_ROOT}/storage"
RETRIEVAL_DIR="${PROJECT_ROOT}/retrieval"
LOG_DIR="${PROJECT_ROOT}/logs"

echo "PROJECT ROOT: $PROJECT_ROOT"

# Create a storage folder

if [ ! -d "${STORAGE_DIR}" ]; then
  mkdir -p "$STORAGE_DIR"
  echo "Storage folder created"
else
  echo "Storage folder already exist at $STORAGE_DIR"
fi


# Create Faiss bin and json files

if [ ! -d "${RETRIEVAL_DIR}" ]; then
  echo "$RETRIEVAL_DIR is missing"
  exit 1
fi


FAISS_BIN="${RETRIEVAL_DIR}/faiss_index.bin"
FAISS_JSON="${RETRIEVAL_DIR}/faiss_index.meta.json"

if [ ! -f "$FAISS_BIN" ]; then
  touch "$FAISS_BIN"
  echo "Faiss bin file created: $FAISS_BIN"
else
  echo "Faiss bin file already exist at $FAISS_BIN"
fi

if [ ! -f "$FAISS_JSON" ]; then
  touch "$FAISS_JSON"
  echo "Faiss JSON file created: $FAISS_JSON"
else
  echo "Faiss JSON file already exist at $FAISS_JSON"
fi


# Create log folder and file
if [ ! -d "$LOG_DIR" ]; then
  mkdir -p "$LOG_DIR"
  echo "Log directory created at $LOG_DIR"
else
  echo "Log directory already created at $LOG_DIR"
fi

if [ ! -d ".venv" ]; then
  echo "Virtual environment (.venv) not found"
  echo "Creating virtual environment..."
  python3 -m venv .venv
  echo "Virtual environment created. Install requirement..."
  source .venv/bin/activate && pip install -r requirements.txt
fi

if [ ! -f "main.py" ]; then
  echo "main.py not found in current directory: $PROJECT_ROOT"
  exit 1
fi

# ⚡ OPTIMIZATION: 4 workers for concurrent request handling
nohup .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --workers 4 > "${LOG_DIR}/uvicorn.log" 2>&1 &

echo "Uvicorn started on port 8000 with 4 workers"

