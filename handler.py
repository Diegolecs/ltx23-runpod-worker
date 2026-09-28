import runpod
import rp_upload
import json
import urllib.request
import time
import os
import requests
import base64
from io import BytesIO
import websocket
import uuid
import tempfile
import socket
import traceback
import logging

from network_volume import (
    is_network_volume_debug_enabled,
    run_network_volume_diagnostics,
)


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

COMFY_HOST = "127.0.0.1:8188"

COMFY_API_AVAILABLE_INTERVAL_MS = int(
    os.environ.get("COMFY_API_AVAILABLE_INTERVAL_MS", "50")
)

COMFY_API_AVAILABLE_MAX_RETRIES = int(
    os.environ.get("COMFY_API_AVAILABLE_MAX_RETRIES", "0")
)

COMFY_API_FALLBACK_MAX_RETRIES = 500

COMFY_PID_FILE = "/tmp/comfyui.pid"


# ============================================================================
# MAPEO DE MODELOS
# ============================================================================

MODEL_LOADER_NODES = {
    "CheckpointLoaderSimple": (
        "checkpoints",
        ("ckpt_name",)
    ),

    "LoraLoader": (
        "loras",
        ("lora_name",)
    ),

    "VAELoader": (
        "vae",
        ("vae_name",)
    ),

    "DualCLIPLoader": (
        "text_encoders",
        ("clip_name1", "clip_name2")
    ),

    "TripleCLIPLoader": (
        "text_encoders",
        ("clip_name1", "clip_name2", "clip_name3")
    ),

    "UNETLoader": (
        "diffusion_models",
        ("unet_name",)
    ),

    "UnetLoaderGGUF": (
        "diffusion_models",
        ("unet_name",)
    ),

    "Hy3DModelLoader": (
        "diffusion_models",
        ("model",)
    ),

    "UpscaleModelLoader": (
        "upscale_models",
        ("model_name",)
    ),
}


MODEL_TYPE_VOLUME_DIRS = {
    "checkpoints": "/runpod-volume/models/checkpoints/",
    "loras": "/runpod-volume/models/loras/",
    "vae": "/runpod-volume/models/vae/",
    "text_encoders": "/runpod-volume/models/clip/",
    "diffusion_models": "/runpod-volume/models/unet/",
    "upscale_models": "/runpod-volume/models/upscale_models/",
}


# ============================================================================
# UTILIDADES
# ============================================================================

def validate_input(job_input):
    """
    Valida la entrada principal del job.
    """

    if not isinstance(job_input, dict):
        return None, "Input debe ser un objeto JSON."

    workflow = job_input.get("workflow")

    if workflow is None:
        return None, "Falta 'workflow' en el input."

    if not isinstance(workflow, dict):
        return None, "'workflow' debe ser un objeto JSON."

    return job_input, None


def check_server(url):
    """
    Comprueba que ComfyUI esté disponible.
    """

    retries = 0

    while True:
        try:
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                return True

        except Exception:
            pass

        retries += 1

        if (
            COMFY_API_AVAILABLE_MAX_RETRIES > 0
            and retries >= COMFY_API_AVAILABLE_MAX_RETRIES
        ):
            return False

        if retries >= COMFY_API_FALLBACK_MAX_RETRIES:
            return False

        time.sleep(COMFY_API_AVAILABLE_INTERVAL_MS / 1000)


def validate_workflow_models(workflow):
    """
    Comprueba que los modelos referenciados por el workflow
    existan en las opciones disponibles de ComfyUI.
    """

    try:
        response = requests.get(
            f"http://{COMFY_HOST}/object_info",
            timeout=30
        )

        if response.status_code != 200:
            return True, None

        object_info = response.json()

    except Exception:
        return True, None

    errors = []

    for node_id, node in workflow.items():

        if not isinstance(node, dict):
            continue

        class_type = node.get("class_type")

        if class_type not in MODEL_LOADER_NODES:
            continue

        config = MODEL_LOADER_NODES[class_type]

        model_type = config[0]
        input_names = config[1]

        node_info = object_info.get(class_type)

        if not node_info:
            continue

        input_data = node_info.get("input", {})

        required_inputs = input_data.get("required", {})

        for input_name in input_names:

            if input_name not in node.get("inputs", {}):
                continue

            model_name = node["inputs"][input_name]

            if not isinstance(model_name, str):
                continue

            available = []

            if input_name in required_inputs:
                definition = required_inputs[input_name]

                if isinstance(definition, list) and definition:
                    first = definition[0]

                    if isinstance(first, list):
                        available = first

            if available and model_name not in available:
                errors.append(
                    f"{class_type} {node_id}: "
                    f"{model_name} no está disponible en {available}"
                )

    if errors:
        return False, errors

    return True, None


def upload_images(workflow):
    """
    Placeholder para compatibilidad con workflows que utilicen imágenes.
    """

    return workflow


def queue_prompt(workflow, client_id):
    """
    Envía el workflow a ComfyUI.
    """

    payload = {
        "prompt": workflow,
        "client_id": client_id
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        f"http://{COMFY_HOST}/prompt",
        data=data,
        headers={
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(request) as response:
        return json.loads(response.read())


def get_history(prompt_id):
    """
    Obtiene el historial de ejecución.
    """

    response = requests.get(
        f"http://{COMFY_HOST}/history/{prompt_id}",
        timeout=30
    )

    if response.status_code != 200:
        return None

    return response.json()


def get_images_from_history(history, prompt_id):
    """
    Obtiene los archivos generados por ComfyUI.
    """

    if not history:
        return []

    prompt_history = history.get(prompt_id)

    if not prompt_history:
        return []

    outputs = prompt_history.get("outputs", {})

    images = []

    for node_id, output in outputs.items():

        for image in output.get("images", []):

            filename = image.get("filename")
            subfolder = image.get("subfolder", "")
            image_type = image.get("type", "output")

            if not filename:
                continue

            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": image_type
            }

            try:
                response = requests.get(
                    f"http://{COMFY_HOST}/view",
                    params=params,
                    timeout=120
                )

                if response.status_code != 200:
                    continue

                images.append({
                    "filename": filename,
                    "subfolder": subfolder,
                    "type": image_type,
                    "data": base64.b64encode(
                        response.content
                    ).decode("utf-8")
                })

            except Exception:
                continue

    return images


# ============================================================================
# HANDLER
# ============================================================================

def handler(job):

    try:

        # ================================================================
        # NETWORK VOLUME DIAGNOSTICS
        # ================================================================

        if is_network_volume_debug_enabled():
            try:
                run_network_volume_diagnostics()
            except Exception:
                traceback.print_exc()

        # ================================================================
        # INPUT
        # ================================================================

        job_input = job["input"]
        job_id = job["id"]

        # ================================================================
        # ESPERAR A QUE TERMINE LA DESCARGA DE MODELOS
        # ================================================================

        models_ready_file = "/tmp/ltx_models_ready"

        max_wait_seconds = 1800
        wait_interval = 2
        waited = 0

        print(
            "worker-comfyui - "
            "Waiting for LTX models to be ready..."
        )

        while not os.path.exists(models_ready_file):

            if waited >= max_wait_seconds:

                return {
                    "error": (
                        "Timeout waiting for LTX models to finish "
                        "downloading after "
                        f"{max_wait_seconds} seconds."
                    )
                }

            time.sleep(wait_interval)
            waited += wait_interval

        print(
            "worker-comfyui - "
            "LTX models are ready."
        )

        # ================================================================
        # VALIDAR INPUT
        # ================================================================

        validated_data, error_message = validate_input(
            job_input
        )

        if error_message:
            return {
                "error": error_message
            }

        workflow = validated_data["workflow"]

        # ================================================================
        # COMPROBAR COMFYUI
        # ================================================================

        if not check_server(
            f"http://{COMFY_HOST}/"
        ):
            return {
                "error": "ComfyUI no está disponible."
            }

        # ================================================================
        # SUBIR IMÁGENES SI LAS HUBIERA
        # ================================================================

        workflow = upload_images(workflow)

        # ================================================================
        # PREFLIGHT DE MODELOS
        # ================================================================

        models_valid, model_errors = validate_workflow_models(
            workflow
        )

        if not models_valid:

            print(
                "worker-comfyui - "
                "Workflow model validation warnings/errors:"
            )

            for error in model_errors:
                print(error)

        # ================================================================
        # WEBSOCKET
        # ================================================================

        client_id = str(uuid.uuid4())

        ws = websocket.WebSocket()

        ws.connect(
            f"ws://{COMFY_HOST}/ws?clientId={client_id}",
            timeout=30
        )

        # ================================================================
        # ENCOLAR WORKFLOW
        # ================================================================

        queue_result = queue_prompt(
            workflow,
            client_id
        )

        prompt_id = queue_result.get("prompt_id")

        if not prompt_id:
            ws.close()

            return {
                "error": (
                    "ComfyUI no devolvió prompt_id.",
                    queue_result
                )
            }

        print(
            f"worker-comfyui - "
            f"Queued prompt: {prompt_id}"
        )

        # ================================================================
        # ESPERAR EJECUCIÓN
        # ================================================================

        while True:

            try:

                message = ws.recv()

                if not message:
                    continue

                if isinstance(message, bytes):
                    continue

                data = json.loads(message)

                msg_type = data.get("type")

                msg_data = data.get("data", {})

                if msg_type == "executing":

                    current_prompt_id = msg_data.get(
                        "prompt_id"
                    )

                    node = msg_data.get("node")

                    if (
                        current_prompt_id == prompt_id
                        and node is None
                    ):
                        print(
                            "worker-comfyui - "
                            "Execution finished."
                        )
                        break

                elif msg_type == "execution_error":

                    print(
                        "worker-comfyui - "
                        "Execution error:",
                        msg_data
                    )

                    ws.close()

                    return {
                        "error": (
                            "ComfyUI execution error",
                            msg_data
                        )
                    }

            except websocket.WebSocketTimeoutException:
                continue

            except Exception:
                traceback.print_exc()
                break

        ws.close()

        # ================================================================
        # OBTENER HISTORIAL
        # ================================================================

        history = None

        for _ in range(60):

            history = get_history(prompt_id)

            if history and prompt_id in history:
                break

            time.sleep(1)

        # ================================================================
        # OBTENER IMÁGENES
        # ================================================================

        images = get_images_from_history(
            history,
            prompt_id
        )

        # ================================================================
        # RESULTADO
        # ================================================================

        return {
            "job_id": job_id,
            "prompt_id": prompt_id,
            "images": images
        }

    except Exception as e:

        traceback.print_exc()

        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# ============================================================================
# RUNPOD
# ============================================================================

runpod.serverless.start({
    "handler": handler
})
