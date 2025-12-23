import os
import io
from datetime import datetime, timezone
from PIL import Image
import boto3


BUCKET = os.getenv("R2_BUCKET")
FOLDER = "uploads"
URL = f"https://{os.getenv('CLOUDFLARE_ACCOUNT_ID')}.r2.cloudflarestorage.com"

s3 = boto3.client(
    service_name="s3",
    endpoint_url=URL,
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    region_name="auto",
)


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
    return buffer, ext


def upload_to_s3(buffer: io.BytesIO, ext: str, original_name: str):
    base = os.path.splitext(os.path.basename(original_name))[0]

    ts = int(datetime.now(timezone.utc).timestamp())
    key = f"{FOLDER}/{base}-{ts}.{ext}"

    s3.upload_fileobj(buffer, BUCKET, key)

    return key


def generate_signed_url(key: str, expires_in=3600):
    try:
        return s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": BUCKET, "Key": key},
                ExpiresIn=expires_in
            )
    except Exception as e:
        print(f"Error generating signed URL: {e}")
        return None
    

def delete_s3_object(key: str):
    try:
        s3.delete_object(Bucket=BUCKET, Key=key)
    except Exception as e:
        print(f"Error deleting S3 object {key}: {e}")


def get_all_urls(db_items: list):
    items_response = []
    
    for item in db_items:
        data = item.model_dump()
        data["image"] = generate_signed_url(item.image)
        items_response.append(data)

    return items_response
