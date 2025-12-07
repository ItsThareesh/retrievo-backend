import os
import io
from datetime import datetime, timezone
from PIL import Image
import boto3
from botocore.config import Config


BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("S3_REGION")
FOLDER = "uploads"

my_config = Config(
    region_name=REGION,
    retries={
        'max_attempts': 5,
        'mode': 'standard'
    }
)

s3 = boto3.client("s3", config=my_config)


def compress_image(data: bytes, max_width=1400, quality=80):
    img = Image.open(io.BytesIO(data))
    img = img.convert("RGB")

    # Resize while keeping aspect ratio
    w, h = img.size
    if w > max_width:
        new_height = int(h * (max_width / w))
        img = img.resize((max_width, new_height), Image.LANCZOS)

    # Try WebP first
    buffer = io.BytesIO()

    try:
        img.save(buffer, format="WEBP", quality=quality, method=6)
        ext = "webp"
        mime = "image/webp"
    except Exception as e:
        print("WebP failed, falling back to JPEG:", e)

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=80, optimize=True)
        ext = "jpg"
        mime = "image/jpeg"

    buffer.seek(0)
    return buffer, ext, mime


def upload_to_s3(buffer: io.BytesIO, ext: str, mime: str, original_name: str):
    base = os.path.splitext(os.path.basename(original_name))[0]

    ts = int(datetime.now(timezone.utc).timestamp())
    key = f"{FOLDER}/{base}-{ts}.{ext}"

    s3.upload_fileobj(
        buffer,
        BUCKET,
        key,
        ExtraArgs={"ContentType": mime, "ACL": "private"}
    )

    return key


def generate_signed_url(key: str, expires_in=3600):
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=expires_in
    )
