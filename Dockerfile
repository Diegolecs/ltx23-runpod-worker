FROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

WORKDIR /comfyui

# LTX-2.3 custom nodes
RUN git clone --depth 1 https://github.com/Lightricks/ComfyUI-LTXVideo.git \
    /comfyui/custom_nodes/ComfyUI-LTXVideo

RUN git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git \
    /comfyui/custom_nodes/ComfyUI-GGUF

# Install custom-node dependencies
RUN if [ -f /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt ]; then \
        pip install --no-cache-dir \
        -r /comfyui/custom_nodes/ComfyUI-LTXVideo/requirements.txt; \
    fi

RUN if [ -f /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt ]; then \
        pip install --no-cache-dir \
        -r /comfyui/custom_nodes/ComfyUI-GGUF/requirements.txt; \
    fi

# RunPod Serverless worker
WORKDIR /

CMD ["python", "/rp_handler.py"]
