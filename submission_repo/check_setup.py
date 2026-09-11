"""Verify your setup before Workshop 1. GIVEN.

    python check_setup.py

Checks the required packages are installed and makes one live call to
each of the three gateway deployments. Paste the summary line when
asked, before Workshop 1.
"""
import sys


def check_imports():
    missing = []
    for mod in ("openai", "chromadb", "bs4", "requests", "dotenv"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print(f"  packages                 FAIL  missing: {', '.join(missing)}")
        print("\n  Run: pip install -r requirements.txt")
        return False
    print("  packages                 PASS")
    return True


def check_env():
    import os
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if not os.environ.get("AZURE_OPENAI_KEY", "").strip():
        print("  .env loaded              FAIL  AZURE_OPENAI_KEY not set")
        print("\n  Copy .env.example to .env and fill in your key.")
        return False
    print("  .env loaded              PASS")
    return True


def check_calls():
    import time
    from bot.llm import chat, embed, CHAT_DEPLOYMENT, EMBED_DEPLOYMENT

    ok = True
    t0 = time.time()
    try:
        chat([{"role": "user", "content": "Reply with one word: connected"}],
             model=CHAT_DEPLOYMENT, max_tokens=5)
        print(f"  chat call                PASS   {time.time() - t0:.1f}s")
    except Exception as exc:                        # noqa: BLE001
        print(f"  chat call                FAIL   {type(exc).__name__}: {str(exc)[:100]}")
        ok = False

    t0 = time.time()
    try:
        embed(["test"])
        print(f"  embedding call           PASS   {time.time() - t0:.1f}s")
    except Exception as exc:                        # noqa: BLE001
        print(f"  embedding call           FAIL   {type(exc).__name__}: {str(exc)[:100]}")
        ok = False

    return ok


if __name__ == "__main__":
    print()
    ok = check_imports()
    ok = check_env() and ok
    if ok:
        ok = check_calls() and ok
    print()
    if ok:
        print("  READY")
    else:
        print("  NOT READY. Fix the failures above and run this again.")
        sys.exit(1)
