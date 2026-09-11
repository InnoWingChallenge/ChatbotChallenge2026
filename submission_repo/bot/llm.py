"""Gateway client. GIVEN. You should not need to edit this file.

Three deployments, three clients, because this gateway takes the full
path (deployment, operation and api-version) as the endpoint, so one
client can only ever talk to one deployment.

Reads settings from the environment. Copy .env.example to .env and
fill in the values you were given.
"""
import base64
import mimetypes
import os
from pathlib import Path

from openai import AzureOpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
CHAT_BASE   = os.getenv("AZURE_CHAT_BASE",  "https://api-iw.azure-api.net/sig-shared-jpeast-increased")
EMBED_BASE  = os.getenv("AZURE_EMBED_BASE", "https://api-iw.azure-api.net/sig-embedding")

CHAT_DEPLOYMENT   = os.getenv("CHAT_DEPLOYMENT",   "gpt-4o-mini")
VISION_DEPLOYMENT = os.getenv("VISION_DEPLOYMENT", "gpt-5-mini")
EMBED_DEPLOYMENT  = os.getenv("EMBED_DEPLOYMENT",  "text-embedding-3-small")

# The chat route has no /openai segment; the embedding route does. This
# asymmetry is real, confirmed against the live gateway. Do not "tidy"
# the two into matching, or one of them will 404.
CHAT_URL   = f"{CHAT_BASE}/deployments/{CHAT_DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
VISION_URL = f"{CHAT_BASE}/deployments/{VISION_DEPLOYMENT}/chat/completions?api-version={API_VERSION}"
EMBED_URL  = f"{EMBED_BASE}/openai/deployments/{EMBED_DEPLOYMENT}/embeddings?api-version={API_VERSION}"

# .strip() matters: pasting a key into a shell or .env often picks up a
# trailing newline, and that alone produces a 401.
_KEY = os.environ.get("AZURE_OPENAI_KEY", "").strip()

# Clients are built lazily, on first real use, not here at import time.
# The openai SDK itself raises if api_key is empty, and this module is
# imported by main.py before main() gets a chance to run its own error
# handling. Building clients eagerly meant a missing key crashed with a
# raw traceback on every single run, including `python main.py` with no
# arguments. check_setup.py is what should catch a missing key, in a
# readable way, before you ever run main.py for real.
_clients: dict = {}


def _client(url: str) -> AzureOpenAI:
    if url not in _clients:
        if not _KEY:
            raise RuntimeError(
                "AZURE_OPENAI_KEY is not set. Copy .env.example to .env "
                "and fill in your key, then run check_setup.py."
            )
        _clients[url] = AzureOpenAI(azure_endpoint=url, api_key=_KEY, api_version=API_VERSION)
    return _clients[url]


def chat(messages: list[dict], model: str = None, temperature: float = 0.0,
         max_tokens: int = 512) -> str:
    """One chat completion. Returns the reply text."""
    r = _client(CHAT_URL).chat.completions.create(
        model=model or CHAT_DEPLOYMENT, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
    )
    return r.choices[0].message.content or ""


def ask(prompt: str, system: str = None, **kw) -> str:
    """Shorthand for a single-turn call."""
    msgs = ([{"role": "system", "content": system}] if system else [])
    return chat(msgs + [{"role": "user", "content": prompt}], **kw)


def embed(texts: list[str], batch_size: int = 256) -> list[list[float]]:
    """Embed a LIST of strings. One call per string is the slow mistake:
    thousands of round trips at ~200ms each is minutes spent waiting on
    the network. Always batch."""
    texts = [t.replace("\n", " ") for t in texts]
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        r = _client(EMBED_URL).embeddings.create(
            model=EMBED_DEPLOYMENT, input=texts[i:i + batch_size]
        )
        out.extend(d.embedding for d in r.data)
    return out


def describe_image(image_path: str, prompt: str) -> str:
    """Send one image plus an instruction to the vision deployment.

    No default prompt: writing it is the Workshop 2 block 3 exercise,
    and it belongs in build/images.py, not here.
    """
    path = Path(image_path)
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    b64 = base64.b64encode(path.read_bytes()).decode()
    r = _client(VISION_URL).chat.completions.create(
        model=VISION_DEPLOYMENT, max_tokens=800,
        messages=[{"role": "user", "content": [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]}],
    )
    return r.choices[0].message.content or ""
