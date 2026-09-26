FROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

# Install LTX-2.3 custom nodes
RUN git clone --depth 1 \
    https://github.com/Lightricks/ComfyUI-LTXVideo.git \
    /comfyui/custom_nodes/ComfyUI-LTXVideo

RUN git clone --depth 1 \
    https://github.com/city96/ComfyUI-GGUF.git \
    /comfyui/custom_nodes/ComfyUI-GGUF

# Install custom-node dependencies into the Python
# environment used by ComfyUI.
RUN for r in /comfyui/custom_nodes/*/requirements.txt; do \
        if [ -f "$r" ]; then \
            uv pip install --system -r "$r"; \
        fi; \
    done
