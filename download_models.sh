#!/bin/bash
set -e

echo "=== DESCARGA MINIMA LTX-2.3 Q4 + GEMMA GGUF ==="

COMFY="/runpod-volume"

mkdir -p "$COMFY/models/unet"
mkdir -p "$COMFY/models/text_encoders"
mkdir -p "$COMFY/models/clip"
mkdir -p "$COMFY/models/vae"
mkdir -p "$COMFY/models/latent_upscale_models"


# ============================================================
# TOKEN
# ============================================================

if [ -z "$HF_TOKEN" ]; then
    echo "ERROR: HF_TOKEN no está definido."
    exit 1
fi

export HF_TOKEN


# ============================================================
# HUGGINGFACE
# ============================================================

pip install --no-cache-dir -q huggingface_hub


# ============================================================
# FUNCION DE DESCARGA
# ============================================================

download() {

    REPO="$1"
    FILE="$2"
    DEST="$3"

    NAME="$(basename "$FILE")"
    TARGET="$DEST/$NAME"

    if [ -f "$TARGET" ]; then

        echo "Ya existe: $TARGET"

        return 0
    fi

    echo "=============================================="
    echo "Descargando: $NAME"
    echo "Repo: $REPO"
    echo "Archivo: $FILE"
    echo "=============================================="

    TMP_DIR="/tmp/ltx-download"

    rm -rf "$TMP_DIR"
    mkdir -p "$TMP_DIR"

    hf download \
        "$REPO" \
        "$FILE" \
        --local-dir "$TMP_DIR" \
        --token "$HF_TOKEN"

    FOUND_FILE="$(find "$TMP_DIR" -type f -name "$NAME" -print -quit)"

    if [ -z "$FOUND_FILE" ]; then

        echo "ERROR: Hugging Face descargó pero no encontramos:"
        echo "$NAME"

        echo "Contenido descargado:"
        find "$TMP_DIR" -type f | sort

        exit 1
    fi

    mkdir -p "$DEST"

    cp "$FOUND_FILE" "$TARGET"

    rm -rf "$TMP_DIR"

    if [ ! -f "$TARGET" ]; then

        echo "ERROR: No se pudo crear:"
        echo "$TARGET"

        exit 1
    fi

    echo "OK: $TARGET"
}


# ============================================================
# MIGRAR GEMMA EXISTENTE
# ============================================================

OLD_GEMMA="$COMFY/models/text_encoders/gemma-3-12b-it-Q2_K.gguf"
NEW_GEMMA="$COMFY/models/clip/gemma-3-12b-it-Q2_K.gguf"

if [ -f "$OLD_GEMMA" ] && [ ! -f "$NEW_GEMMA" ]; then

    echo "=== MOVIENDO GEMMA A models/clip ==="

    mv "$OLD_GEMMA" "$NEW_GEMMA"

    echo "OK: $NEW_GEMMA"

fi


# ============================================================
# MIGRAR TEXT PROJECTION EXISTENTE
# ============================================================

OLD_PROJECTION="$COMFY/models/text_encoders/ltx-2.3_text_projection_bf16.safetensors"
NEW_PROJECTION="$COMFY/models/clip/ltx-2.3_text_projection_bf16.safetensors"

if [ -f "$OLD_PROJECTION" ] && [ ! -f "$NEW_PROJECTION" ]; then

    echo "=== MOVIENDO TEXT PROJECTION A models/clip ==="

    mv "$OLD_PROJECTION" "$NEW_PROJECTION"

    echo "OK: $NEW_PROJECTION"

fi


# ============================================================
# LIMPIAR GEMMA SCALED ANTIGUO
# ============================================================

OLD_SCALED="$COMFY/models/text_encoders/gemma_3_12B_it_fp8_scaled.safetensors"

if [ -f "$OLD_SCALED" ]; then

    echo "=== ELIMINANDO GEMMA SCALED ANTIGUO ==="

    rm -f "$OLD_SCALED"

    echo "Eliminado: $OLD_SCALED"

fi


# ============================================================
# LTX-2.3 Q4 GGUF
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
# TEXT PROJECTION
# ============================================================

download \
    "Kijai/LTX2.3_comfy" \
    "text_encoders/ltx-2.3_text_projection_bf16.safetensors" \
    "$COMFY/models/clip"


# ============================================================
# GEMMA 3 12B GGUF
# ============================================================

download \
    "tensorblock/gemma-3-12b-it-GGUF" \
    "gemma-3-12b-it-Q2_K.gguf" \
    "$COMFY/models/clip"


# ============================================================
# MOSTRAR MODELOS
# ============================================================

echo ""
echo "=============================================="
echo "MODELOS INSTALADOS"
echo "=============================================="

find "$COMFY/models" -type f | sort


# ============================================================
# VERIFICAR ARCHIVOS
# ============================================================

REQUIRED_FILES=(

    "$COMFY/models/unet/LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf"

    "$COMFY/models/clip/gemma-3-12b-it-Q2_K.gguf"

    "$COMFY/models/clip/ltx-2.3_text_projection_bf16.safetensors"

    "$COMFY/models/vae/LTX23_video_vae_bf16.safetensors"

    "$COMFY/models/vae/LTX23_audio_vae_bf16.safetensors"
)


echo ""
echo "=============================================="
echo "VERIFICANDO ARCHIVOS"
echo "=============================================="


for FILE in "${REQUIRED_FILES[@]}"; do

    if [ ! -f "$FILE" ]; then

        echo "ERROR: Falta:"
        echo "$FILE"

        exit 1
    fi

    echo "OK: $FILE"

done


# ============================================================
# VERIFICACION ESPECIAL DEL DIRECTORIO CLIP
# ============================================================

echo ""
echo "=============================================="
echo "MODELOS CLIP DISPONIBLES"
echo "=============================================="

find "$COMFY/models/clip" \
    -maxdepth 1 \
    -type f \
    -printf "%f\n" \
    | sort


# ============================================================
# SEÑAL
# ============================================================

touch /tmp/ltx_models_ready

echo ""
echo "=============================================="
echo "LTX-2.3 READY"
echo "=============================================="
