FROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

COPY requirements.txt /tmp/requirements.txt
COPY download_models.sh /download_models.sh
COPY ltx_handler.py /ltx_handler.py

RUN echo "=== VERIFICANDO HANDLER REAL ===" && \
    grep -n "CALLBACK REAL OK" /ltx_handler.py && \
    echo "=== HANDLER REAL CONFIRMADO ==="

RUN chmod +x /download_mFROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

COPY requirements.txt /tmp/requirements.txt
COPY download_models.sh /download_models.sh
COPY ltx_handler.py /ltx_handler.py

RUN echo "=== VERIFICANDO HANDLER REAL ===" && \
    grep -n "def handler(job)" /ltx_handler.py && \
    echo "=== HANDLER REAL CONFIRMADO ==="

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

ENTRYPOINT ["/bin/bash", "-c", "echo '=== LTX HANDLER PROPIO ==='; /download_models.sh; DOWNLOAD_STATUS=$?; if [ $DOWNLOAD_STATUS -ne 0 ]; then echo 'ERROR: Falló la descarga de modelos.'; exit $DOWNLOAD_STATUS; fi; echo '=== EJECUTANDO LTX HANDLER PROPIO ==='; python3 -u /ltx_handler.py"]odels.sh

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

ENTRYPOINT ["/bin/bash", "-c", "echo '=== LTX HANDLER PROPIO ==='; /download_models.sh; DOWNLOAD_STATUS=$?; if [ $DOWNLOAD_STATUS -ne 0 ]; then echo 'ERROR: Falló la descarga de modelos.'; exit $DOWNLOAD_STATUS; fi; echo '=== EJECUTANDO LTX HANDLER PROPIO ==='; python3 -u /ltx_handler.py"]
