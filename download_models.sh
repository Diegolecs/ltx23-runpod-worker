#!/bin/bash
set -e

echo "=== Descarga mínima LTX-2.3 Q4 ==="

COMFY="/runpod-volume"

mkdir -p "$COMFY/models/unet"
mkdir -p "$COMFY/models/text_encoders"
mkdir -p "$COMFY/models/vae"
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

    NAME="$(basename "$FILE")"

    if [ -f "$DEST/$NAME" ]; then
        echo "Ya existe: $NAME"
        return
    fi

    echo "Descargando: $NAME"

    TMP="/tmp/$NAME"

    hf download "$REPO" "$FILE" \
        --local-dir "/tmp/ltx-download" \
        --token "$HF_TOKEN"

    mkdir -p "$DEST"

    find "/tmp/ltx-download" \
        -type f \
        -name "$NAME" \
        -exec cp {} "$DEST/$NAME" \;

    rm -rf "/tmp/ltx-download"
}

# ============================================================
# MODELO PRINCIPAL — Q4
# ============================================================

download \
    "QuantStack/LTX-2.3-GGUF" \
    "LTX-2.3-distilled-1.1/LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf" \
    "$COMFY/models/unet"

# ============================================================
# VIDEO VAE
# ============================================================

download \
    "smthem/LTX-2.3-test-gguf" \
    "ltx-2.3-22b-distilled_video_vae.safetensors" \
    "$COMFY/models/vae"

# ============================================================
# AUDIO VAE
# ============================================================

download \
    "smthem/LTX-2.3-test-gguf" \
    "ltx-2.3-22b-distilled_audio_vae.safetensors" \
    "$COMFY/models/vae"

# ============================================================
# EMBEDDING CONNECTORS
# ============================================================

download \
    "smthem/LTX-2.3-test-gguf" \
    "ltx-2.3-22b-distilled_embeddings_connectors.safetensors" \
    "$COMFY/models/text_encoders"

# ============================================================
# GEMMA TEXT ENCODER
# ============================================================

download \
    "Comfy-Org/ltx-2" \
    "gemma_3_12B_it_fp8_e4m3fn.safetensors" \
    "$COMFY/models/text_encoders"

echo "=== Descarga mínima LTX-2.3 Q4 completada ==="

echo "=== Modelos instalados ==="
find "$COMFY/models" -type f | sort
