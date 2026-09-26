FROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

# Dependencias propias del worker
COPY requirements.txt /tmp/requirements.txt

# Script de descarga de modelos
COPY download_models.sh /download_models.sh
RUN chmod +x /download_models.sh

# LTX-2.3
RUN git clone --depth 1 \
    https://github.com/Lightricks/ComfyUI-LTXVideo.git \
    /comfyui/custom_nodes/ComfyUI-LTXVideo

# GGUF support
RUN git clone --depth 1 \
    https://github.com/city96/ComfyUI-GGUF.git \
    /comfyui/custom_nodes/ComfyUI-GGUF

# KJNodes
RUN git clone --depth 1 \
    https://github.com/kijai/ComfyUI-KJNodes.git \
    /comfyui/custom_nodes/ComfyUI-KJNodes

# Instalar dependencias
RUN pip install --no-cache-dir \
    -r /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt \
    -r /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt \
    -r /tmp/requirements.txt

# Arrancar ComfyUI primero.
# Esperar a que su estructura de modelos exista.
# Luego descargar los modelos.
ENTRYPOINT ["/bin/bash", "-c", "\
    /start.sh & \
    START_PID=$!; \
    echo 'Esperando inicialización de ComfyUI...'; \
    until [ -d /comfyui/models ]; do \
        sleep 2; \
    done; \
    echo 'ComfyUI inicializado.'; \
    /download_models.sh; \
    wait $START_PID \
"]
