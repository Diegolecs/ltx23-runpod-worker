import json
import os
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid

import runpod


COMFY_HOST = "127.0.0.1:8188"
COMFY_URL = f"http://{COMFY_HOST}"

comfy_process = None
comfy_log_file = None


# =========================================================
# HTTP
# =========================================================

def http_get_json(url, timeout=10):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def http_post_json(url, payload, timeout=30):
    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout
        ) as response:

            body = response.read().decode("utf-8")

            if not body:
                return {}

            return json.loads(body)

    except urllib.error.HTTPError as e:

        print(
            f"=== COMFYUI HTTP ERROR {e.code} ===",
            flush=True
        )

        try:
            error_body = e.read().decode(
                "utf-8",
                errors="replace"
            )

            print(
                "=== RESPUESTA REAL DE COMFYUI ===",
                flush=True
            )

            print(
                error_body,
                flush=True
            )

        except Exception as read_error:

            print(
                f"No se pudo leer el cuerpo del error: {read_error}",
                flush=True
            )

        raise

    except Exception as e:

        print(
            "=== ERROR HTTP ===",
            flush=True
        )

        print(
            str(e),
            flush=True
        )

        raise


# =========================================================
# COMFYUI
# =========================================================

def check_comfyui():
    try:
        http_get_json(
            f"{COMFY_URL}/system_stats",
            timeout=3
        )
        return True

    except Exception:
        return False


def get_object_info():

    print(
        "=== CONSULTANDO /object_info ===",
        flush=True
    )

    data = http_get_json(
        f"{COMFY_URL}/object_info",
        timeout=30
    )

    print(
        f"=== COMFYUI DEVOLVIO {len(data)} NODOS ===",
        flush=True
    )

    return data


# =========================================================
# LOG DE COMFYUI
# =========================================================

def show_comfy_log_tail(lines=100):

    log_path = "/tmp/comfyui.log"

    print(
        "=== ULTIMAS LINEAS DE COMFYUI ===",
        flush=True
    )

    if not os.path.exists(log_path):

        print(
            "No existe /tmp/comfyui.log",
            flush=True
        )

        return

    try:

        with open(
            log_path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as f:

            content = f.readlines()

        for line in content[-lines:]:

            print(
                line.rstrip(),
                flush=True
            )

    except Exception as e:

        print(
            f"Error leyendo log ComfyUI: {e}",
            flush=True
        )


# =========================================================
# ARRANQUE COMFYUI
# =========================================================

def start_comfyui():

    global comfy_process
    global comfy_log_file

    print(
        "==============================================",
        flush=True
    )

    print(
        "INICIANDO COMFYUI",
        flush=True
    )

    print(
        "==============================================",
        flush=True
    )

    if check_comfyui():

        print(
            "=== COMFYUI YA ESTABA ACTIVO ===",
            flush=True
        )

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

        print(
            "=== ERROR INICIANDO COMFYUI ===",
            flush=True
        )

        print(
            str(e),
            flush=True
        )

        traceback.print_exc()

        raise

    print(
        "=== ESPERANDO COMFYUI ===",
        flush=True
    )

    started_at = time.time()
    timeout_seconds = 180

    while time.time() - started_at < timeout_seconds:

        if check_comfyui():

            print(
                "=== COMFYUI LISTO EN 127.0.0.1:8188 ===",
                flush=True
            )

            return

        if comfy_process is not None:

            exit_code = comfy_process.poll()

            if exit_code is not None:

                print(
                    f"=== COMFYUI SE CERRO. EXIT CODE={exit_code} ===",
                    flush=True
                )

                show_comfy_log_tail()

                raise RuntimeError(
                    f"ComfyUI terminó con exit code {exit_code}"
                )

        time.sleep(2)

    print(
        "=== TIMEOUT ESPERANDO COMFYUI ===",
        flush=True
    )

    show_comfy_log_tail()

    raise RuntimeError(
        "ComfyUI no estuvo disponible después de 180 segundos"
    )


def ensure_comfyui():

    if check_comfyui():
        return

    start_comfyui()


# =========================================================
# QUEUE
# =========================================================

def queue_prompt(workflow):

    client_id = str(uuid.uuid4())

    payload = {
        "prompt": workflow,
        "client_id": client_id
    }

    print(
        "=== ENVIANDO WORKFLOW A COMFYUI ===",
        flush=True
    )

    response = http_post_json(
        f"{COMFY_URL}/prompt",
        payload,
        timeout=30
    )

    print(
        f"=== RESPUESTA /prompt: {response} ===",
        flush=True
    )

    if "error" in response:

        raise RuntimeError(
            "ComfyUI rechazó el workflow: "
            + json.dumps(
                response,
                ensure_ascii=False
            )
        )

    prompt_id = response.get(
        "prompt_id"
    )

    if not prompt_id:

        raise RuntimeError(
            f"ComfyUI no devolvió prompt_id: {response}"
        )

    return prompt_id


def get_history(prompt_id):

    return http_get_json(
        f"{COMFY_URL}/history/{prompt_id}",
        timeout=30
    )


def wait_for_execution(
    prompt_id,
    timeout_seconds=900
):

    print(
        f"=== ESPERANDO EJECUCION {prompt_id} ===",
        flush=True
    )

    started_at = time.time()

    while time.time() - started_at < timeout_seconds:

        try:

            history = get_history(
                prompt_id
            )

            if prompt_id in history:

                item = history[prompt_id]

                status = item.get(
                    "status",
                    {}
                )

                status_str = status.get(
                    "status_str"
                )

                completed = status.get(
                    "completed",
                    False
                )

                messages = status.get(
                    "messages",
                    []
                )

                print(
                    f"=== STATUS: {status_str} "
                    f"COMPLETED={completed} ===",
                    flush=True
                )

                if status_str == "success" and completed:

                    print(
                        "=== EJECUCION COMPLETADA ===",
                        flush=True
                    )

                    return item

                if status_str == "error":

                    print(
                        "=== COMFYUI DEVOLVIO ERROR ===",
                        flush=True
                    )

                    print(
                        json.dumps(
                            messages,
                            ensure_ascii=False,
                            indent=2
                        ),
                        flush=True
                    )

                    raise RuntimeError(
                        "ComfyUI terminó la ejecución con ERROR"
                    )

        except urllib.error.HTTPError:
            pass

        time.sleep(2)

    raise TimeoutError(
        "ComfyUI no terminó el workflow dentro del tiempo límite"
    )


# =========================================================
# OUTPUTS
# =========================================================

def extract_outputs(history_item):

    outputs = history_item.get(
        "outputs",
        {}
    )

    result = {
        "videos": [],
        "images": [],
        "gifs": [],
        "other": {}
    }

    for node_id, node_output in outputs.items():

        if not isinstance(
            node_output,
            dict
        ):
            continue

        for key in [
            "videos",
            "gifs",
            "images"
        ]:

            items = node_output.get(
                key,
                []
            )

            if isinstance(
                items,
                list
            ):

                result[key].extend(
                    items
                )

        known = {
            "videos",
            "gifs",
            "images"
        }

        other = {
            k: v
            for k, v in node_output.items()
            if k not in known
        }

        if other:

            result["other"][node_id] = other

    return result


# =========================================================
# WORKFLOW LTX-2.3
# =========================================================

def build_ltx_workflow(
    prompt_text,
    seed=42,
    width=768,
    height=512,
    length=49,
    fps=25,
    steps=8,
    cfg=1.0
):

    negative_prompt = (
        "blurry, low quality, distorted, "
        "deformed, watermark, subtitles, text"
    )

    workflow = {

        # -------------------------------------------------
        # MODEL
        # -------------------------------------------------

        "1": {
            "class_type": "UnetLoaderGGUF",
            "inputs": {
                "unet_name":
                    "LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf"
            }
        },

        # -------------------------------------------------
        # VIDEO VAE
        # -------------------------------------------------

        "2": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name":
                    "LTX23_video_vae_bf16.safetensors"
            }
        },

        # -------------------------------------------------
        # AUDIO VAE
        # -------------------------------------------------

        "3": {
            "class_type": "VAELoader",
            "inputs": {
                "vae_name":
                    "LTX23_audio_vae_bf16.safetensors"
            }
        },

        # -------------------------------------------------
        # GEMMA + TEXT PROJECTION
        # -------------------------------------------------

        "4": {
            "class_type": "DualCLIPLoader",
            "inputs": {
                "clip_name1":
                    "gemma_3_12B_it_fp8_scaled.safetensors",

                "clip_name2":
                    "ltx-2.3_text_projection_bf16.safetensors",

                "type":
                    "ltxv",

                "device":
                    "default"
            }
        },

        # -------------------------------------------------
        # POSITIVE PROMPT
        # -------------------------------------------------

        "5": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text":
                    prompt_text,

                "clip": [
                    "4",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # NEGATIVE PROMPT
        # -------------------------------------------------

        "6": {
            "class_type": "CLIPTextEncode",
            "inputs": {
                "text":
                    negative_prompt,

                "clip": [
                    "4",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # LTX CONDITIONING
        # -------------------------------------------------

        "7": {
            "class_type": "LTXVConditioning",
            "inputs": {
                "positive": [
                    "5",
                    0
                ],

                "negative": [
                    "6",
                    0
                ],

                "frame_rate":
                    fps
            }
        },

        # -------------------------------------------------
        # VIDEO LATENT
        # -------------------------------------------------

        "8": {
            "class_type": "EmptyLTXVLatentVideo",
            "inputs": {
                "width":
                    width,

                "height":
                    height,

                "length":
                    length,

                "batch_size":
                    1
            }
        },

        # -------------------------------------------------
        # AUDIO LATENT
        # -------------------------------------------------

        "9": {
            "class_type": "LTXVEmptyLatentAudio",
            "inputs": {
                "audio_vae": [
                    "3",
                    0
                ],

                "batch_size":
                    1,

                "frame_rate":
                    fps,

                "frames_number":
                    length
            }
        },

        # -------------------------------------------------
        # CONCAT VIDEO + AUDIO
        # -------------------------------------------------

        "10": {
            "class_type": "LTXVConcatAVLatent",
            "inputs": {
                "video_latent": [
                    "8",
                    0
                ],

                "audio_latent": [
                    "9",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # SCHEDULER
        # -------------------------------------------------

        "11": {
            "class_type": "LTXVScheduler",
            "inputs": {
                "steps":
                    steps,

                "max_shift":
                    2.05,

                "base_shift":
                    0.95,

                "stretch":
                    True,

                "terminal":
                    0.1,

                "latent": [
                    "10",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # SAMPLER
        # -------------------------------------------------

        "12": {
            "class_type": "KSamplerSelect",
            "inputs": {
                "sampler_name":
                    "euler"
            }
        },

        # -------------------------------------------------
        # NOISE
        # -------------------------------------------------

        "13": {
            "class_type": "RandomNoise",
            "inputs": {
                "noise_seed":
                    seed
            }
        },

        # -------------------------------------------------
        # GUIDER
        # -------------------------------------------------

        "14": {
            "class_type": "CFGGuider",
            "inputs": {
                "model": [
                    "1",
                    0
                ],

                "positive": [
                    "7",
                    0
                ],

                "negative": [
                    "7",
                    1
                ],

                "cfg":
                    cfg
            }
        },

        # -------------------------------------------------
        # SAMPLER
        # -------------------------------------------------

        "15": {
            "class_type": "SamplerCustomAdvanced",
            "inputs": {
                "noise": [
                    "13",
                    0
                ],

                "guider": [
                    "14",
                    0
                ],

                "sampler": [
                    "12",
                    0
                ],

                "sigmas": [
                    "11",
                    0
                ],

                "latent_image": [
                    "10",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # SEPARATE A/V
        # -------------------------------------------------

        "16": {
            "class_type": "LTXVSeparateAVLatent",
            "inputs": {
                "av_latent": [
                    "15",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # VIDEO DECODE
        # -------------------------------------------------

        "17": {
            "class_type": "VAEDecode",
            "inputs": {
                "samples": [
                    "16",
                    0
                ],

                "vae": [
                    "2",
                    0
                ]
            }
        },

        # -------------------------------------------------
        # CREATE VIDEO
        # -------------------------------------------------

        "18": {
            "class_type": "CreateVideo",
            "inputs": {
                "images": [
                    "17",
                    0
                ],

                "fps":
                    fps
            }
        },

        # -------------------------------------------------
        # SAVE VIDEO
        # -------------------------------------------------

        "19": {
            "class_type": "SaveVideo",
            "inputs": {
                "video": [
                    "18",
                    0
                ],

                "filename_prefix":
                    "video/LTX23_test",

                "format":
                    "mp4",

                "codec":
                    "auto"
            }
        }
    }

    return workflow


# =========================================================
# HANDLER
# =========================================================

def handler(job):

    print(
        "DEBUG TEST: ENTRE A handler(job)",
        flush=True
    )

    print(
        "=== CALLBACK REAL OK ===",
        flush=True
    )

    try:

        print(
            f"JOB COMPLETO: {job}",
            flush=True
        )

        job_input = job.get(
            "input",
            {}
        )

        job_id = job.get(
            "id"
        )

        action = job_input.get(
            "action"
        )

        # =================================================
        # TEST
        # =================================================

        if action == "test":

            result = {
                "ok": True,
                "action": "test",
                "job_id": job_id,
                "comfyui": check_comfyui()
            }

            print(
                f"RESPUESTA: {result}",
                flush=True
            )

            return result

        # =================================================
        # LIST NODES
        # =================================================

        if action == "list_nodes":

            ensure_comfyui()

            nodes = get_object_info()

            target_nodes = [
                "LTXVGemmaCLIPModelLoader",
                "LTXVConditioning",
                "DecodeAndSaveVideo",
                "SamplerCustomAdvanced",
                "LTXVScheduler",
                "UnetLoaderGGUF",
                "VAELoader",
                "EmptyLTXVLatentVideo",
                "LTXVEmptyLatentAudio",
                "LTXVConcatAVLatent",
                "LTXVSeparateAVLatent",
                "VAEDecode"
            ]

            selected_info = {
                name: nodes.get(name)
                for name in target_nodes
                if name in nodes
            }

            relevant = []

            keywords = [
                "LTX",
                "GGUF",
                "Gemma",
                "VAE",
                "SaveVideo",
                "Sampler",
                "Conditioning"
            ]

            for name in nodes.keys():

                upper = name.upper()

                if any(
                    keyword.upper() in upper
                    for keyword in keywords
                ):

                    relevant.append(
                        name
                    )

            result = {
                "ok": True,
                "action": "list_nodes",
                "job_id": job_id,
                "total_nodes": len(nodes),
                "relevant_nodes": sorted(
                    relevant
                ),
                "target_nodes": sorted(
                    selected_info.keys()
                ),
                "object_info": selected_info
            }

            print(
                "=== OBJECT_INFO OBJETIVO ===",
                flush=True
            )

            print(
                json.dumps(
                    selected_info,
                    ensure_ascii=False,
                    indent=2
                ),
                flush=True
            )

            return result

        # =================================================
        # GENERATE
        # =================================================

        if action == "generate":

            ensure_comfyui()

            prompt_text = job_input.get(
                "prompt",
                "A cinematic shot of a realistic orange sports car driving through a futuristic city at night, wet streets, reflections, dramatic lighting, smooth camera movement"
            )

            seed = int(
                job_input.get(
                    "seed",
                    42
                )
            )

            width = int(
                job_input.get(
                    "width",
                    768
                )
            )

            height = int(
                job_input.get(
                    "height",
                    512
                )
            )

            length = int(
                job_input.get(
                    "length",
                    49
                )
            )

            fps = float(
                job_input.get(
                    "fps",
                    25
                )
            )

            steps = int(
                job_input.get(
                    "steps",
                    8
                )
            )

            cfg = float(
                job_input.get(
                    "cfg",
                    1.0
                )
            )

            print(
                "==============================================",
                flush=True
            )

            print(
                "GENERATE LTX-2.3",
                flush=True
            )

            print(
                "==============================================",
                flush=True
            )

            print(
                f"prompt={prompt_text}",
                flush=True
            )

            print(
                f"size={width}x{height}",
                flush=True
            )

            print(
                f"frames={length}",
                flush=True
            )

            print(
                f"fps={fps}",
                flush=True
            )

            print(
                f"steps={steps}",
                flush=True
            )

            print(
                f"cfg={cfg}",
                flush=True
            )

            print(
                f"seed={seed}",
                flush=True
            )

            workflow = build_ltx_workflow(
                prompt_text=prompt_text,
                seed=seed,
                width=width,
                height=height,
                length=length,
                fps=fps,
                steps=steps,
                cfg=cfg
            )

            print(
                "=== WORKFLOW CONSTRUIDO ===",
                flush=True
            )

            print(
                json.dumps(
                    workflow,
                    ensure_ascii=False,
                    indent=2
                ),
                flush=True
            )

            prompt_id = queue_prompt(
                workflow
            )

            history_item = wait_for_execution(
                prompt_id,
                timeout_seconds=900
            )

            outputs = extract_outputs(
                history_item
            )

            result = {
                "ok": True,
                "action": "generate",
                "job_id": job_id,
                "prompt_id": prompt_id,
                "settings": {
                    "width":
                        width,

                    "height":
                        height,

                    "length":
                        length,

                    "fps":
                        fps,

                    "steps":
                        steps,

                    "cfg":
                        cfg,

                    "seed":
                        seed
                },
                "outputs":
                    outputs
            }

            print(
                "=== GENERACION TERMINADA ===",
                flush=True
            )

            print(
                json.dumps(
                    result,
                    ensure_ascii=False,
                    indent=2
                ),
                flush=True
            )

            return result

        # =================================================
        # UNKNOWN ACTION
        # =================================================

        result = {
            "ok": False,
            "error":
                f"Acción desconocida: {action}",
            "available_actions": [
                "test",
                "list_nodes",
                "generate"
            ],
            "job_id":
                job_id
        }

        print(
            f"RESPUESTA: {result}",
            flush=True
        )

        return result

    except Exception as e:

        print(
            "==============================================",
            flush=True
        )

        print(
            "ERROR EN HANDLER",
            flush=True
        )

        print(
            "==============================================",
            flush=True
        )

        print(
            str(e),
            flush=True
        )

        traceback.print_exc()

        return {
            "ok": False,
            "error": str(e),
            "job_id": job.get("id")
        }


# =========================================================
# START
# =========================================================

print(
    "==============================================",
    flush=True
)

print(
    "LTX HANDLER PROPIO",
    flush=True
)

print(
    "==============================================",
    flush=True
)

try:

    start_comfyui()

    print(
        "=== COMFYUI CONFIRMADO ===",
        flush=True
    )

    print(
        "=== INICIANDO RUNPOD SERVERLESS ===",
        flush=True
    )

    runpod.serverless.start({
        "handler": handler
    })

except Exception as e:

    print(
        "==============================================",
        flush=True
    )

    print(
        "ERROR FATAL DURANTE EL ARRANQUE",
        flush=True
    )

    print(
        "==============================================",
        flush=True
    )

    print(
        str(e),
        flush=True
    )

    traceback.print_exc()

    raise
