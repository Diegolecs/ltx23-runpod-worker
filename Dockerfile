FROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

COPY requirements.txt /tmp/requirements.txt
COPY download_models.sh /download_models.sh
COPY handler.py /handler.py

RUN echo "=== VERIFICANDO HANDLER ===" && \
    grep -n "DEBUG TEST: ENTRE A handler(job)" /handler.py && \
    echo "=== HANDLER CORRECTO ==="

RUN chmod +x /download_models.sh

RUN git clone --depth 1 \
    https://github.com/Lightricks/ComfyUI-LTXVideo.git \
    /comfyui/custom_nodes/ComfyUI-LTXVideo

RUN git clone --depth 1 \
    https://github.com/city96/ComfyUI-GGUF.git \
    /comfyui/custom_nodes/ComfyUI-GGUF

RUN git clone --depth 1 \
    https://github.com/kijai/ComfyUI-KJNodes.git \
    /comfyui/custom_nodes/ComfyUI-KJNodes

RUN pip install --no-cache-dir \
    -r /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt \
    -r /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt \
    -r /tmp/requirements.txt

ENTRYPOINT ["/bin/bash", "-c", "echo '=== Descargando modelos antes de iniciar ComfyUI ==='; /download_models.sh; DOWNLOAD_STATUS=$?; if [ $DOWNLOAD_STATUS -ne 0 ]; then echo 'ERROR: Falló la descarga de modelos.'; exit $DOWNLOAD_STATUS; fi; echo '=== Iniciando ComfyUI + Handler personalizado ==='; python3 -u /handler.py"]
