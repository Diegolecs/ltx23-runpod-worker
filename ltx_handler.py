import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


# ============================================================
# CONFIG
# ============================================================

COMFY_HOST = "127.0.0.1"
COMFY_PORT = 8188
COMFY_URL = f"http://{COMFY_HOST}:{COMFY_PORT}"

COMFY_PYTHON = "/opt/venv/bin/python3"
COMFY_MAIN = "/comfyui/main.py"

COMFY_OUTPUT_DIR = Path("/comfyui/output")
NETWORK_VOLUME_DIR = Path("/runpod-volume")
NETWORK_VIDEO_DIR = NETWORK_VOLUME_DIR / "video"

COMFY_PROCESS = None


# ============================================================
# GITHUB CONFIG
# ============================================================

GITHUB_OWNER = "Diegolecs"
GITHUB_REPO = "ltx23-runpod-worker"

GITHUB_API_BASE = (
    f"https://api.github.com/repos/"
    f"{GITHUB_OWNER}/{GITHUB_REPO}"
)

GITHUB_API_VERSION = "2026-03-10"

GITHUB_TRANSFER_TAG = "video-transfer"
GITHUB_TRANSFER_RELEASE_NAME = "LTX Video Transfer"


# ============================================================
# LOGGING
# ============================================================

def log(message):
    print(message, flush=True)


# ============================================================
# HTTP HELPERS - COMFYUI
# ============================================================

def http_request(
    method,
    path,
    payload=None,
    timeout=30,
):
    url = f"{COMFY_URL}{path}"

    data = None
    headers = {}

    if payload is not None:
        data = json.dumps(
            payload
        ).encode("utf-8")

        headers["Content-Type"] = (
            "application/json"
        )

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    with urllib.request.urlopen(
        request,
        timeout=timeout,
    ) as response:
        raw = response.read()

    if not raw:
        return {}

    return json.loads(
        raw.decode("utf-8")
    )


def get_json(
    path,
    timeout=30,
):
    return http_request(
        "GET",
        path,
        timeout=timeout,
    )


def post_json(
    path,
    payload,
    timeout=30,
):
    return http_request(
        "POST",
        path,
        payload=payload,
        timeout=timeout,
    )


# ============================================================
# HTTP HELPERS - GITHUB
# ============================================================

def github_request(
    method,
    path,
    payload=None,
    timeout=30,
):
    token = os.getenv(
        "GITHUB_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN no está configurado "
            "en las variables del worker."
        )

    url = (
        f"{GITHUB_API_BASE}"
        f"{path}"
    )

    headers = {
        "Accept": (
            "application/vnd.github+json"
        ),
        "Authorization": (
            f"Bearer {token}"
        ),
        "X-GitHub-Api-Version": (
            GITHUB_API_VERSION
        ),
        "User-Agent": (
            "ltx23-runpod-worker"
        ),
    }

    data = None

    if payload is not None:
        data = json.dumps(
            payload
        ).encode("utf-8")

        headers["Content-Type"] = (
            "application/json"
        )

    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            raw = response.read()
            status_code = response.status

    except urllib.error.HTTPError as exc:
        try:
            raw_error = exc.read()

            error_body = raw_error.decode(
                "utf-8",
                errors="replace",
            )

        except Exception:
            error_body = ""

        raise RuntimeError(
            "GitHub API respondió con "
            f"HTTP {exc.code}: {error_body}"
        ) from exc

    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"No se pudo conectar con GitHub: "
            f"{exc}"
        ) from exc

    if not raw:
        return {
            "status_code": status_code,
        }

    try:
        result = json.loads(
            raw.decode("utf-8")
        )

    except json.JSONDecodeError:
        result = {
            "raw": raw.decode(
                "utf-8",
                errors="replace",
            )
        }

    if isinstance(
        result,
        dict,
    ):
        result["_status_code"] = (
            status_code
        )

    return result


# ============================================================
# GITHUB TEST
# ============================================================

def github_test():
    log(
        "=============================================="
    )

    log(
        "GITHUB TEST"
    )

    log(
        "=============================================="
    )

    token = os.getenv(
        "GITHUB_TOKEN"
    )

    if not token:
        return {
            "ok": False,
            "action": "github_test",
            "message": (
                "GITHUB_TOKEN no está configurado."
            ),
        }

    log(
        "=== GITHUB_TOKEN ENCONTRADO ==="
    )

    log(
        "=== CONSULTANDO REPOSITORIO GITHUB ==="
    )

    repo_data = github_request(
        "GET",
        "",
        timeout=30,
    )

    return {
        "ok": True,
        "action": "github_test",
        "github": {
            "authenticated": True,
            "owner": GITHUB_OWNER,
            "repo": GITHUB_REPO,
            "full_name": repo_data.get(
                "full_name"
            ),
            "private": repo_data.get(
                "private"
            ),
            "default_branch": repo_data.get(
                "default_branch"
            ),
            "html_url": repo_data.get(
                "html_url"
            ),
        },
    }


# ============================================================
# GITHUB RELEASE
# ============================================================

def github_get_or_create_transfer_release():

    log(
        "=== BUSCANDO RELEASE DE TRANSFERENCIA ==="
    )

    releases = github_request(
        "GET",
        "/releases?per_page=100",
        timeout=30,
    )

    if not isinstance(
        releases,
        list,
    ):
        raise RuntimeError(
            "GitHub no devolvió una lista "
            "de releases."
        )

    for release in releases:

        if (
            release.get("tag_name")
            == GITHUB_TRANSFER_TAG
        ):
            log(
                f"=== RELEASE ENCONTRADO "
                f"ID={release.get('id')} ==="
            )

            return release

    log(
        "=== RELEASE NO EXISTE ==="
    )

    log(
        "=== CREANDO RELEASE DE TRANSFERENCIA ==="
    )

    release = github_request(
        "POST",
        "/releases",
        payload={
            "tag_name":
                GITHUB_TRANSFER_TAG,

            "name":
                GITHUB_TRANSFER_RELEASE_NAME,

            "body": (
                "Release temporal utilizado "
                "para transferencia de videos LTX."
            ),

            "draft":
                False,

            "prerelease":
                True,

            "make_latest":
                False,

            "generate_release_notes":
                False,
        },

        timeout=60,
    )

    log(
        f"=== RELEASE CREADO "
        f"ID={release.get('id')} ==="
    )

    return release


# ============================================================
# GITHUB UPLOAD
# ============================================================

def github_upload_file(
    file_path,
    asset_name=None,
):
    file_path = Path(
        file_path
    )

    if not file_path.is_file():
        raise FileNotFoundError(
            f"No existe el archivo: "
            f"{file_path}"
        )

    if asset_name is None:
        asset_name = (
            f"ltx_test_"
            f"{int(time.time())}.mp4"
        )

    release = (
        github_get_or_create_transfer_release()
    )

    upload_url = release.get(
        "upload_url"
    )

    if not upload_url:
        raise RuntimeError(
            "GitHub Release no devolvió "
            "upload_url."
        )

    upload_url = upload_url.split(
        "{",
        1,
    )[0]

    query = urllib.parse.urlencode({
        "name":
            asset_name,
    })

    final_url = (
        f"{upload_url}?{query}"
    )

    log(
        "=============================================="
    )

    log(
        "SUBIENDO VIDEO A GITHUB"
    )

    log(
        "=============================================="
    )

    log(
        f"ARCHIVO: {file_path}"
    )

    log(
        f"NOMBRE ASSET: {asset_name}"
    )

    file_size = file_path.stat().st_size

    log(
        f"TAMAÑO: {file_size:,} bytes"
    )

    token = os.getenv(
        "GITHUB_TOKEN"
    )

    if not token:
        raise RuntimeError(
            "GITHUB_TOKEN no está configurado."
        )

    with open(
        file_path,
        "rb",
    ) as file:
        data = file.read()

    headers = {
        "Accept": (
            "application/vnd.github+json"
        ),
        "Authorization": (
            f"Bearer {token}"
        ),
        "X-GitHub-Api-Version": (
            GITHUB_API_VERSION
        ),
        "User-Agent": (
            "ltx23-runpod-worker"
        ),
        "Content-Type": (
            "video/mp4"
        ),
    }

    request = urllib.request.Request(
        final_url,
        data=data,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=300,
        ) as response:
            raw = response.read()
            status_code = response.status

    except urllib.error.HTTPError as exc:

        try:
            error_body = (
                exc.read()
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

        except Exception:
            error_body = ""

        raise RuntimeError(
            "GitHub upload respondió con "
            f"HTTP {exc.code}: {error_body}"
        ) from exc

    except urllib.error.URLError as exc:

        raise RuntimeError(
            "No se pudo conectar con GitHub "
            "durante el upload: "
            f"{exc}"
        ) from exc

    try:
        result = json.loads(
            raw.decode("utf-8")
        )

    except json.JSONDecodeError as exc:

        raise RuntimeError(
            "GitHub devolvió una respuesta "
            "que no es JSON."
        ) from exc

    if status_code != 201:
        raise RuntimeError(
            "GitHub esperaba HTTP 201 "
            f"pero devolvió {status_code}."
        )

    asset_id = result.get(
        "id"
    )

    browser_download_url = (
        result.get(
            "browser_download_url"
        )
    )

    if not asset_id:
        raise RuntimeError(
            "GitHub upload terminó pero "
            "no devolvió asset_id."
        )

    if not browser_download_url:
        raise RuntimeError(
            "GitHub upload terminó pero "
            "no devolvió "
            "browser_download_url."
        )

    log(
        "=== UPLOAD COMPLETADO ==="
    )

    log(
        f"ASSET ID: {asset_id}"
    )

    log(
        "DOWNLOAD URL: "
        f"{browser_download_url}"
    )

    return {
        "asset_id":
            asset_id,

        "filename":
            result.get(
                "name",
                asset_name,
            ),

        "size_bytes":
            result.get(
                "size",
                file_size,
            ),

        "browser_download_url":
            browser_download_url,

        "release_id":
            release.get(
                "id"
            ),

        "release_tag":
            release.get(
                "tag_name"
            ),
    }


# ============================================================
# GITHUB DELETE ASSET
# ============================================================

def github_delete_asset(
    asset_id,
):
    asset_id = int(
        asset_id
    )

    log(
        "=============================================="
    )

    log(
        "ELIMINANDO ASSET GITHUB"
    )

    log(
        "=============================================="
    )

    github_request(
        "DELETE",
        f"/releases/assets/{asset_id}",
        timeout=30,
    )

    log(
        f"=== ASSET {asset_id} ELIMINADO ==="
    )

    return {
        "ok":
            True,

        "action":
            "github_delete_asset",

        "asset_id":
            asset_id,

        "deleted":
            True,
    }


# ============================================================
# COMFYUI
# ============================================================

def start_comfyui():
    global COMFY_PROCESS

    log(
        "=============================================="
    )

    log(
        "INICIANDO COMFYUI"
    )

    log(
        "=============================================="
    )

    command = [
        COMFY_PYTHON,
        "-u",
        COMFY_MAIN,
        "--listen",
        COMFY_HOST,
        "--port",
        str(COMFY_PORT),
        "--disable-auto-launch",
        "--disable-metadata",
    ]

    log(
        "COMANDO COMFYUI: "
        + " ".join(command)
    )

    COMFY_PROCESS = subprocess.Popen(
        command,
        stdout=None,
        stderr=None,
        cwd="/comfyui",
    )

    log(
        f"=== PROCESO COMFYUI INICIADO "
        f"PID={COMFY_PROCESS.pid} ==="
    )

    log(
        "=== ESPERANDO COMFYUI ==="
    )

    started = time.time()

    while True:

        if (
            COMFY_PROCESS.poll()
            is not None
        ):
            raise RuntimeError(
                f"ComfyUI terminó "
                f"prematuramente con código "
                f"{COMFY_PROCESS.returncode}"
            )

        try:
            get_json(
                "/system_stats",
                timeout=3,
            )

            break

        except Exception:

            if (
                time.time() - started
                > 180
            ):
                raise RuntimeError(
                    "ComfyUI no respondió "
                    "dentro de 180 segundos."
                )

            time.sleep(1)

    log(
        f"=== COMFYUI LISTO EN "
        f"{COMFY_HOST}:{COMFY_PORT} ==="
    )


# ============================================================
# STORAGE
# ============================================================

SAFE_RUNPOD_ENV_KEYS = [
    "RUNPOD_VOLUME_ID",
    "RUNPOD_DC_ID",
    "RUNPOD_DATACENTER_ID",
    "RUNPOD_DATACENTER",
    "RUNPOD_REGION",
    "RUNPOD_POD_ID",
    "RUNPOD_ENDPOINT_ID",
]


def get_storage_info():

    info = {}

    for key in SAFE_RUNPOD_ENV_KEYS:

        value = os.getenv(
            key
        )

        if value is not None:
            info[key] = value

    volume_exists = (
        NETWORK_VOLUME_DIR.exists()
    )

    volume_is_dir = (
        NETWORK_VOLUME_DIR.is_dir()
    )

    writable = False
    write_test = None

    if (
        volume_exists
        and volume_is_dir
    ):

        try:

            NETWORK_VOLUME_DIR.mkdir(
                parents=True,
                exist_ok=True,
            )

            write_test = (
                NETWORK_VOLUME_DIR
                / ".ltx_write_test"
            )

            write_test.write_text(
                "LTX storage test\n",
                encoding="utf-8",
            )

            write_test.unlink(
                missing_ok=True
            )

            writable = True

        except Exception:

            try:

                if write_test is not None:
                    write_test.unlink(
                        missing_ok=True
                    )

            except Exception:
                pass

    disk = None

    if volume_exists:

        try:

            usage = shutil.disk_usage(
                NETWORK_VOLUME_DIR
            )

            disk = {
                "total_bytes":
                    usage.total,

                "used_bytes":
                    usage.used,

                "free_bytes":
                    usage.free,
            }

        except Exception:
            disk = None

    contents = []

    if (
        volume_exists
        and volume_is_dir
    ):

        try:

            entries = sorted(
                NETWORK_VOLUME_DIR.iterdir(),
                key=lambda p:
                    p.name.lower(),
            )

            for entry in entries[:100]:

                contents.append({
                    "name":
                        entry.name,

                    "type": (
                        "directory"
                        if entry.is_dir()
                        else "file"
                    ),
                })

        except Exception:
            pass

    return {
        "ok":
            True,

        "action":
            "storage_info",

        "network_volume_path":
            str(NETWORK_VOLUME_DIR),

        "network_volume_exists":
            volume_exists,

        "network_volume_is_directory":
            volume_is_dir,

        "network_volume_writable":
            writable,

        "disk":
            disk,

        "runpod_environment":
            info,

        "network_volume_contents":
            contents,
    }


# ============================================================
# NODE INSPECTION
# ============================================================

LTX_NODE_NAMES = [
    "DualCLIPLoader",
    "DualCLIPLoaderGGUF",
    "CLIPLoaderGGUF",
    "CLIPTextEncode",
    "CFGGuider",
    "UnetLoaderGGUF",
    "VAELoader",
    "EmptyLTXVLatentVideo",
    "LTXVEmptyLatentAudio",
    "LTXVConcatAVLatent",
    "LTXVConditioning",
    "LTXVScheduler",
    "KSamplerSelect",
    "RandomNoise",
    "SamplerCustomAdvanced",
    "LTXVSeparateAVLatent",
    "VAEDecode",
    "DecodeAndSaveVideo",
    "SaveVideo",
    "CreateVideo",
    "LTXVGemmaCLIPModelLoader",
]


def get_object_info():
    return get_json(
        "/object_info",
        timeout=60,
    )


def list_nodes():

    log(
        "=== CONSULTANDO /object_info ==="
    )

    object_info = get_object_info()

    log(
        f"=== COMFYUI DEVOLVIO "
        f"{len(object_info)} NODOS ==="
    )

    result = {}

    for node_name in LTX_NODE_NAMES:

        if node_name in object_info:
            result[node_name] = (
                object_info[node_name]
            )

    return {
        "ok":
            True,

        "action":
            "list_nodes",

        "total_nodes":
            len(object_info),

        "requested_nodes":
            result,
    }


def inspect_ltx():

    log(
        "=== CONSULTANDO "
        "INFORMACION LTX ==="
    )

    object_info = get_object_info()

    result = {}

    for node_name in LTX_NODE_NAMES:

        if node_name in object_info:
            result[node_name] = (
                object_info[node_name]
            )

    return {
        "ok":
            True,

        "action":
            "inspect_ltx",

        "nodes":
            result,
    }


# ============================================================
# WORKFLOW VALIDATION
# ============================================================

def validate_workflow_nodes(
    workflow,
):

    log(
        "=== CONSULTANDO /object_info ==="
    )

    object_info = get_object_info()

    log(
        f"=== COMFYUI DEVOLVIO "
        f"{len(object_info)} NODOS ==="
    )

    missing = []

    for node_id, node in workflow.items():

        class_type = node.get(
            "class_type"
        )

        if not class_type:

            missing.append({
                "node_id":
                    node_id,

                "reason":
                    "missing_class_type",
            })

            continue

        if class_type not in object_info:

            missing.append({
                "node_id":
                    node_id,

                "class_type":
                    class_type,

                "reason":
                    "node_not_found",
            })

    if missing:

        log(
            "=== NODOS FALTANTES ==="
        )

        log(
            json.dumps(
                missing,
                indent=2,
                ensure_ascii=False,
            )
        )

        raise RuntimeError(
            "El workflow contiene nodos "
            "que ComfyUI no reconoce."
        )

    log(
        "=== TODOS LOS NODOS DEL WORKFLOW "
        "EXISTEN ==="
    )


# ============================================================
# BUILD LTX WORKFLOW
# ============================================================

def build_ltx_workflow(
    prompt,
    seed,
    width,
    height,
    length,
    fps,
    steps,
    cfg,
):
    negative_prompt = (
        "blurry, low quality, distorted, "
        "deformed, watermark, subtitles, text"
    )

    workflow = {

        "1": {
            "class_type":
                "UnetLoaderGGUF",

            "inputs": {
                "unet_name":
                    "LTX-2.3-22B-distilled-1.1-Q4_K_M.gguf"
            },
        },

        "2": {
            "class_type":
                "VAELoader",

            "inputs": {
                "vae_name":
                    "LTX23_video_vae_bf16.safetensors"
            },
        },

        "3": {
            "class_type":
                "VAELoader",

            "inputs": {
                "vae_name":
                    "LTX23_audio_vae_bf16.safetensors"
            },
        },

        "4": {
            "class_type":
                "DualCLIPLoaderGGUF",

            "inputs": {

                "clip_name1":
                    "gemma-3-12b-it-Q2_K.gguf",

                "clip_name2":
                    "ltx-2.3_text_projection_bf16.safetensors",

                "type":
                    "ltxv",
            },
        },

        "5": {
            "class_type":
                "CLIPTextEncode",

            "inputs": {

                "text":
                    prompt,

                "clip":
                    ["4", 0],
            },
        },

        "6": {
            "class_type":
                "CLIPTextEncode",

            "inputs": {

                "text":
                    negative_prompt,

                "clip":
                    ["4", 0],
            },
        },

        "7": {
            "class_type":
                "LTXVConditioning",

            "inputs": {

                "positive":
                    ["5", 0],

                "negative":
                    ["6", 0],

                "frame_rate":
                    float(fps),
            },
        },

        "8": {
            "class_type":
                "EmptyLTXVLatentVideo",

            "inputs": {

                "width":
                    int(width),

                "height":
                    int(height),

                "length":
                    int(length),

                "batch_size":
                    1,
            },
        },

        "9": {
            "class_type":
                "LTXVEmptyLatentAudio",

            "inputs": {

                "audio_vae":
                    ["3", 0],

                "batch_size":
                    1,

                "frame_rate":
                    float(fps),

                "frames_number":
                    int(length),
            },
        },

        "10": {
            "class_type":
                "LTXVConcatAVLatent",

            "inputs": {

                "video_latent":
                    ["8", 0],

                "audio_latent":
                    ["9", 0],
            },
        },

        "11": {
            "class_type":
                "LTXVScheduler",

            "inputs": {

                "steps":
                    int(steps),

                "max_shift":
                    2.05,

                "base_shift":
                    0.95,

                "stretch":
                    True,

                "terminal":
                    0.1,

                "latent":
                    ["10", 0],
            },
        },

        "12": {
            "class_type":
                "KSamplerSelect",

            "inputs": {

                "sampler_name":
                    "euler",
            },
        },

        "13": {
            "class_type":
                "RandomNoise",

            "inputs": {

                "noise_seed":
                    int(seed),
            },
        },

        "14": {
            "class_type":
                "CFGGuider",

            "inputs": {

                "model":
                    ["1", 0],

                "positive":
                    ["7", 0],

                "negative":
                    ["7", 1],

                "cfg":
                    float(cfg),
            },
        },

        "15": {
            "class_type":
                "SamplerCustomAdvanced",

            "inputs": {

                "noise":
                    ["13", 0],

                "guider":
                    ["14", 0],

                "sampler":
                    ["12", 0],

                "sigmas":
                    ["11", 0],

                "latent_image":
                    ["10", 0],
            },
        },

        "16": {
            "class_type":
                "LTXVSeparateAVLatent",

            "inputs": {

                "av_latent":
                    ["15", 0],
            },
        },

        "17": {
            "class_type":
                "DecodeAndSaveVideo",

            "inputs": {

                "video_latent":
                    ["16", 0],

                "audio_latent":
                    ["16", 1],

                "fps":
                    float(fps),

                "filename_prefix":
                    "video/LTX23_test",

                "format":
                    "mp4",

                "codec":
                    "h264",

                "video_vae":
                    ["2", 0],

                "audio_vae":
                    ["3", 0],

                "tiling":
                    "disabled",
            },
        },
    }

    return workflow


# ============================================================
# WAIT FOR COMFY EXECUTION
# ============================================================

def wait_for_execution(
    prompt_id,
    timeout=1800,
):

    log(
        f"=== ESPERANDO EJECUCION "
        f"{prompt_id} ==="
    )

    started = time.time()

    while True:

        if (
            time.time() - started
            > timeout
        ):
            raise TimeoutError(
                f"ComfyUI no termino dentro "
                f"de {timeout} segundos."
            )

        try:

            history = get_json(
                f"/history/{prompt_id}",
                timeout=30,
            )

        except Exception as exc:

            log(
                f"Advertencia consultando "
                f"history: {exc}"
            )

            time.sleep(2)

            continue

        if prompt_id not in history:

            time.sleep(2)

            continue

        entry = history[
            prompt_id
        ]

        status = entry.get(
            "status",
            {},
        )

        if isinstance(
            status,
            dict,
        ):

            completed = status.get(
                "completed",
                False,
            )

            status_str = status.get(
                "status_str",
                "",
            )

            log(
                f"=== STATUS: "
                f"{status_str} "
                f"COMPLETED={completed} ==="
            )

            if (
                status.get(
                    "status_str"
                )
                == "error"
            ):

                raise RuntimeError(
                    json.dumps(
                        entry,
                        indent=2,
                        ensure_ascii=False,
                    )
                )

            if completed:

                log(
                    "=== EJECUCION "
                    "COMPLETADA ==="
                )

                return entry

        time.sleep(2)


# ============================================================
# OUTPUT DISCOVERY
# ============================================================

VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".webm",
    ".mov",
}


def outputs_from_history(
    history_entry,
):

    candidates = []

    outputs = history_entry.get(
        "outputs",
        {},
    )

    if not isinstance(
        outputs,
        dict,
    ):
        return candidates

    for (
        node_id,
        node_output,
    ) in outputs.items():

        if not isinstance(
            node_output,
            dict,
        ):
            continue

        for key in [
            "videos",
            "gifs",
            "images",
            "files",
        ]:

            items = node_output.get(
                key,
                [],
            )

            if not isinstance(
                items,
                list,
            ):
                continue

            for item in items:

                if not isinstance(
                    item,
                    dict,
                ):
                    continue

                filename = item.get(
                    "filename"
                )

                subfolder = item.get(
                    "subfolder",
                    "",
                )

                if not filename:
                    continue

                extension = (
                    Path(filename)
                    .suffix
                    .lower()
                )

                if (
                    extension
                    not in VIDEO_EXTENSIONS
                ):
                    continue

                if subfolder:

                    path = (
                        COMFY_OUTPUT_DIR
                        / subfolder
                        / filename
                    )

                else:

                    path = (
                        COMFY_OUTPUT_DIR
                        / filename
                    )

                candidates.append(
                    path
                )

    return candidates


def find_generated_video(
    history_entry,
    generation_started,
):

    history_candidates = (
        outputs_from_history(
            history_entry
        )
    )

    for path in history_candidates:

        if path.is_file():
            return path

    if not COMFY_OUTPUT_DIR.exists():
        return None

    recent = []

    for path in COMFY_OUTPUT_DIR.rglob("*"):

        if not path.is_file():
            continue

        if (
            path.suffix.lower()
            not in VIDEO_EXTENSIONS
        ):
            continue

        try:

            mtime = path.stat().st_mtime

            if (
                mtime
                >= generation_started - 5
            ):
                recent.append(
                    path
                )

        except OSError:
            continue

    if not recent:
        return None

    recent.sort(
        key=lambda p:
            p.stat().st_mtime,
        reverse=True,
    )

    return recent[0]


# ============================================================
# COPY VIDEO TO NETWORK VOLUME
# ============================================================

def copy_video_to_network_volume(
    source_path,
):

    source_path = Path(
        source_path
    )

    if not source_path.is_file():
        raise FileNotFoundError(
            f"No existe el video generado: "
            f"{source_path}"
        )

    NETWORK_VIDEO_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    target_path = (
        NETWORK_VIDEO_DIR
        / source_path.name
    )

    log(
        "=============================================="
    )

    log(
        "COPIANDO VIDEO AL NETWORK VOLUME"
    )

    log(
        "=============================================="
    )

    log(
        f"ORIGEN: {source_path}"
    )

    log(
        f"DESTINO: {target_path}"
    )

    shutil.copy2(
        source_path,
        target_path,
    )

    if not target_path.is_file():
        raise RuntimeError(
            "El video no apareció en el "
            "Network Volume después "
            "de la copia."
        )

    size_bytes = (
        target_path.stat().st_size
    )

    log(
        f"=== VIDEO COPIADO: "
        f"{size_bytes:,} bytes ==="
    )

    return {
        "filename":
            target_path.name,

        "source_path":
            str(source_path),

        "network_path":
            str(target_path),

        "size_bytes":
            size_bytes,
    }


# ============================================================
# GENERATE
# ============================================================

def generate_video(
    job_input,
):

    prompt = str(
        job_input.get(
            "prompt",
            "",
        )
    ).strip()

    if not prompt:
        raise ValueError(
            "Falta input.prompt"
        )

    seed = int(
        job_input.get(
            "seed",
            42,
        )
    )

    width = int(
        job_input.get(
            "width",
            768,
        )
    )

    height = int(
        job_input.get(
            "height",
            512,
        )
    )

    length = int(
        job_input.get(
            "length",
            49,
        )
    )

    fps = float(
        job_input.get(
            "fps",
            25,
        )
    )

    steps = int(
        job_input.get(
            "steps",
            8,
        )
    )

    cfg = float(
        job_input.get(
            "cfg",
            1.0,
        )
    )

    log(
        "=============================================="
    )

    log(
        "GENERATE LTX-2.3"
    )

    log(
        "=============================================="
    )

    log(
        f"prompt={prompt}"
    )

    log(
        f"size={width}x{height}"
    )

    log(
        f"frames={length}"
    )

    log(
        f"fps={fps}"
    )

    log(
        f"steps={steps}"
    )

    log(
        f"cfg={cfg}"
    )

    log(
        f"seed={seed}"
    )

    workflow = build_ltx_workflow(
        prompt=prompt,
        seed=seed,
        width=width,
        height=height,
        length=length,
        fps=fps,
        steps=steps,
        cfg=cfg,
    )

    log(
        "=== WORKFLOW CONSTRUIDO ==="
    )

    log(
        json.dumps(
            workflow,
            indent=2,
            ensure_ascii=False,
        )
    )

    validate_workflow_nodes(
        workflow
    )

    log(
        "=== ENVIANDO WORKFLOW "
        "A COMFYUI ==="
    )

    generation_started = (
        time.time()
    )

    response = post_json(
        "/prompt",
        {
            "prompt":
                workflow,

            "client_id":
                "ltx-runpod-handler",
        },

        timeout=120,
    )

    log(
        "=== RESPUESTA /prompt ==="
    )

    log(
        json.dumps(
            response,
            indent=2,
            ensure_ascii=False,
        )
    )

    if response.get("error"):

        raise RuntimeError(
            json.dumps(
                response,
                indent=2,
                ensure_ascii=False,
            )
        )

    prompt_id = response.get(
        "prompt_id"
    )

    if not prompt_id:

        raise RuntimeError(
            "ComfyUI no devolvio "
            "prompt_id."
        )

    history_entry = (
        wait_for_execution(
            prompt_id
        )
    )

    log(
        "=== GENERACION TERMINADA ==="
    )

    video_path = (
        find_generated_video(
            history_entry,
            generation_started,
        )
    )

    if video_path is None:

        raise RuntimeError(
            "La ejecucion de ComfyUI "
            "termino pero no encontramos "
            "ningun video en "
            "/comfyui/output."
        )

    log(
        f"=== VIDEO ENCONTRADO: "
        f"{video_path} ==="
    )

    network_output = (
        copy_video_to_network_volume(
            video_path
        )
    )

    outputs = {

        "videos": [
            {
                "filename":
                    network_output[
                        "filename"
                    ],

                "path":
                    network_output[
                        "network_path"
                    ],

                "size_bytes":
                    network_output[
                        "size_bytes"
                    ],
            }
        ],

        "images": [],

        "gifs": [],

        "other": {},
    }

    return {

        "ok":
            True,

        "action":
            "generate",

        "prompt_id":
            prompt_id,

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
                seed,
        },

        "outputs":
            outputs,

        "video":
            network_output,
    }


# ============================================================
# TEST
# ============================================================

def test_handler():

    return {

        "ok":
            True,

        "action":
            "test",

        "message":
            "LTX handler funcionando.",
    }


# ============================================================
# MAIN HANDLER
# ============================================================

def handler(job):

    job_input = job.get(
        "input",
        {},
    )

    if not isinstance(
        job_input,
        dict,
    ):

        raise ValueError(
            "job.input debe ser un objeto."
        )

    action = job_input.get(
        "action",
        "test",
    )

    log(
        "=============================================="
    )

    log(
        "JOB RECIBIDO"
    )

    log(
        "=============================================="
    )

    log(
        f"action={action}"
    )

    # --------------------------------------------------------
    # TEST NORMAL
    # --------------------------------------------------------

    if action == "test":
        return test_handler()

    # --------------------------------------------------------
    # GITHUB TEST
    # --------------------------------------------------------

    if action == "github_test":
        return github_test()

    # --------------------------------------------------------
    # GITHUB UPLOAD TEST
    # --------------------------------------------------------

    if action == "github_upload_test":

        test_path = job_input.get(
            "path",
            "/runpod-volume/video/"
            "LTX23_test_00001_.mp4",
        )

        result = github_upload_file(
            test_path,
            asset_name=(
                f"ltx_test_"
                f"{int(time.time())}.mp4"
            ),
        )

        return {

            "ok":
                True,

            "action":
                "github_upload_test",

            "file":
                test_path,

            "upload":
                result,
        }

    # --------------------------------------------------------
    # GITHUB DELETE ASSET
    # --------------------------------------------------------

    if action == "github_delete_asset":

        asset_id = job_input.get(
            "asset_id"
        )

        if asset_id is None:

            raise ValueError(
                "Falta input.asset_id"
            )

        return github_delete_asset(
            asset_id
        )

    # --------------------------------------------------------
    # STORAGE INFO
    # --------------------------------------------------------

    if action == "storage_info":

        log(
            "=== CONSULTANDO "
            "STORAGE INFO ==="
        )

        result = (
            get_storage_info()
        )

        log(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        return result

    # --------------------------------------------------------
    # LIST NODES
    # --------------------------------------------------------

    if action == "list_nodes":
        return list_nodes()

    # --------------------------------------------------------
    # INSPECT LTX
    # --------------------------------------------------------

    if action == "inspect_ltx":
        return inspect_ltx()

    # --------------------------------------------------------
    # GENERATE
    # --------------------------------------------------------

    if action == "generate":

        return generate_video(
            job_input
        )

    # --------------------------------------------------------
    # UNKNOWN ACTION
    # --------------------------------------------------------

    raise ValueError(
        f"Accion desconocida: "
        f"{action}"
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    log(
        "LTX HANDLER PROPIO"
    )

    log(
        "=============================================="
    )

    start_comfyui()

    log(
        "=== COMFYUI CONFIRMADO ==="
    )

    log(
        "=== INICIANDO RUNPOD SERVERLESS ==="
    )

    import runpod

    runpod.serverless.start({
        "handler":
            handler
    })
