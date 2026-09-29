```python
import runpod
import json
import urllib.request
import time
import os
import requests
import base64
import websocket
import uuid
import traceback

from network_volume import (
    is_network_volume_debug_enabled,
    run_network_volume_diagnostics,
)

COMFY_HOST = "127.0.0.1:8188"

COMFY_API_AVAILABLE_INTERVAL_MS = int(
    os.environ.get("COMFY_API_AVAILABLE_INTERVAL_MS", "100")
)

COMFY_API_AVAILABLE_MAX_RETRIES = int(
    os.environ.get("COMFY_API_AVAILABLE_MAX_RETRIES", "0")
)

COMFY_API_FALLBACK_MAX_RETRIES = 1200

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
    "text_encoders": "/runpod-volume/models/text_encoders/",
    "diffusion_models": "/runpod-volume/models/unet/",
    "upscale_models": "/runpod-volume/models/upscale_models/",
}


def validate_input(job_input):
    print("DEBUG 1: Validando input del job...")

    if not isinstance(job_input, dict):
        return None, "Input debe ser un objeto JSON."

    workflow = job_input.get("workflow")

    if workflow is None:
        return None, "Falta 'workflow' en el input."

    if not isinstance(workflow, dict):
        return None, "'workflow' debe ser un objeto JSON."

    print(
        f"DEBUG 1 OK: workflow recibido con "
        f"{len(workflow)} nodos."
    )

    return job_input, None


def check_server(url):
    print(
        "DEBUG 2: Esperando a que ComfyUI responda..."
    )

    retries = 0

    while True:
        try:
            response = requests.get(
                url,
                timeout=5
            )

            if response.status_code == 200:
                print(
                    "DEBUG 2 OK: ComfyUI responde "
                    f"HTTP {response.status_code}."
                )
                return True

            print(
                "DEBUG 2: ComfyUI respondió "
                f"HTTP {response.status_code}."
            )

        except Exception as e:
            if retries % 10 == 0:
                print(
                    "DEBUG 2: ComfyUI todavía no responde. "
                    f"Intento {retries}. Error: {e}"
                )

        retries += 1

        if (
            COMFY_API_AVAILABLE_MAX_RETRIES > 0
            and retries >= COMFY_API_AVAILABLE_MAX_RETRIES
        ):
            print(
                "DEBUG 2 ERROR: Se alcanzó "
                "COMFY_API_AVAILABLE_MAX_RETRIES."
            )
            return False

        if retries >= COMFY_API_FALLBACK_MAX_RETRIES:
            print(
                "DEBUG 2 ERROR: Se alcanzó el máximo "
                "de intentos esperando ComfyUI."
            )
            return False

        time.sleep(
            COMFY_API_AVAILABLE_INTERVAL_MS / 1000
        )


def validate_workflow_models(workflow):
    print(
        "DEBUG 3: Consultando /object_info de ComfyUI..."
    )

    try:
        response = requests.get(
            f"http://{COMFY_HOST}/object_info",
            timeout=30
        )

        print(
            "DEBUG 3: /object_info respondió "
            f"HTTP {response.status_code}."
        )

        if response.status_code != 200:
            print(
                "DEBUG 3: No se pudo consultar "
                "/object_info. Continuando..."
            )
            return True, None

        object_info = response.json()

    except Exception as e:
        print(
            "DEBUG 3: Error consultando /object_info: "
            f"{e}"
        )
        print(
            "DEBUG 3: Continuando sin validación "
            "de modelos."
        )
        return True, None

    errors = []

    for node_id, node in workflow.items():

        if not isinstance(node, dict):
            continue

        class_type = node.get("class_type")

        if class_type not in MODEL_LOADER_NODES:
            continue

        config = MODEL_LOADER_NODES[class_type]
        input_names = config[1]

        node_info = object_info.get(class_type)

        if not node_info:
            continue

        input_data = node_info.get("input", {})
        required_inputs = input_data.get(
            "required",
            {}
        )

        for input_name in input_names:

            if input_name not in node.get(
                "inputs",
                {}
            ):
                continue

            model_name = node["inputs"][input_name]

            if not isinstance(model_name, str):
                continue

            available = []

            if input_name in required_inputs:

                definition = required_inputs[
                    input_name
                ]

                if (
                    isinstance(definition, list)
                    and definition
                ):

                    first = definition[0]

                    if isinstance(first, list):
                        available = first

            if (
                available
                and model_name not in available
            ):

                errors.append(
                    f"{class_type} {node_id}: "
                    f"{model_name} no está disponible "
                    f"en {available}"
                )

    if errors:

        print(
            "DEBUG 3: Se encontraron advertencias "
            "de modelos:"
        )

        for error in errors:
            print(
                f"DEBUG 3 WARNING: {error}"
            )

    else:

        print(
            "DEBUG 3 OK: Validación de modelos "
            "terminada sin errores."
        )

    return True, None


def upload_images(workflow):
    print(
        "DEBUG 4: Procesando imágenes del workflow..."
    )

    return workflow


def queue_prompt(workflow, client_id):
    print(
        "DEBUG 6: Enviando workflow a "
        "http://127.0.0.1:8188/prompt ..."
    )

    payload = {
        "prompt": workflow,
        "client_id": client_id
    }

    data = json.dumps(
        payload
    ).encode("utf-8")

    request = urllib.request.Request(
        f"http://{COMFY_HOST}/prompt",
        data=data,
        headers={
            "Content-Type": "application/json"
        }
    )

    with urllib.request.urlopen(
        request,
        timeout=60
    ) as response:

        result = json.loads(
            response.read()
        )

        print(
            "DEBUG 6 OK: ComfyUI respondió al "
            "endpoint /prompt."
        )

        return result


def get_history(prompt_id):
    response = requests.get(
        f"http://{COMFY_HOST}/history/{prompt_id}",
        timeout=30
    )

    if response.status_code != 200:
        return None

    return response.json()


def get_outputs_from_history(
    history,
    prompt_id
):

    if not history:
        return []

    prompt_history = history.get(
        prompt_id
    )

    if not prompt_history:
        return []

    outputs = prompt_history.get(
        "outputs",
        {}
    )

    results = []

    for node_id, output in outputs.items():

        for image in output.get(
            "images",
            []
        ):

            filename = image.get(
                "filename"
            )

            subfolder = image.get(
                "subfolder",
                ""
            )

            image_type = image.get(
                "type",
                "output"
            )

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

                results.append({
                    "type": "image",
                    "filename": filename,
                    "subfolder": subfolder,
                    "data": base64.b64encode(
                        response.content
                    ).decode("utf-8")
                })

            except Exception:
                traceback.print_exc()

        for video in output.get(
            "gifs",
            []
        ):

            filename = video.get(
                "filename"
            )

            subfolder = video.get(
                "subfolder",
                ""
            )

            video_type = video.get(
                "type",
                "output"
            )

            if not filename:
                continue

            params = {
                "filename": filename,
                "subfolder": subfolder,
                "type": video_type
            }

            try:

                response = requests.get(
                    f"http://{COMFY_HOST}/view",
                    params=params,
                    timeout=300
                )

                if response.status_code != 200:
                    continue

                results.append({
                    "type": "video",
                    "filename": filename,
                    "subfolder": subfolder,
                    "data": base64.b64encode(
                        response.content
                    ).decode("utf-8")
                })

            except Exception:
                traceback.print_exc()

    return results


def handler(job):

    try:

        print(
            "========================================"
        )

        print(
            "LTX RUNPOD HANDLER - NUEVO JOB"
        )

        print(
            "========================================"
        )

        if is_network_volume_debug_enabled():

            print(
                "DEBUG: Ejecutando diagnóstico "
                "del Network Volume..."
            )

            try:

                run_network_volume_diagnostics()

            except Exception:

                traceback.print_exc()

        job_input = job["input"]
        job_id = job["id"]

        print(
            f"DEBUG: Job ID = {job_id}"
        )

        models_ready_file = (
            "/tmp/ltx_models_ready"
        )

        max_wait_seconds = 1800
        wait_interval = 2
        waited = 0

        print(
            "DEBUG 0: Esperando modelos LTX..."
        )

        while not os.path.exists(
            models_ready_file
        ):

            if waited >= max_wait_seconds:

                return {
                    "error": (
                        "Timeout waiting for LTX "
                        "models to finish downloading "
                        f"after {max_wait_seconds} "
                        "seconds."
                    )
                }

            time.sleep(
                wait_interval
            )

            waited += wait_interval

        print(
            "DEBUG 0 OK: LTX models are ready."
        )

        validated_data, error_message = (
            validate_input(job_input)
        )

        if error_message:

            print(
                "DEBUG 1 ERROR: "
                f"{error_message}"
            )

            return {
                "error": error_message
            }

        workflow = validated_data[
            "workflow"
        ]

        print(
            "DEBUG: Workflow recibido. "
            "Continuando..."
        )

        if not check_server(
            f"http://{COMFY_HOST}/"
        ):

            print(
                "DEBUG 2 ERROR: "
                "ComfyUI no está disponible."
            )

            return {
                "error": (
                    "ComfyUI no está disponible."
                )
            }

        print(
            "DEBUG: ComfyUI está disponible."
        )

        workflow = upload_images(
            workflow
        )

        print(
            "DEBUG: upload_images terminado."
        )

        models_valid, model_errors = (
            validate_workflow_models(
                workflow
            )
        )

        if not models_valid:

            print(
                "DEBUG: La validación devolvió "
                "un estado no válido."
            )

            if model_errors:

                for error in model_errors:
                    print(error)

        print(
            "DEBUG 5 OK: Preparación del workflow "
            "terminada."
        )

        client_id = str(
            uuid.uuid4()
        )

        print(
            "DEBUG 5: Creando conexión WebSocket..."
        )

        ws = websocket.WebSocket()

        ws.connect(
            f"ws://{COMFY_HOST}/ws"
            f"?clientId={client_id}",
            timeout=30
        )

        print(
            "DEBUG 5 OK: WebSocket conectado."
        )

        print(
            "DEBUG 6: Sending workflow to ComfyUI..."
        )

        queue_result = queue_prompt(
            workflow,
            client_id
        )

        print(
            "DEBUG 6 RESULT:",
            queue_result
        )

        prompt_id = queue_result.get(
            "prompt_id"
        )

        if not prompt_id:

            ws.close()

            return {
                "error": (
                    "ComfyUI no devolvió "
                    "prompt_id.",
                    queue_result
                )
            }

        print(
            "DEBUG 7 OK: Prompt en cola: "
            f"{prompt_id}"
        )

        print(
            "DEBUG 8: Esperando ejecución..."
        )

        while True:

            try:

                message = ws.recv()

                if not message:
                    continue

                if isinstance(
                    message,
                    bytes
                ):
                    continue

                data = json.loads(
                    message
                )

                msg_type = data.get(
                    "type"
                )

                msg_data = data.get(
                    "data",
                    {}
                )

                if msg_type == "executing":

                    current_prompt_id = (
                        msg_data.get(
                            "prompt_id"
                        )
                    )

                    node = msg_data.get(
                        "node"
                    )

                    if (
                        current_prompt_id
                        == prompt_id
                    ):

                        print(
                            "DEBUG 8: Ejecutando "
                            f"nodo: {node}"
                        )

                    if (
                        current_prompt_id
                        == prompt_id
                        and node is None
                    ):

                        print(
                            "DEBUG 8 OK: "
                            "Execution finished."
                        )

                        break

                elif msg_type == "execution_error":

                    print(
                        "DEBUG 8 ERROR: "
                        "ComfyUI execution error:",
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

                print(
                    "DEBUG 8: WebSocket timeout. "
                    "Seguimos esperando..."
                )

                continue

            except Exception:

                traceback.print_exc()

                break

        ws.close()

        print(
            "DEBUG 9: WebSocket cerrado."
        )

        print(
            "DEBUG 9: Buscando historial "
            "del prompt..."
        )

        history = None

        for attempt in range(60):

            history = get_history(
                prompt_id
            )

            if (
                history
                and prompt_id in history
            ):

                print(
                    "DEBUG 9 OK: Historial encontrado."
                )

                break

            if attempt % 5 == 0:

                print(
                    "DEBUG 9: Historial todavía "
                    "no disponible..."
                )

            time.sleep(1)

        print(
            "DEBUG 10: Extrayendo outputs..."
        )

        outputs = get_outputs_from_history(
            history,
            prompt_id
        )

        print(
            "DEBUG 10 OK: Outputs encontrados: "
            f"{len(outputs)}"
        )

        for output in outputs:

            print(
                "DEBUG OUTPUT:",
                output.get("type"),
                output.get("filename")
            )

        print(
            "========================================"
        )

        print(
            "JOB TERMINADO"
        )

        print(
            "========================================"
        )

        return {
            "job_id": job_id,
            "prompt_id": prompt_id,
            "outputs": outputs
        }

    except Exception as e:

        print(
            "========================================"
        )

        print(
            "HANDLER ERROR"
        )

        print(
            "========================================"
        )

        traceback.print_exc()

        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


runpod.serverless.start({
    "handler": handler
})
```
