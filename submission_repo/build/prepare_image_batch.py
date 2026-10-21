"""Audit all sources, recover a bounded pilot, flag duplicates, select reviews.

No vision/embedding calls and no Chroma writes. Historical manifest is immutable.
Run from submission_repo: python -m build.prepare_image_batch audit|recover|group|batch
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "prompt_from_web/innoacademy/preparation"
RAW = ROOT / "submission_repo/data/web_academy"
if (RAW / "tools").exists():
    sys.path.insert(0, str(RAW / "tools"))
from PIL import Image, ImageOps
from build import scrape
MANIFEST = ROOT / "prompt_from_web/innoacademy/manifest.json"
REVIEWS = ROOT / "prompt_from_web/innoacademy/manual_reviews.json"
HOST = "innoacademy.engg.hku.hk"
MAX_BYTES = 40 * 1024 * 1024


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else default


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_path(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def audit():
    manifest, reviews = read(MANIFEST), read(REVIEWS, {})
    recovery = read(OUT / "recovery.json", {})
    assets = []
    for folder in (ROOT / "image_source", ROOT / "submission_repo/image_hzq"):
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".heic", ".webp"}:
                continue
            assets.append({"source_id": path.relative_to(ROOT).as_posix(), "source_type": "physical_photo",
                           "sha256": digest(path), "local_path": path.relative_to(ROOT).as_posix(),
                           "file_state": "verified", "capture_date": "unknown"})
    for ident, item in sorted(manifest.items()):
        relative = item.get("local_path")
        historical_path = relative
        recovered = recovery.get(ident, {})
        if recovered.get("status") == "recovered":
            relative = recovered["local_path"]
        exists = bool(relative) and safe_path(relative).is_file()
        actual = digest(safe_path(relative)) if exists else None
        file_state = "missing"
        if exists:
            file_state = ("verified" if actual == item.get("sha256") else "hash_changed") if item.get("sha256") else "captured_without_prior_hash"
        assets.append({"source_id": ident, "source_type": "web_image", "url": item["url"],
                       "local_path": relative, "sha256": item.get("sha256"), "actual_sha256": actual,
                       "historical_local_path": historical_path,
                       "file_state": file_state,
                       "historical_download_status": item.get("download_status"),
                       "description_completed": reviews.get(item.get("sha256"), {}).get("status") == "completed",
                       "retrieved_at": item.get("retrieved_at"), "capture_date": "unknown"})
    groups = defaultdict(list)
    for asset in assets:
        if asset.get("sha256"):
            groups[asset["sha256"]].append(asset["source_id"])
    result = {"audited_at": datetime.now(timezone.utc).isoformat(), "assets": assets,
              "summary": {"physical_photos": sum(a["source_type"] == "physical_photo" for a in assets),
                          "website_urls": len(manifest),
                          "file_states": dict(Counter(a["file_state"] for a in assets))}}
    save(OUT / "inventory.json", result)
    save(OUT / "exact_duplicates.json", {"basis": "historical web SHA-256; verified current local-photo SHA-256",
         "groups": [{"sha256": h, "source_ids": ids} for h, ids in groups.items() if len(ids) > 1]})
    print(json.dumps(result["summary"]))


def priority(item):
    url = item["url"].lower()
    width, height = item.get("width", 0), item.get("height", 0)
    reason = []
    if any(word in url for word in ("logo", "icon", "facebook", "transparent", "banner")):
        return -100, ["branding_or_banner_candidate"]
    if width and height and (min(width, height) < 240 or max(width, height) / min(width, height) > 4):
        return -90, ["small_or_extreme_aspect_ratio"]
    if item.get("bytes", 0) > MAX_BYTES:
        return -80, ["large_file_deferred"]
    score = 1
    for keyword, bonus in (("poster", 10), ("equipment", 9), ("machine", 8), ("sign", 6),
                           ("award", 6), ("robot", 5), ("project", 4), ("innoshow", 3)):
        if keyword in url:
            score += bonus
            reason.append(keyword)
    return score, reason or ["general_event_photo"]


def select_candidates(manifest, reviews, limit):
    by_hash = {}
    for item in manifest.values():
        if urlparse(item["url"]).netloc.lower() != HOST or item.get("description_status") == "unsupported_format":
            continue
        key = item.get("sha256") or item["id"]
        if key not in by_hash or item.get("width", 0) * item.get("height", 0) > by_hash[key].get("width", 0) * by_hash[key].get("height", 0):
            by_hash[key] = item
    completed = [v for h, v in by_hash.items() if reviews.get(h, {}).get("status") == "completed"]
    pending = sorted((v for h, v in by_hash.items() if h not in reviews and priority(v)[0] >= 0),
                     key=lambda v: (-priority(v)[0], v["id"]))
    chosen, page_counts = [], Counter()
    for item in pending:
        page = next((o.get("source_page") for o in item.get("occurrences", []) if o.get("source_page")), item["id"])
        if page_counts[page] >= 3:
            continue
        page_counts[page] += 1
        chosen.append(item)
        if len(chosen) >= limit:
            break
    return completed + chosen


def recover(limit, workers):
    manifest, reviews = read(MANIFEST), read(REVIEWS, {})
    selected = select_candidates(manifest, reviews, limit)
    state = read(OUT / "recovery.json", {})
    robots = RobotFileParser()
    with scrape.build_session() as session:
        response = session.get("https://" + HOST + "/robots.txt", timeout=(15, 60))
        if response.status_code == 404:
            robots.parse([])
        else:
            response.raise_for_status()
            robots.parse(response.text.splitlines())
    save(OUT / "recovery_selection.json", [{"id": i["id"], "url": i["url"],
         "priority": priority(i)[0], "reasons": priority(i)[1]} for i in selected])

    def one(item):
        old = state.get(item["id"], {})
        if old.get("status") == "recovered" and safe_path(old["local_path"]).is_file() and digest(safe_path(old["local_path"])) == old["sha256"]:
            return old
        if not robots.can_fetch(scrape.USER_AGENT, item["url"]):
            return {"status": "robots_excluded"}
        with scrape.build_session() as session:
            with session.get(item["url"], stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                if urlparse(response.url).netloc.lower() != HOST:
                    raise ValueError("external redirect")
                mime = response.headers.get("Content-Type", "").split(";")[0].lower()
                if not mime.startswith("image/"):
                    raise ValueError("non-image response")
                data = bytearray()
                for block in response.iter_content(65536):
                    data.extend(block)
                    if len(data) > MAX_BYTES:
                        raise ValueError("image exceeds pilot size limit")
        actual = hashlib.sha256(data).hexdigest()
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif", "image/svg+xml": ".svg"}.get(mime, ".img")
        # Content-addressed recovery never overwrites a previous raw capture.
        path = RAW / "recovered" / (actual + ext)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            temp = path.with_name(path.name + "." + item["id"] + ".tmp")
            temp.write_bytes(data)
            temp.replace(path)
        return {"status": "recovered", "id": item["id"], "url": item["url"],
                "local_path": path.relative_to(ROOT).as_posix(), "sha256": actual,
                "previous_sha256": item.get("sha256"),
                "content_changed": bool(item.get("sha256")) and actual != item["sha256"],
                "bytes": len(data), "content_type": mime, "retrieved_at": datetime.now(timezone.utc).isoformat()}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(one, item): item for item in selected}
        for n, future in enumerate(as_completed(jobs), 1):
            item = jobs[future]
            try:
                state[item["id"]] = future.result()
            except Exception as exc:
                state[item["id"]] = {"status": "failed", "id": item["id"], "url": item["url"], "error_type": type(exc).__name__}
            save(OUT / "recovery.json", state)
            print(f"Recovered/checked {n}/{len(selected)}: {state[item['id']]['status']}", flush=True)
    print(json.dumps(dict(Counter(v["status"] for v in state.values()))))


def fingerprint(path):
    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        width, height = image.size
        pixels = list(image.convert("L").resize((9, 8)).get_flattened_data())
        value = 0
        for y in range(8):
            for x in range(8):
                value = (value << 1) | (pixels[y * 9 + x] > pixels[y * 9 + x + 1])
        return {"dhash": f"{value:016x}", "width": width, "height": height}


def group():
    # Optional decoder is isolated from the shared runtime environment.
    optional = RAW / "tools"
    if optional.exists():
        sys.path.insert(0, str(optional))
    try:
        import pillow_heif
        pillow_heif.register_heif_opener()
    except ImportError:
        pass
    assets = [a for a in read(OUT / "inventory.json")["assets"] if a["source_type"] == "physical_photo"]
    for ident, item in read(OUT / "recovery.json", {}).items():
        if item["status"] == "recovered":
            assets.append({**item, "source_id": ident, "source_type": "web_image"})
    failures = []
    valid = []
    for item in assets:
        try:
            valid.append({**item, **fingerprint(safe_path(item["local_path"]))})
        except Exception as exc:
            failures.append({"source_id": item["source_id"], "error_type": type(exc).__name__})
    pairs, exact = [], defaultdict(list)
    for item in assets:
        exact[item["sha256"]].append(item["source_id"])
    for i, a in enumerate(valid):
        for b in valid[i + 1:]:
            if a["sha256"] == b["sha256"]:
                continue
            ratio_a, ratio_b = a["width"] / a["height"], b["width"] / b["height"]
            distance = bin(int(a["dhash"], 16) ^ int(b["dhash"], 16)).count("1")
            if distance <= 8 and abs(ratio_a / ratio_b - 1) <= .15:
                pairs.append({"a": a["source_id"], "b": b["source_id"], "distance": distance,
                              "cross_source": a["source_type"] != b["source_type"], "status": "candidate_only_not_deleted"})
    save(OUT / "similarity.json", {"algorithm": "64-bit dHash <= 8, aspect ratio within 15%; candidate filter, not proof",
         "assets": valid, "decode_failures": failures, "near_duplicate_candidates": pairs,
         "verified_exact_groups": [{"sha256": h, "source_ids": ids} for h, ids in exact.items() if len(ids) > 1]})
    print(json.dumps({"fingerprinted": len(valid), "decode_failures": len(failures), "near_pairs": len(pairs),
                      "cross_source_near_pairs": sum(p["cross_source"] for p in pairs)}))


def batch(size):
    manifest, reviews = read(MANIFEST), read(REVIEWS, {})
    similarity = read(OUT / "similarity.json")
    assets = {a["source_id"]: a for a in similarity["assets"]}
    selected, hashes, pages = [], set(reviews), Counter()
    hashes.update(a["sha256"] for a in assets.values() if a["source_type"] == "physical_photo")
    neighbors = defaultdict(set)
    for pair in similarity["near_duplicate_candidates"]:
        neighbors[pair["a"]].add(pair["b"])
        neighbors[pair["b"]].add(pair["a"])
    for ident, item in sorted(assets.items(), key=lambda pair: (-priority(manifest[pair[0]])[0] if pair[0] in manifest else 100, pair[0])):
        if item["source_type"] != "web_image" or item["sha256"] in hashes or item.get("content_changed"):
            continue
        if any(s["id"] in neighbors[ident] for s in selected):
            continue
        source = manifest[ident]
        page = next((o.get("source_page") for o in source.get("occurrences", []) if o.get("source_page")), ident)
        if pages[page] >= 2 or min(item["width"], item["height"]) < 240:
            continue
        pages[page] += 1
        hashes.add(item["sha256"])
        selected.append({**item, "id": ident, "priority_reasons": priority(source)[1],
                         "source_pages": sorted({o.get("source_page", "") for o in source.get("occurrences", [])}),
                         "near_duplicate_candidates": sorted(neighbors[ident]), "capture_date": "unknown"})
        if len(selected) >= size:
            break
    for item in selected:
        preview = RAW / "previews" / (item["id"] + ".jpg")
        preview.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(safe_path(item["local_path"])) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((2600, 2600))
            image.save(preview, quality=95)
        item["preview_path"] = preview.relative_to(ROOT).as_posix()
    save(OUT / "pilot_batch.json", selected)
    save(OUT / "sol_batch.json", selected[::2])
    save(OUT / "luna_batch.json", selected[1::2])
    print(json.dumps({"selected": len(selected), "sol": len(selected[::2]), "luna": len(selected[1::2])}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["audit", "recover", "group", "batch"])
    parser.add_argument("--limit", type=int, default=60)
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=3)
    parser.add_argument("--size", type=int, default=20)
    args = parser.parse_args()
    if args.limit < 1 or args.size < 1:
        parser.error("limit and size must be positive")
    if args.stage == "audit": audit()
    elif args.stage == "recover": recover(args.limit, args.workers)
    elif args.stage == "group": group()
    else: batch(args.size)


if __name__ == "__main__":
    main()
