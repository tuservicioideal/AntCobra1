"""Rutas de Storage que una Function puede tocar para un job."""


def is_owned_storage_path(path: str, uid: str, job_id: str) -> bool:
    if not path or not uid or not job_id:
        return False
    if ".." in path or path.startswith("/"):
        return False
    prefix = f"cartera_uploads/{uid}/{job_id}/"
    return path.startswith(prefix)
