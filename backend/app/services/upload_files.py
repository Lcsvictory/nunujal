import re
import uuid
from urllib.parse import quote

from fastapi import HTTPException


IMAGE_CONTENT_TYPE_PREFIX = "image/"


def is_image_content_type(content_type: str | None) -> bool:
    return bool(content_type and content_type.lower().startswith(IMAGE_CONTENT_TYPE_PREFIX))


def safe_file_name(file_name: str) -> str:
    stripped = file_name.strip().replace("\\", "_").replace("/", "_")
    cleaned = re.sub(r"\s+", " ", stripped)
    return cleaned[:180] or "file"


def build_s3_object_key(project_id: int, file_name: str, prefix: str) -> str:
    normalized_prefix = prefix.strip("/")
    normalized_file_name = safe_file_name(file_name)
    unique_name = f"{uuid.uuid4().hex}-{normalized_file_name}"
    if normalized_prefix:
        return f"{normalized_prefix}/projects/{project_id}/{unique_name}"
    return f"projects/{project_id}/{unique_name}"


def _create_s3_client(settings):
    if not settings.s3_bucket_name:
        raise HTTPException(status_code=503, detail="S3 bucket is not configured.")

    try:
        import boto3
        from botocore.config import Config
    except ImportError as exc:
        raise HTTPException(status_code=503, detail="boto3 is not installed.") from exc

    kwargs = {
        "region_name": settings.aws_region,
        "endpoint_url": f"https://s3.{settings.aws_region}.amazonaws.com",
        "config": Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    }
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client("s3", **kwargs)


def create_presigned_upload_url(settings, *, object_key: str, content_type: str) -> str:
    client = _create_s3_client(settings)
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket_name,
            "Key": object_key,
            "ContentType": content_type,
        },
        ExpiresIn=settings.s3_presigned_expire_seconds,
    )


def delete_s3_object(settings, *, object_key: str) -> None:
    client = _create_s3_client(settings)
    client.delete_object(Bucket=settings.s3_bucket_name, Key=object_key)


def create_presigned_download_url(
    settings,
    *,
    object_key: str,
    file_name: str,
    as_attachment: bool,
) -> str:
    client = _create_s3_client(settings)
    params = {
        "Bucket": settings.s3_bucket_name,
        "Key": object_key,
    }
    if as_attachment:
        ascii_name = safe_file_name(file_name).encode("ascii", "ignore").decode("ascii") or "download"
        params["ResponseContentDisposition"] = (
            f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name)}"
        )

    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=settings.s3_presigned_expire_seconds,
    )


def get_s3_object_size(settings, *, object_key: str) -> int:
    client = _create_s3_client(settings)
    response = client.head_object(Bucket=settings.s3_bucket_name, Key=object_key)
    return int(response.get("ContentLength") or 0)
