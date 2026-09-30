import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request

import runpod


COMFY_HOST = "127.0.0.1:8188"
COMFY_URL = f"http://{COMFY_HOST}"

comfy_process = None
comfy_log_file = None


def http_get_json(url, timeout=5):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_comfyui():
    try:
        http_get_json(f"{COMFY_URL}/system_stats", timeout=3)
        return True
    except Exception:
        return False


def show_comfy_log_tail(lines=40):
    log_path = "/tmp/comfyui.log"

    print("=== ULTIMAS LINEAS DE COMFYUI ===", flush=True)

    if not os.path.exists(log_path):
        print("No existe /tmp/comfyui.log", flush=True)
        return

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.readlines()

        for line in content[-lines:]:
            print(line.rstrip(), flush=True)

    except Exception as e:
        print(f"No se pudo leer el log de ComfyUI: {e}", flush=True)


def start_comfyui():
    global comfy_process
    global comfy_log_file

    print("==============================================", flush=True)
    print("INICIANDO COMFYUI", flush=True)
    print("==============================================", flush=True)

    if check_comfyui():
        print("=== COMFYUI YA ESTABA ACTIVO ===", flush=True)
        return

    log_path = "/tmp/comfyui.log"

    try:
        comfy_log_file = open(
            log_path,
            "w",
            encoding="utf-8"
        )

        command = [
            sys.executable,
            "-u",
            "/comfyui/main.py",
            "--listen",
            "127.0.0.1",
            "--port",
            "8188",
            "--disable-auto-launch",
            "--disable-metadata",
        ]

        print(
            f"COMANDO COMFYUI: {' '.join(command)}",
            flush=True
        )

        comfy_process = subprocess.Popen(
            command,
            cwd="/comfyui",
            stdout=comfy_log_file,
            stderr=subprocess.STDOUT,
        )

        print(
            f"=== PROCESO COMFYUI INICIADO PID={comfy_process.pid} ===",
            flush=True
        )

    except Exception as e:
        print("=== ERROR INICIANDO COMFYUI ===", flush=True)
        print(str(e), flush=True)
        traceback.print_exc()
        raise

    print("=== ESPERANDO COMFYUI ===", flush=True)

    max_wait = 180
    started_at = time.time()

    while time.time() - started_at < max_wait:

        if check_comfyui():
            print("=== COMFYUI LISTO EN 127.0.0.1:8188 ===", flush=True)
            return

        if comfy_process is not None:
            exit_code = comfy_process.poll()

            if exit_code is not None:
                print(
                    f"=== COMFYUI SE CERRO. EXIT CODE: {exit_code} ===",
                    flush=True
                )
                show_comfy_log_tail()
                raise RuntimeError(
                    f"ComfyUI terminó durante el arranque. Exit code: {exit_code}"
                )

        time.sleep(2)

    print("=== TIMEOUT ESPERANDO COMFYUI ===", flush=True)
    show_comfy_log_tail()

    raise RuntimeError(
        "ComfyUI no estuvo disponible después de 180 segundos."
    )


def get_object_info():
    print("=== CONSULTANDO /object_info ===", flush=True)

    data = http_get_json(
        f"{COMFY_URL}/object_info",
        timeout=30
    )

    print(
        f"=== COMFYUI DEVOLVIO {len(data)} NODOS ===",
        flush=True
    )

    return data


def get_relevant_nodes(nodes):
    keywords = [
        "LTX",
        "GGUF",
        "Gemma",
        "VAE",
        "SaveVideo",
        "VHS",
        "Sampler",
        "Conditioning",
        "Latent",
    ]

    relevant = []

    for node_name in nodes.keys():

        name_upper = node_name.upper()

        for keyword in keywords:

            if keyword.upper() in name_upper:
                relevant.append(node_name)
                break

    return sorted(set(relevant))


def handler(job):
    print("=== CALLBACK REAL OK ===", flush=True)

    try:
        print(f"JOB COMPLETO: {job}", flush=True)

        job_input = job.get("input", {})
        job_id = job.get("id")

        action = job_input.get("action")

        # ------------------------------------------
        # TEST SIMPLE
        # ------------------------------------------

        if action == "test":

            result = {
                "ok": True,
                "action": "test",
                "message": "RunPod + handler + ComfyUI están funcionando.",
                "job_id": job_id,
                "comfyui": check_comfyui(),
            }

            print(f"RESPUESTA: {result}", flush=True)

            return result

        # ------------------------------------------
        # LISTAR NODOS
        # ------------------------------------------

        if action == "list_nodes":

            if not check_comfyui():
                print(
                    "=== COMFYUI NO RESPONDE. INTENTANDO REINICIAR ===",
                    flush=True
                )

                start_comfyui()

            nodes = get_object_info()
            relevant_nodes = get_relevant_nodes(nodes)

            result = {
                "ok": True,
                "action": "list_nodes",
                "job_id": job_id,
                "total_nodes": len(nodes),
                "relevant_node_count": len(relevant_nodes),
                "relevant_nodes": relevant_nodes,
            }

            print(
                f"=== NODOS RELEVANTES: {len(relevant_nodes)} ===",
                flush=True
            )

            for node in relevant_nodes:
                print(f"  - {node}", flush=True)

            return result

        # ------------------------------------------
        # ACCION DESCONOCIDA
        # ------------------------------------------

        result = {
            "ok": False,
            "error": f"Acción desconocida: {action}",
            "available_actions": [
                "test",
                "list_nodes",
            ],
        }

        print(f"RESPUESTA: {result}", flush=True)

        return result

    except Exception as e:

        print("=== ERROR EN HANDLER ===", flush=True)
        print(str(e), flush=True)
        traceback.print_exc()

        return {
            "ok": False,
            "error": str(e),
            "job_id": job.get("id"),
        }


# ==================================================
# ARRANQUE
# ==================================================

print("==============================================", flush=True)
print("LTX HANDLER PROPIO", flush=True)
print("==============================================", flush=True)

try:

    # Primero arrancamos ComfyUI.
    start_comfyui()

    print("=== COMFYUI CONFIRMADO ===", flush=True)
    print("=== INICIANDO RUNPOD SERVERLESS ===", flush=True)

    runpod.serverless.start({
        "handler": handler
    })

except Exception as e:

    print("==============================================", flush=True)
    print("ERROR FATAL DURANTE EL ARRANQUE", flush=True)
    print("==============================================", flush=True)

    print(str(e), flush=True)
    traceback.print_exc()

    raise
