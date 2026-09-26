FROM runpod/worker-comfyui:5.10.0-base-cuda12.8.1

# LTX-2.3
RUN git clone --depth 1 \
    https://github.com/Lightricks/ComfyUI-LTXVideo.git \
    /comfyui/custom_nodes/ComfyUI-LTXVideo

# GGUF support
RUN git clone --depth 1 \
    https://github.com/city96/ComfyUI-GGUF.git \
    /comfyui/custom_nodes/ComfyUI-GGUF

# KJNodes - required by the LTX-2.3 optimized workflows
RUN git clone --depth 1 \
    https://github.com/kijai/ComfyUI-KJNodes.git \
    /comfyui/custom_nodes/ComfyUI-KJNodes

# Install dependencies for custom nodes
RUN for r in /comfyui/custom_nodes/*/requirements.txt; do \
        if [ -f "$r" ]; then \
            uv pip install --system -r "$r"; \
        fi; \
    done

# RunPod Serverless
ENTRYPOINT []
CMD ["python3", "-u", "/handler.py"]
