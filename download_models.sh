#!/bin/bash
set -e

echo "=== Descarga de modelos LTX-2.3 ==="

COMFY="/workspace/runpod-slim/ComfyUI"

mkdir -p "$COMFY/models/unet"
mkdir -p "$COMFY/models/text_encoders"
mkdir -p "$COMFY/models/checkpoints"
mkdir -p "$COMFY/models/vae"
mkdir -p "$COMFY/models/loras"
mkdir -p "$COMFY/models/upscale_models"

if [ -z "$HF_TOKEN" ]; then
    echo "ERROR: HF_TOKEN no está definido."
    exit 1
fi

export HF_TOKEN

pip install --no-cache-dir -q huggingface_hub

download() {
    REPO="$1"
    FILE="$2"
    DEST="$3"

    if [ -f "$DEST/$FILE" ]; then
        echo "Ya existe: $FILE"
        return
    fi

    echo "Descargando: $FILE"

    huggingface-cli download "$REPO" "$FILE" \
        --local-dir "$DEST" \
        --token "$HF_TOKEN"
}

download \
    "QuantStack/LTX-2.3-GGUF" \
    "ltx-2.3-22b-distilled-1.1-Q4_K_M.gguf" \
    "$COMFY/models/unet"

echo "=== Modelos descargados ==="
