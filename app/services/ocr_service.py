import json
import httpx
from time import time
from uuid import uuid4
from app.core.config import settings
from app.schemas.ocr import OcrRawItem


async def scan_receipt(image_bytes: bytes, filename: str) -> list[OcrRawItem]:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    message = {
        "images": [{"format": ext, "name": filename}],
        "requestId": str(uuid4()),
        "version": "V2",
        "timestamp": int(time() * 1000),
    }
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.post(
            settings.clova_ocr_url,
            headers={"X-OCR-SECRET": settings.clova_ocr_secret},
            files={
                "message": (None, json.dumps(message), "application/json"),
                "file": (filename, image_bytes),
            },
        )
    resp.raise_for_status()
    data = resp.json()

    items: list[OcrRawItem] = []
    for image in data.get("images", []):
        sub_results = (image.get("receipt") or {}).get("result", {}).get("subResults", [])
        for sub in sub_results:
            for item in sub.get("items", []):
                text = (item.get("name") or {}).get("text", "").strip()
                if text:
                    items.append(OcrRawItem(text=text))
    return items
