#!/bin/bash
set -e

echo "=== Descarga mínima LTX-2.3 Q4 + Gemma GGUF ==="

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


# ============================================================
# FUNCIÓN DE DESCARGA
# ============================================================

download() {

    REPO="$1"
    FILE="$2"
    DEST="$3"

    NAME="$(basename "$FILE")"
    TARGET="$DEST/$NAME"

    if [ -f "$TARGET" ]; then

        echo "Ya existe: $TARGET"

        return

    fi

    echo "Descargando: $NAME"
    echo "Repo: $REPO"
    echo "Archivo: $FILE"

    mkdir -p "$DEST"

    hf download \
        "$REPO" \
        "$FILE" \
        --local-dir "$DEST" \
        --token "$HF_TOKEN"

    if [ ! -f "$TARGET" ]; then

        echo "ERROR: No apareció el archivo esperado:"
        echo "$TARGET"

        exit 1

    fi

    echo "OK: $TARGET"
}


# ============================================================
# LIMPIAR GEMMA SCALED FP8 ANTERIOR
#
# Este archivo NO es compatible con DualCLIPLoaderGGUF.
# Lo eliminamos para liberar espacio.
# ============================================================

OLD_GEMMA="$COMFY/models/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors"

if [ -f "$OLD_GEMMA" ]; then

    echo "=== ELIMINANDO GEMMA SCALED FP8 ANTERIOR ==="

    rm -f "$OLD_GEMMA"

    echo "Eliminado: $OLD_GEMMA"

fi


# ============================================================
# MODELO PRINCIPAL — LTX-2.3 Q4
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
# TEXT PROJECTION LTX-2.3
# ============================================================

download \
    "Kijai/LTX2.3_comfy" \
    "text_encoders/ltx-2.3_text_projection_bf16.safetensors" \
    "$COMFY/models/text_encoders"


# ============================================================
# GEMMA 3 12B — GGUF Q2_K
#
# Compatible con DualCLIPLoaderGGUF.
# Tamaño aproximado: 4.77 GB.
# ============================================================

download \
    "tensorblock/gemma-3-12b-it-GGUF" \
    "gemma-3-12b-it-Q2_K.gguf" \
    "$COMFY/models/text_encoders"


# ============================================================
# VERIFICACIÓN
# ============================================================

echo ""
echo "=== MODELOS INSTALADOS ==="

find "$COMFY/models" \
    -type f \
    | sort


# ============================================================
# COMPROBACIÓN ESPECÍFICA
# ============================================================

echo ""
echo "=== COMPROBACIÓN LTX ==="

REQUIRED_FILES=(

    "$COMFY/models/unet/LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf"

    "$COMFY/models/text_encoders/gemma-3-12b-it-Q2_K.gguf"

    "$COMFY/models/text_encoders/ltx-2.3_text_projection_bf16.safetensors"

    "$COMFY/models/vae/LTX23_video_vae_bf16.safetensors"

    "$COMFY/models/vae/LTX23_audio_vae_bf16.safetensors"
)


for FILE in "${REQUIRED_FILES[@]}"; do

    if [ ! -f "$FILE" ]; then

        echo "ERROR: Falta:"
        echo "$FILE"

        exit 1

    fi

    echo "OK: $FILE"

done


# ============================================================
# SEÑAL PARA EL HANDLER
# ============================================================

touch /tmp/ltx_models_ready

echo ""
echo "=== SEÑAL: modelos listos ==="
echo "=== LTX-2.3 READY ==="
