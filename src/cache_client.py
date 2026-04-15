"""Read/write performance baselines via the GitHub Actions Cache REST API."""

import io
import json
import os
import tarfile
import tempfile

import requests

_BASELINE_FILENAME = "baseline.json"


def _cache_url() -> str:
    url = os.environ.get("ACTIONS_CACHE_URL", "")
    if not url.endswith("/"):
        url += "/"
    return url


def _token() -> str:
    return os.environ.get("ACTIONS_RUNTIME_TOKEN", "")


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/json;api-version=6.0-preview.1",
        "Content-Type": "application/json",
    }


def _cache_key(base_ref: str) -> str:
    return f"slop-perf-{base_ref}"


def get_baseline(base_ref: str) -> dict | None:
    """Fetch baseline timing data from the Actions cache. Returns None if not found."""
    cache_url = _cache_url()
    token = _token()
    if not cache_url or not token:
        return None

    key = _cache_key(base_ref)
    try:
        resp = requests.get(
            f"{cache_url}_apis/artifactcache/cache",
            headers=_headers(),
            params={"keys": key, "version": "1"},
            timeout=30,
        )
        if resp.status_code == 204:
            return None
        resp.raise_for_status()
        cache_entry = resp.json()
        archive_url = cache_entry.get("archiveLocation")
        if not archive_url:
            return None

        download = requests.get(archive_url, timeout=60)
        download.raise_for_status()

        with tarfile.open(fileobj=io.BytesIO(download.content), mode="r:gz") as tar:
            member = tar.getmember(_BASELINE_FILENAME)
            f = tar.extractfile(member)
            return json.loads(f.read())
    except Exception:
        return None


def save_baseline(base_ref: str, data: dict) -> None:
    """Upload baseline timing data to the Actions cache."""
    cache_url = _cache_url()
    token = _token()
    if not cache_url or not token:
        return

    key = _cache_key(base_ref)

    # Create a tar.gz archive containing baseline.json
    with tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with tarfile.open(tmp_path, "w:gz") as tar:
            raw = json.dumps(data).encode()
            info = tarfile.TarInfo(name=_BASELINE_FILENAME)
            info.size = len(raw)
            tar.addfile(info, io.BytesIO(raw))

        with open(tmp_path, "rb") as f:
            archive_bytes = f.read()
    finally:
        os.unlink(tmp_path)

    try:
        # Reserve a cache entry
        reserve_resp = requests.post(
            f"{cache_url}_apis/artifactcache/caches",
            headers=_headers(),
            json={"key": key, "version": "1"},
            timeout=30,
        )
        reserve_resp.raise_for_status()
        cache_id = reserve_resp.json()["cacheId"]

        # Upload the archive
        upload_headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;api-version=6.0-preview.1",
            "Content-Type": "application/octet-stream",
            "Content-Range": f"bytes 0-{len(archive_bytes) - 1}/*",
        }
        patch_resp = requests.patch(
            f"{cache_url}_apis/artifactcache/caches/{cache_id}",
            headers=upload_headers,
            data=archive_bytes,
            timeout=60,
        )
        patch_resp.raise_for_status()

        # Commit the cache entry
        commit_resp = requests.post(
            f"{cache_url}_apis/artifactcache/caches/{cache_id}",
            headers=_headers(),
            json={"size": len(archive_bytes)},
            timeout=30,
        )
        commit_resp.raise_for_status()
    except Exception:
        pass  # Cache save is best-effort; don't fail the action
