#!/bin/bash
set -e

echo "=== Descarga de modelos LTX-2.3 ==="

COMFY="/workspace/runpod-slim/ComfyUI"

mkdir -p "$COMFY/models/unet"
mkdir -p "$COMFY/models/text_encoders"
mkdir -p "$COMFY/models/checkpoints"
mkdir -p "$COMFY/models/vae"
mkdir -p "$COMFY/models/loras"
mkdir -p "$COMFY/models/latent_upscale_models"

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

    if [ -f "$DEST/$(basename "$FILE")" ]; then
        echo "Ya existe: $(basename "$FILE")"
        return
    fi

    echo "Descargando: $FILE"

    huggingface-cli download "$REPO" "$FILE" \
        --local-dir "$DEST" \
        --token "$HF_TOKEN"
}

# =========================================================
# MODELO PRINCIPAL
# =========================================================

download \
    "QuantStack/LTX-2.3-GGUF" \
    "LTX-2.3-distilled-1.1/LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf" \
    "$COMFY/models/unet"


# =========================================================
# VIDEO VAE
# =========================================================

download \
    "smthem/LTX-2.3-test-gguf" \
    "ltx-2.3-22b-distilled_video_vae.safetensors" \
    "$COMFY/models/vae"


# =========================================================
# AUDIO VAE
# =========================================================

download \
    "smthem/LTX-2.3-test-gguf" \
    "ltx-2.3-22b-distilled_audio_vae.safetensors" \
    "$COMFY/models/vae"


# =========================================================
# SPATIAL UPSCALER
# =========================================================

download \
    "Lightricks/LTX-2.3" \
    "ltx-2.3-spatial-upscaler-x2-1.1.safetensors" \
    "$COMFY/models/latent_upscale_models"


# =========================================================
# LORA
# =========================================================

download \
    "Lightricks/LTX-2.3" \
    "gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors" \
    "$COMFY/models/loras"


echo "=== Descarga de modelos LTX-2.3 completada ==="
