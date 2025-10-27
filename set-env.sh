#!/bin/bash
# LiveTranslator Environment Setup
# Source this file before running docker-compose commands
# Usage: source ./set-env.sh

export LT_STT_PARTIAL_MODE=openai_chunked
export LT_STT_FINAL_MODE=openai_chunked
export WHISPER_MODEL=base
export LT_MT_MODE_PARTIAL=local
export LT_MT_MODE_FINAL=openai
export NUM_THREADS=4
export MAX_REDECODE_SEC=3

echo "✅ LiveTranslator environment variables set:"
echo "   LT_STT_PARTIAL_MODE=$LT_STT_PARTIAL_MODE"
echo "   LT_STT_FINAL_MODE=$LT_STT_FINAL_MODE"
echo "   WHISPER_MODEL=$WHISPER_MODEL"
echo "   LT_MT_MODE_PARTIAL=$LT_MT_MODE_PARTIAL"
echo "   LT_MT_MODE_FINAL=$LT_MT_MODE_FINAL"
echo ""
echo "Now you can run: docker compose up -d"
