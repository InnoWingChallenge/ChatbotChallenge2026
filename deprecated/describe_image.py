from dotenv import load_dotenv
import os
import base64
import mimetypes
from typing import Optional
from openai import AzureOpenAI


load_dotenv()

API_Key = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_AZURE_ENDPOINT") or os.getenv("AZURE_OPENAI_API_URL")
MODEL = os.getenv("AZURE_OPENAI_MODEL") or "gpt-4o-mini"

if not API_Key:
    raise RuntimeError("Missing Azure OpenAI credentials. Set AZURE_OPENAI_API_KEY in .env or environment.")
if not AZURE_ENDPOINT:
    raise RuntimeError("Missing Azure OpenAI endpoint. Set AZURE_OPENAI_AZURE_ENDPOINT or AZURE_OPENAI_API_URL.")


def _image_to_data_url(path: str) -> str:
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    data = open(path, "rb").read()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:{mime};base64,{b64}"


def describe_image(image_path: Optional[str] = None, image_url: Optional[str] = None) -> str:
    """Return a short description for the image at `image_path` or `image_url`.

    If `image_path` is provided it will be encoded as a data URL and sent inline.
    """
    client = AzureOpenAI(azure_endpoint=AZURE_ENDPOINT, api_key=API_Key, api_version="2025-01-01-preview")

    if image_path:
        img_ref = _image_to_data_url(image_path)
    elif image_url:
        img_ref = image_url
    else:
        raise ValueError("Provide either image_path or image_url")

    # Construct a multimodal `input` with an image then a text instruction.
    input_payload = [
        {
            "role": "user",
            "content": [
                {"type": "input_image", "image_url": img_ref},
                {
                    "type": "input_text",
                    "text": (
                        "Please provide a concise description of the above image in 2-3 sentences. "
                        "Mention visible objects, prominent colors, and the overall mood. "
                        "Return only the description text."
                    ),
                },
            ],
        }
    ]

    resp = client.responses.create(model=MODEL, input=input_payload, max_output_tokens=500)

    # Prefer `output_text` if present, otherwise try to extract text content from structured output.
    if hasattr(resp, "output_text") and getattr(resp, "output_text"):
        return resp.output_text

    # Attempt to extract from resp.output (various SDK shapes)
    try:
        parts = []
        for item in getattr(resp, "output", []) or []:
            if isinstance(item, dict):
                for c in item.get("content", []) or []:
                    if isinstance(c, dict) and c.get("type") in ("output_text", "text"):
                        parts.append(c.get("text") or c.get("content") or "")
                    elif isinstance(c, str):
                        parts.append(c)
            elif isinstance(item, str):
                parts.append(item)
        if parts:
            return "\n".join([p for p in parts if p])
    except Exception:
        pass

    # Fallback: return the raw response representation
    return str(resp)


if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="Describe an image using Azure OpenAI")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--image-path", help="Local image file path to describe")
    g.add_argument("--image-url", help="Public image URL to describe")
    args = p.parse_args()

    desc = describe_image(image_path=args.image_path, image_url=args.image_url)
    print(desc)
