import runpod
import json
import urllib.request
import time
import os
import requests
import websocket
import uuid
import traceback


COMFY_HOST = "127.0.0.1:8188"

READY_FILE = "/tmp/ltx_models_ready"

MAX_MODEL_WAIT = int(os.getenv("MAX_MODEL_WAIT", "1200"))
COMFY_RETRIES = int(os.getenv("COMFY_API_FALLBACK_MAX_RETRIES", "1200"))


def validate_input(job_input):
    if not isinstance(job_input, dict):
        return False, "job input no es un objeto"

    if "workflow" not in job_input:
        return False, "Falta 'workflow' en job input"

    if not isinstance(job_input["workflow"], dict):
        return False, "'workflow' debe ser un objeto JSON"

    return True, None


def check_server():
    url = f"http://{COMFY_HOST}/system_stats"

    for attempt in range(COMFY_RETRIES):
        try:
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                print(
                    f"DEBUG 2 OK: ComfyUI responde en intento {attempt + 1}",
                    flush=True
                )
                return True

        except Exception:
            pass

        if attempt % 10 == 0:
            print(
                f"DEBUG 2: Esperando ComfyUI... intento {attempt + 1}",
                flush=True
            )

        time.sleep(1)

    print("DEBUG 2 ERROR: ComfyUI no respondió", flush=True)
    return False


def get_object_info():
    url = f"http://{COMFY_HOST}/object_info"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def get_relevant_nodes():
    object_info = get_object_info()

    keywords = [
        "ltx",
        "gguf",
        "gemma",
        "vae",
        "sampler",
        "video",
        "audio",
        "combine",
        "text",
        "latent"
    ]

    relevant = {}

    for name, info in object_info.items():
        name_lower = name.lower()

        if any(keyword in name_lower for keyword in keywords):
            relevant[name] = info

    return relevant


def validate_workflow_models(workflow):
    print(
        "DEBUG 3: Consultando object_info de ComfyUI...",
        flush=True
    )

    try:
        object_info = get_object_info()

    except Exception as e:
        print(
            f"DEBUG 3 ERROR: No se pudo obtener object_info: {e}",
            flush=True
        )
        return False

    print(
        f"DEBUG 3 OK: ComfyUI tiene {len(object_info)} tipos de nodos",
        flush=True
    )

    missing_nodes = []

    for node_id, node in workflow.items():
        class_type = node.get("class_type")

        if class_type and class_type not in object_info:
            missing_nodes.append(class_type)

    if missing_nodes:
        print(
            "DEBUG 3 WARNING: Nodos no encontrados:",
            flush=True
        )

        for node in sorted(set(missing_nodes)):
            print(f"  - {node}", flush=True)

    return True


def queue_prompt(workflow, client_id):
    payload = {
        "prompt": workflow,
        "client_id": client_id
    }

    data = json.dumps(payload).encode("utf-8")

    url = f"http://{COMFY_HOST}/prompt"

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        }
    )

    print(
        "DEBUG 6: Enviando workflow a ComfyUI...",
        flush=True
    )

    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(
            response.read().decode("utf-8")
        )

    print(
        f"DEBUG 6 RESULT: {result}",
        flush=True
    )

    return result


def get_history(prompt_id):
    url = f"http://{COMFY_HOST}/history/{prompt_id}"

    response = requests.get(url, timeout=30)
    response.raise_for_status()

    return response.json()


def wait_for_execution(ws, prompt_id):
    print(
        f"DEBUG 8: Esperando ejecución de prompt {prompt_id}...",
        flush=True
    )

    while True:
        message = ws.recv()

        if not message:
            continue

        if isinstance(message, bytes):
            continue

        try:
            data = json.loads(message)

        except Exception:
            continue

        message_type = data.get("type")
        message_data = data.get("data", {})

        if message_type == "progress":
            value = message_data.get("value")
            maximum = message_data.get("max")

            print(
                f"DEBUG PROGRESS: {value}/{maximum}",
                flush=True
            )

        elif message_type == "executing":
            node = message_data.get("node")
            current_prompt = message_data.get("prompt_id")

            if current_prompt == prompt_id and node is None:
                print(
                    "DEBUG 8 OK: Generación terminada",
                    flush=True
                )
                return True

        elif message_type == "execution_error":
            print(
                f"DEBUG 8 ERROR: {message_data}",
                flush=True
            )
            return False


def get_outputs_from_history(history, prompt_id):
    outputs = []

    prompt_history = history.get(prompt_id, {})

    node_outputs = prompt_history.get("outputs", {})

    print(
        f"DEBUG 9: Analizando outputs de {len(node_outputs)} nodos",
        flush=True
    )

    for node_id, node_output in node_outputs.items():

        if "images" in node_output:
            for image in node_output["images"]:
                outputs.append({
                    "type": "image",
                    "filename": image.get("filename"),
                    "subfolder": image.get("subfolder"),
                    "type_folder": image.get("type")
                })

        if "gifs" in node_output:
            for video in node_output["gifs"]:
                outputs.append({
                    "type": "video",
                    "filename": video.get("filename"),
                    "subfolder": video.get("subfolder"),
                    "type_folder": video.get("type")
                })

        if "videos" in node_output:
            for video in node_output["videos"]:
                outputs.append({
                    "type": "video",
                    "filename": video.get("filename"),
                    "subfolder": video.get("subfolder"),
                    "type_folder": video.get("type")
                })

    return outputs


def handler(job):

    print("", flush=True)
    print("==============================================", flush=True)
    print("LTX RUNPOD HANDLER - NUEVO JOB", flush=True)
    print("==============================================", flush=True)
    print("DEBUG TEST: ENTRE A handler(job)", flush=True)

    try:

        job_input = job["input"]
        job_id = job["id"]

        print(
            f"DEBUG: Job ID = {job_id}",
            flush=True
        )

        # ==========================================
        # MODO DIAGNOSTICO: LISTAR NODOS
        # ==========================================

        if job_input.get("action") == "list_nodes":

            print(
                "DEBUG DIAGNOSTIC: Consultando nodos de ComfyUI...",
                flush=True
            )

            if not check_server():

                return {
                    "error": "ComfyUI no está disponible"
                }

            nodes = get_relevant_nodes()

            print(
                f"DEBUG DIAGNOSTIC: "
                f"{len(nodes)} nodos relevantes encontrados",
                flush=True
            )

            return {
                "job_id": job_id,
                "action": "list_nodes",
                "node_count": len(nodes),
                "nodes": sorted(nodes.keys())
            }

        # ==========================================
        # FLUJO NORMAL
        # ==========================================

        print(
            "DEBUG 0: Esperando modelos LTX...",
            flush=True
        )

        start_wait = time.time()

        while not os.path.exists(READY_FILE):

            if time.time() - start_wait > MAX_MODEL_WAIT:

                return {
                    "error": "Timeout esperando modelos LTX"
                }

            time.sleep(1)

        print(
            "DEBUG 0 OK: LTX models are ready.",
            flush=True
        )

        valid, error = validate_input(job_input)

        if not valid:

            print(
                f"DEBUG 1 ERROR: {error}",
                flush=True
            )

            return {
                "error": error
            }

        workflow = job_input["workflow"]

        print(
            f"DEBUG 1 OK: "
            f"Workflow recibido con {len(workflow)} nodos",
            flush=True
        )

        print(
            "DEBUG 2: Comprobando ComfyUI...",
            flush=True
        )

        if not check_server():

            return {
                "error": "ComfyUI no está disponible"
            }

        print(
            "DEBUG 2 OK: ComfyUI disponible",
            flush=True
        )

        if not validate_workflow_models(workflow):

            return {
                "error": "Falló la validación del workflow"
            }

        print(
            "DEBUG 5 OK: Workflow validado",
            flush=True
        )

        client_id = str(uuid.uuid4())

        print(
            f"DEBUG 5: Client ID = {client_id}",
            flush=True
        )

        ws_url = (
            f"ws://{COMFY_HOST}/ws"
            f"?clientId={client_id}"
        )

        print(
            "DEBUG 5: Conectando WebSocket...",
            flush=True
        )

        ws = websocket.create_connection(
            ws_url,
            timeout=30
        )

        print(
            "DEBUG 5 OK: WebSocket conectado.",
            flush=True
        )

        queue_result = queue_prompt(
            workflow,
            client_id
        )

        prompt_id = queue_result.get("prompt_id")

        if not prompt_id:

            print(
                "DEBUG 6 ERROR: "
                "ComfyUI no devolvió prompt_id",
                flush=True
            )

            return {
                "error": "ComfyUI no devolvió prompt_id",
                "queue_result": queue_result
            }

        print(
            f"DEBUG 7 OK: "
            f"Workflow enviado. Prompt ID = {prompt_id}",
            flush=True
        )

        execution_ok = wait_for_execution(
            ws,
            prompt_id
        )

        ws.close()

        if not execution_ok:

            return {
                "error": "ComfyUI execution error",
                "prompt_id": prompt_id
            }

        print(
            "DEBUG 9: Obteniendo history...",
            flush=True
        )

        history = get_history(prompt_id)

        print(
            "DEBUG 9 OK: History recibido",
            flush=True
        )

        outputs = get_outputs_from_history(
            history,
            prompt_id
        )

        print(
            f"DEBUG 10 OK: "
            f"Outputs encontrados: {len(outputs)}",
            flush=True
        )

        return {
            "job_id": job_id,
            "prompt_id": prompt_id,
            "outputs": outputs,
            "history": history
        }

    except Exception as e:

        print("", flush=True)
        print("==============================================", flush=True)
        print("HANDLER ERROR", flush=True)
        print("==============================================", flush=True)

        print(
            str(e),
            flush=True
        )

        traceback.print_exc()

        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


runpod.serverless.start({
    "handler": handler
})
