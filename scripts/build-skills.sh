#!/bin/bash
set -e

mkdir -p dist

echo "Building dist/sumtube.skill..."
(cd plugins/sumtube && zip -r ../../dist/sumtube.skill . \
  --exclude "commands/*" \
  --exclude "hooks/*" \
  --exclude "__pycache__/*" \
  --exclude "*/__pycache__/*" \
  --exclude "*/__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".venv/*" \
  --exclude "tests/*" \
  --exclude "conftest.py" \
  --exclude ".pytest_cache/*" \
)
echo "  -> dist/sumtube.skill"

echo "Building dist/media-downloader.skill..."
(cd plugins/media-downloader && zip -r ../../dist/media-downloader.skill . \
  --exclude "commands/*" \
  --exclude "hooks/*" \
  --exclude "__pycache__/*" \
  --exclude "*/__pycache__/*" \
  --exclude "*/__pycache__/" \
  --exclude "*.pyc" \
  --exclude ".venv/*" \
  --exclude "tests/*" \
  --exclude "conftest.py" \
  --exclude ".pytest_cache/*" \
)
echo "  -> dist/media-downloader.skill"

echo "Build complete."
