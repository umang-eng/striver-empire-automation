"""Persistent file storage adapter supporting local filesystem, S3-compatible storage, and Vercel Blob."""

import os
from pathlib import Path
from typing import Optional

import httpx


class StorageManager:
    """Stores and retrieves generated Excel and PDF artifacts across local or cloud storage."""

    def __init__(self) -> None:
        self.s3_bucket = (os.getenv("S3_BUCKET") or "").strip()
        self.s3_endpoint = (os.getenv("S3_ENDPOINT_URL") or "").strip() or None
        self.s3_region = (os.getenv("AWS_REGION") or "auto").strip()
        self.blob_token = (os.getenv("BLOB_READ_WRITE_TOKEN") or "").strip()

        if self.s3_bucket:
            self.mode = "s3"
        elif self.blob_token:
            self.mode = "vercel_blob"
        else:
            self.mode = "local"

    def save_file(self, local_path: Path, subfolder: str, filename: str) -> str:
        """Persist a generated file and return its storage key/URL."""
        if self.mode == "s3":
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint,
                region_name=self.s3_region,
            )
            key = f"reports/{subfolder}/{filename}"
            client.upload_file(str(local_path), self.s3_bucket, key)
            return key

        if self.mode == "vercel_blob":
            pathname = f"reports/{subfolder}/{filename}"
            content_type = (
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                if filename.endswith(".xlsx")
                else "application/pdf"
            )
            with local_path.open("rb") as fh:
                resp = httpx.put(
                    f"https://blob.vercel-storage.com/{pathname}",
                    content=fh.read(),
                    headers={
                        "authorization": f"Bearer {self.blob_token}",
                        "content-type": content_type,
                        "x-api-version": "7",
                    },
                    timeout=60.0,
                )
            resp.raise_for_status()
            data = resp.json()
            return str(data["url"])

        # Local persistent path relative to workspace root
        return str(local_path)

    def read_bytes(self, storage_key: str) -> Optional[bytes]:
        """Load file bytes securely from the configured storage backend."""
        if not storage_key:
            return None

        if self.mode == "s3" and not Path(storage_key).exists():
            import boto3

            client = boto3.client(
                "s3",
                endpoint_url=self.s3_endpoint,
                region_name=self.s3_region,
            )
            obj = client.get_object(Bucket=self.s3_bucket, Key=storage_key)
            return obj["Body"].read()

        if self.mode == "vercel_blob" and storage_key.startswith("https://"):
            resp = httpx.get(
                storage_key,
                headers={"authorization": f"Bearer {self.blob_token}"},
                timeout=60.0,
            )
            if resp.status_code == 200:
                return resp.content
            return None

        path = Path(storage_key)
        if path.exists() and path.is_file():
            return path.read_bytes()
        return None

    def delete_file(self, storage_key: str) -> None:
        """Delete a stored artifact if it exists."""
        if not storage_key:
            return
        try:
            if self.mode == "s3" and not Path(storage_key).exists():
                import boto3

                client = boto3.client(
                    "s3",
                    endpoint_url=self.s3_endpoint,
                    region_name=self.s3_region,
                )
                client.delete_object(Bucket=self.s3_bucket, Key=storage_key)
                return
            if self.mode == "vercel_blob" and storage_key.startswith("https://"):
                httpx.post(
                    "https://blob.vercel-storage.com/delete",
                    json={"urls": [storage_key]},
                    headers={"authorization": f"Bearer {self.blob_token}"},
                    timeout=30.0,
                )
                return
            path = Path(storage_key)
            if path.exists() and path.is_file():
                path.unlink()
        except Exception:
            pass
