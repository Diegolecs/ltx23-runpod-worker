import runpod
import traceback


print("==============================================", flush=True)
print("LTX HANDLER PROPIO - TEST MINIMO", flush=True)
print("==============================================", flush=True)


def handler(job):
    print("=== CALLBACK REAL OK ===", flush=True)

    try:
        print(f"JOB COMPLETO: {job}", flush=True)

        job_id = job.get("id")

        result = {
            "ok": True,
            "message": "El handler propio está funcionando correctamente.",
            "job_id": job_id,
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
        }


print("=== INICIANDO RUNPOD SERVERLESS ===", flush=True)

runpod.serverless.start({
    "handler": handler
})
