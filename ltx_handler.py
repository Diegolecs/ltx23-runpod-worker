def handler(job):
    print("===== HANDLER TEST 1 =====", flush=True)
    print(f"JOB RECIBIDO: {job}", flush=True)

    return {
        "ok": True,
        "message": "El handler propio funciona",
        "job_id": job.get("id")
    }
