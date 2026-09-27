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
    "Kijai/LTX2.3_comfy" \
    "vae/LTX23_video_vae_bf16.safetensors" \
    "$COMFY/models/vae"

# ============================================================
# AUDIO VAE
# ============================================================

download \
    "Kijai/LTX2.3_comfy" \
    "vae/LTX23_audio_vae_bf16.safetensors" \
    "$COMFY/models/vae"

# ============================================================
# PROYECCIÓN DE TEXTO (conecta Gemma con el DiT de LTX-2.3)
# ============================================================

download \
    "Kijai/LTX2.3_comfy" \
    "text_encoders/ltx-2.3_text_projection_bf16.safetensors" \
    "$COMFY/models/text_encoders"

# ============================================================
# GEMMA TEXT ENCODER (versión correcta para LTX-2.3, no LTX-2)
# ============================================================

download \
    "Comfy-Org/ltx-2" \
    "split_files/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors" \
    "$COMFY/models/text_encoders"

echo "=== Descarga mínima LTX-2.3 Q4 completada ==="

echo "=== Modelos instalados ==="
find "$COMFY/models" -type f | sort

