"""Unified media storage — works with any S3-compatible provider or falls back to local disk.

Supported cloud providers: AWS S3, DigitalOcean Spaces, Cloudflare R2, MinIO, Backblaze B2.

Environment variables:
    S3_ENDPOINT_URL  — Custom endpoint (required for non-AWS providers)
    S3_BUCKET        — Bucket name
    S3_REGION        — Region (default: us-east-1)
    S3_ACCESS_KEY    — Access key ID
    S3_SECRET_KEY    — Secret access key
    S3_PUBLIC_URL    — Public base URL for uploaded objects (optional; derived from endpoint if absent)

If S3_BUCKET is not set the system stores files locally under /app/media/ and serves
them via the FastAPI static mount at /media.  The system never stops — it stores locally
until cloud storage is connected.
"""

from __future__ import annotations

import logging
import mimetypes
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCAL_MEDIA_ROOT = Path(os.getenv("LOCAL_MEDIA_ROOT", "/app/media"))
LOCAL_MEDIA_URL_PREFIX = "/media"

# ---------------------------------------------------------------------------
# MediaStorage
# ---------------------------------------------------------------------------


class MediaStorage:
    """Unified storage that targets S3-compatible buckets or local disk."""

    def __init__(self) -> None:
        self._endpoint_url: Optional[str] = os.getenv("S3_ENDPOINT_URL")
        self._bucket: Optional[str] = os.getenv("S3_BUCKET")
        self._region: str = os.getenv("S3_REGION", "us-east-1")
        self._access_key: Optional[str] = os.getenv("S3_ACCESS_KEY")
        self._secret_key: Optional[str] = os.getenv("S3_SECRET_KEY")
        self._public_url: Optional[str] = os.getenv("S3_PUBLIC_URL")

        self._s3_client = None
        self._use_s3 = bool(self._bucket and self._access_key and self._secret_key)

        if self._use_s3:
            self._init_s3()
        else:
            logger.info(
                "S3 not configured — using local storage at %s. "
                "Set S3_BUCKET, S3_ACCESS_KEY, S3_SECRET_KEY to enable cloud storage.",
                LOCAL_MEDIA_ROOT,
            )
            LOCAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    # -- S3 initialisation --------------------------------------------------

    def _init_s3(self) -> None:
        try:
            import boto3
            from botocore.config import Config

            boto_kwargs: dict = {
                "aws_access_key_id": self._access_key,
                "aws_secret_access_key": self._secret_key,
                "region_name": self._region,
                "config": Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            }
            if self._endpoint_url:
                boto_kwargs["endpoint_url"] = self._endpoint_url

            self._s3_client = boto3.client("s3", **boto_kwargs)
            logger.info(
                "S3 storage initialised — bucket=%s region=%s endpoint=%s",
                self._bucket,
                self._region,
                self._endpoint_url or "default (AWS)",
            )
        except Exception:
            logger.exception("Failed to initialise S3 client — falling back to local storage")
            self._use_s3 = False
            LOCAL_MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

    # -- Public helpers -----------------------------------------------------

    @property
    def is_cloud(self) -> bool:
        """True when uploads go to S3-compatible storage."""
        return self._use_s3

    def generate_key(self, prefix: str = "uploads", extension: str = "") -> str:
        """Generate a unique object key: ``<prefix>/<uuid>.<ext>``."""
        ext = extension.lstrip(".") if extension else ""
        unique = uuid.uuid4().hex
        if ext:
            return f"{prefix}/{unique}.{ext}"
        return f"{prefix}/{unique}"

    # -- Upload methods -----------------------------------------------------

    def upload_file(
        self,
        local_path: str | Path,
        key: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> str:
        """Upload a file from the local filesystem and return its public URL.

        Args:
            local_path: Absolute or relative path to the source file.
            key: Optional object key.  If omitted a unique key is generated from the filename.
            content_type: MIME type.  Guessed from the filename when not provided.

        Returns:
            Public URL of the uploaded object.
        """
        local_path = Path(local_path)
        if not local_path.is_file():
            raise FileNotFoundError(f"Source file does not exist: {local_path}")

        if content_type is None:
            content_type = self._guess_content_type(local_path.name)

        if key is None:
            key = self.generate_key(prefix="uploads", extension=local_path.suffix)

        if self._use_s3:
            return self._s3_upload_file(local_path, key, content_type)
        return self._local_save_file(local_path, key)

    def upload_from_url(
        self,
        source_url: str,
        key: Optional[str] = None,
    ) -> str:
        """Download a remote file and persist it to storage.

        Args:
            source_url: HTTP(S) URL to fetch.
            key: Optional object key.

        Returns:
            Public URL of the stored object.
        """
        try:
            with httpx.Client(timeout=60, follow_redirects=True) as client:
                resp = client.get(source_url)
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Failed to download {source_url}: {exc}") from exc

        content_type = resp.headers.get("content-type", "application/octet-stream").split(";")[0].strip()

        if key is None:
            ext = self._extension_from_content_type(content_type) or self._extension_from_url(source_url)
            key = self.generate_key(prefix="downloads", extension=ext)

        return self.upload_bytes(resp.content, key, content_type)

    def upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw bytes and return the public URL.

        Args:
            data: Raw file bytes.
            key: Object key (required).
            content_type: MIME type.

        Returns:
            Public URL of the uploaded object.
        """
        if not key:
            raise ValueError("key is required for upload_bytes")

        if self._use_s3:
            return self._s3_upload_bytes(data, key, content_type)
        return self._local_save_bytes(data, key)

    # -- Delete -------------------------------------------------------------

    def delete(self, key: str) -> bool:
        """Delete an object by key.  Returns True on success, False on failure."""
        if self._use_s3:
            return self._s3_delete(key)
        return self._local_delete(key)

    # -- S3 internals -------------------------------------------------------

    def _s3_upload_file(self, local_path: Path, key: str, content_type: str) -> str:
        extra = {"ContentType": content_type}
        try:
            self._s3_client.upload_file(
                Filename=str(local_path),
                Bucket=self._bucket,
                Key=key,
                ExtraArgs=extra,
            )
            logger.info("S3 upload OK: %s -> s3://%s/%s", local_path, self._bucket, key)
            return self._s3_public_url(key)
        except Exception:
            logger.exception("S3 upload_file failed for key=%s — falling back to local", key)
            return self._local_save_file(local_path, key)

    def _s3_upload_bytes(self, data: bytes, key: str, content_type: str) -> str:
        import io

        extra = {"ContentType": content_type}
        try:
            self._s3_client.upload_fileobj(
                Fileobj=io.BytesIO(data),
                Bucket=self._bucket,
                Key=key,
                ExtraArgs=extra,
            )
            logger.info("S3 upload_bytes OK: key=%s size=%d", key, len(data))
            return self._s3_public_url(key)
        except Exception:
            logger.exception("S3 upload_bytes failed for key=%s — falling back to local", key)
            return self._local_save_bytes(data, key)

    def _s3_delete(self, key: str) -> bool:
        try:
            self._s3_client.delete_object(Bucket=self._bucket, Key=key)
            logger.info("S3 delete OK: s3://%s/%s", self._bucket, key)
            return True
        except Exception:
            logger.exception("S3 delete failed for key=%s", key)
            return False

    def _s3_public_url(self, key: str) -> str:
        if self._public_url:
            base = self._public_url.rstrip("/")
            return f"{base}/{key}"
        if self._endpoint_url:
            base = self._endpoint_url.rstrip("/")
            return f"{base}/{self._bucket}/{key}"
        return f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"

    # -- Local internals ----------------------------------------------------

    def _local_save_file(self, local_path: Path, key: str) -> str:
        dest = LOCAL_MEDIA_ROOT / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(local_path), str(dest))
        logger.info("Local save OK: %s -> %s", local_path, dest)
        return f"{LOCAL_MEDIA_URL_PREFIX}/{key}"

    def _local_save_bytes(self, data: bytes, key: str) -> str:
        dest = LOCAL_MEDIA_ROOT / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        logger.info("Local save OK: key=%s size=%d -> %s", key, len(data), dest)
        return f"{LOCAL_MEDIA_URL_PREFIX}/{key}"

    def _local_delete(self, key: str) -> bool:
        dest = LOCAL_MEDIA_ROOT / key
        try:
            if dest.is_file():
                dest.unlink()
                logger.info("Local delete OK: %s", dest)
                return True
            logger.warning("Local delete — file not found: %s", dest)
            return False
        except Exception:
            logger.exception("Local delete failed for %s", dest)
            return False

    # -- Utility ------------------------------------------------------------

    @staticmethod
    def _guess_content_type(filename: str) -> str:
        ct, _ = mimetypes.guess_type(filename)
        return ct or "application/octet-stream"

    @staticmethod
    def _extension_from_content_type(content_type: str) -> str:
        mapping = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
            "image/gif": "gif",
            "video/mp4": "mp4",
            "video/webm": "webm",
            "audio/mpeg": "mp3",
            "audio/wav": "wav",
            "application/pdf": "pdf",
        }
        return mapping.get(content_type, "")

    @staticmethod
    def _extension_from_url(url: str) -> str:
        """Best-effort extension extraction from a URL path."""
        try:
            path = url.split("?")[0].split("#")[0]
            if "." in path.split("/")[-1]:
                return path.rsplit(".", 1)[-1][:10]
        except Exception:
            pass
        return ""


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_instance: Optional[MediaStorage] = None


def get_storage() -> MediaStorage:
    """Return (and lazily create) a singleton ``MediaStorage`` instance."""
    global _instance
    if _instance is None:
        _instance = MediaStorage()
    return _instance
