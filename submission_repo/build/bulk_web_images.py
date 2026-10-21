"""Resume full website-image recovery and conservative screening, without model calls.

Historical manifest and pilot assignments are read-only. Raw bytes are content-addressed.
python -m build.bulk_web_images download|screen [--workers 4]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
import threading
import time
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from build.prepare_image_batch import (
    ROOT, RAW, OUT, HOST, MANIFEST, REVIEWS, Image, ImageOps,
    read, save, digest, safe_path, priority,
)
from build import scrape

BULK = OUT / "bulk"
STATE = BULK / "recovery.json"
JOURNAL = RAW / "bulk_progress.jsonl"
LIMIT = 300 * 1024 * 1024
TLS = threading.local()


def now():
    return datetime.now(timezone.utc).isoformat()


def session():
    if not hasattr(TLS, "session"):
        TLS.session = scrape.build_session()
    return TLS.session


def cached(entry):
    return (entry.get("status") == "recovered" and entry.get("local_path")
            and safe_path(entry["local_path"]).is_file()
            and digest(safe_path(entry["local_path"])) == entry.get("sha256"))


@contextmanager
def run_lock():
    """OS-owned lock is released on process exit, including an interrupted run."""
    RAW.mkdir(parents=True, exist_ok=True)
    with (RAW / "bulk.lock").open("a+b") as lock:
        lock.seek(0)
        if lock.read(1) == b"":
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError("Another image job is running; do not start a duplicate job") from exc
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def load_state():
    state = read(OUT / "recovery.json", {})
    state.update(read(STATE, {}))
    if JOURNAL.exists():
        for line in JOURNAL.read_text(encoding="utf-8").splitlines():
            try:
                entry = json.loads(line)
                state[entry["id"]] = entry
            except (ValueError, KeyError):
                continue  # An interrupted final journal line is retried.
    return state


def plan(manifest, state, retry_only=False, retry_all=False):
    selected, skipped, deferred = [], [], []
    cache_checks = {}
    for ident, item in manifest.items():
        entry = state.get(ident, {})
        if urlparse(item["url"]).netloc.lower() != HOST:
            deferred.append({"id": ident, "url": item["url"], "reason": "external_reference"})
            continue
        key = (entry.get("local_path"), entry.get("sha256"), entry.get("status"))
        if key not in cache_checks:
            cache_checks[key] = bool(cached(entry))
        if cache_checks[key]:
            skipped.append(ident)
            continue
        deterministic_failure = (entry.get("http_status") in (403, 404, 410)
                                 or entry.get("error_type") == "ValueError"
                                 or entry.get("status") in ("non_image", "oversized", "robots_excluded", "external_redirect"))
        if deterministic_failure and not retry_all:
            deferred.append({"id": ident, "url": item["url"], "reason": entry.get("status"),
                             "http_status": entry.get("http_status"), "error_type": entry.get("error_type")})
        elif retry_only and entry.get("status") != "failed":
            deferred.append({"id": ident, "url": item["url"], "reason": "not_a_failed_record"})
        else:
            selected.append(item)
    result = {"planned_at": now(), "network_requests_made": 0,
              "summary": {"total_urls": len(manifest), "verified_cached_skip": len(skipped),
                          "download_queue": len(selected), "deferred": len(deferred)},
              "verified_cached_ids": skipped,
              "download_queue": [{"id": i["id"], "url": i["url"],
                                  "previous_status": state.get(i["id"], {}).get("status", "missing")} for i in selected],
              "deferred": deferred}
    save(BULK / "download_plan.json", result)
    print(json.dumps(result["summary"]), flush=True)
    return selected


def download(workers, retry_only=False, retry_all=False, dry_run=False):
    manifest, state = read(MANIFEST), load_state()
    selected = plan(manifest, state, retry_only=retry_only, retry_all=retry_all)
    if dry_run:
        return
    for ident, item in manifest.items():
        if urlparse(item["url"]).netloc.lower() != HOST:
            state[ident] = {"id": ident, "url": item["url"], "status": "external_reference"}
    if not selected:
        save(STATE, state)
        return
    robots = RobotFileParser()
    response = session().get("https://" + HOST + "/robots.txt", timeout=(15, 60))
    if response.status_code == 404:
        robots.parse([])
    else:
        response.raise_for_status()
        robots.parse(response.text.splitlines())
    RAW.mkdir(parents=True, exist_ok=True)
    save(STATE, state)
    started = time.monotonic()
    print(f"Queued {len(selected)} URLs; other records skipped or deferred (see download_plan.json)", flush=True)

    def one(item):
        ident, url = item["id"], item["url"]
        base = {"id": ident, "url": url, "previous_sha256": item.get("sha256"), "attempted_at": now()}
        temp = RAW / "partial" / (ident + ".part")
        try:
            if not robots.can_fetch(scrape.USER_AGENT, url):
                return {**base, "status": "robots_excluded"}
            temp.parent.mkdir(parents=True, exist_ok=True)
            with session().get(url, stream=True, timeout=(15, 60)) as response:
                response.raise_for_status()
                if urlparse(response.url).netloc.lower() != HOST:
                    return {**base, "status": "external_redirect"}
                mime = response.headers.get("Content-Type", "").split(";")[0].lower()
                if not mime.startswith("image/"):
                    return {**base, "status": "non_image", "content_type": mime}
                if int(response.headers.get("Content-Length", 0)) > LIMIT:
                    return {**base, "status": "oversized", "limit_bytes": LIMIT}
                h, size = hashlib.sha256(), 0
                with temp.open("wb") as stream:
                    for block in response.iter_content(262144):
                        size += len(block)
                        if size > LIMIT:
                            raise ValueError("size_limit")
                        h.update(block)
                        stream.write(block)
            actual = h.hexdigest()
            ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/gif": ".gif",
                   "image/webp": ".webp", "image/svg+xml": ".svg", "image/tiff": ".tiff",
                   "image/avif": ".avif"}.get(mime, ".img")
            target = RAW / "recovered" / (actual + ext)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp.replace(target)
            return {**base, "status": "recovered", "sha256": actual, "bytes": size,
                    "local_path": target.relative_to(ROOT).as_posix(), "content_type": mime,
                    "content_changed": bool(item.get("sha256")) and item["sha256"] != actual,
                    "retrieved_at": now()}
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) == "size_limit":
                return {**base, "status": "oversized", "limit_bytes": LIMIT}
            return {**base, "status": "failed", "error_type": type(exc).__name__,
                    "http_status": getattr(getattr(exc, "response", None), "status_code", None)}
        finally:
            if temp.exists():
                temp.unlink()

    with JOURNAL.open("a", encoding="utf-8") as journal, ThreadPoolExecutor(max_workers=workers) as pool:
        jobs = {pool.submit(one, item): item["id"] for item in selected}
        for index, future in enumerate(as_completed(jobs), 1):
            entry = future.result()
            state[entry["id"]] = entry
            journal.write(json.dumps(entry, ensure_ascii=False) + "\n")
            journal.flush()
            if index % 100 == 0 or index == len(selected):
                save(STATE, state)
                print(json.dumps({"processed": index, "queued": len(selected), "seconds": round(time.monotonic()-started),
                                  "status": dict(Counter(v["status"] for v in state.values()))}), flush=True)
    save(STATE, state)


def signature(path):
    with Image.open(path) as im:
        width, height = im.size
        if im.getexif().get(274) in (5, 6, 7, 8):
            width, height = height, width
        frames = getattr(im, "n_frames", 1)
        # Avoid decoding huge posters solely for similarity; keep their raw bytes.
        if width * height > 80_000_000:
            return {"width": width, "height": height, "frames": frames, "decode_state": "huge_image_deferred"}
        im.draft("RGB", (512, 512))
        im = ImageOps.exif_transpose(im)
        small = im.convert("L").resize((9, 8))
        pixels = list(small.get_flattened_data())
        value = 0
        for y in range(8):
            for x in range(8):
                value = (value << 1) | (pixels[y*9+x] > pixels[y*9+x+1])
        return {"width": width, "height": height, "frames": frames, "dhash": f"{value:016x}", "decode_state": "decoded"}


def near_pairs(assets):
    # For Hamming distance <= 8, at least one of nine disjoint bit blocks matches.
    buckets = defaultdict(list)
    result = []
    for index, item in enumerate(assets):
        if not item.get("dhash"):
            continue
        value = int(item["dhash"], 16)
        keys = [(n, (value >> (7*n)) & (255 if n == 8 else 127)) for n in range(9)]
        candidates = set(j for key in keys for j in buckets[key])
        for other in sorted(candidates):
            b = assets[other]
            if item["sha256"] == b["sha256"]:
                continue
            aspect = item["width"] * b["height"] / (item["height"] * b["width"])
            if not .85 <= aspect <= 1.15:
                continue
            distance = bin(value ^ int(b["dhash"], 16)).count("1")
            if distance <= 8:
                result.append({"a": b["id"], "b": item["id"], "distance": distance,
                               "cross_source": b["source_type"] != item["source_type"],
                               "decision": "review_candidate_not_deleted"})
        for key in keys:
            buckets[key].append(index)
    return result


def candidate_groups(assets, pairs):
    """Connected candidates are review work units, never equivalence classes."""
    lookup = {a["id"]: a for a in assets}
    graph = defaultdict(set)
    for pair in pairs:
        graph[pair["a"]].add(pair["b"])
        graph[pair["b"]].add(pair["a"])
    seen, groups = set(), []
    for ident in sorted(graph):
        if ident in seen:
            continue
        todo, members = [ident], []
        while todo:
            current = todo.pop()
            if current in seen:
                continue
            seen.add(current)
            members.append(current)
            todo.extend(graph[current] - seen)
        representative = max(members, key=lambda i: (lookup[i].get("width", 0)*lookup[i].get("height", 0), i))
        groups.append({"candidate_representative": representative, "members": sorted(members),
                       "cross_source": len({lookup[i]["source_type"] for i in members}) > 1,
                       "decision": "manual_review_required; connected similarity is not identity"})
    return groups


def screen():
    import pillow_heif
    pillow_heif.register_heif_opener()
    manifest, state, reviews = read(MANIFEST), read(STATE, {}), read(REVIEWS, {})
    pilot = read(OUT / "pilot_reviews.json", {})
    pilot_hashes = {v["sha256"] for v in pilot.values()}
    groups = defaultdict(list)
    for ident, item in state.items():
        if item["status"] == "recovered":
            groups[item["sha256"]].append(ident)
    assets = []
    for folder in (ROOT / "image_source", ROOT / "submission_repo/image_hzq"):
        for path in sorted(folder.rglob("*")):
            if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".heic", ".webp"}:
                assets.append({"id": path.relative_to(ROOT).as_posix(), "source_type": "physical_photo",
                               "local_path": path.relative_to(ROOT).as_posix(), "sha256": digest(path)})
    local_hashes = {a["sha256"] for a in assets}
    for h, ids in sorted(groups.items()):
        ident = max(ids, key=lambda i: priority(manifest[i])[0])
        assets.append({"id": ident, "source_type": "web_image", "sha256": h,
                       "local_path": state[ident]["local_path"], "source_ids": sorted(ids),
                       "url": manifest[ident]["url"], "bytes": state[ident]["bytes"],
                       "historical_hash_changed": any(state[i].get("content_changed", False) for i in ids)})
    feature_cache = read(BULK / "fingerprints.json", {})
    for n, item in enumerate(assets, 1):
        h = item["sha256"]
        if h not in feature_cache:
            try:
                feature_cache[h] = signature(safe_path(item["local_path"]))
            except Exception as exc:
                feature_cache[h] = {"decode_state": "unsupported_or_invalid", "error_type": type(exc).__name__}
        item.update(feature_cache[h])
        if n % 250 == 0:
            save(BULK / "fingerprints.json", feature_cache)
            print(f"Fingerprinted {n}/{len(assets)}", flush=True)
    save(BULK / "fingerprints.json", feature_cache)
    pairs = near_pairs(assets)
    lookup = {a["id"]: a for a in assets}
    rejected = set()
    for review in read(BULK / "pair_reviews.json", []):
        if (review.get("decision") == "distinct"
                and lookup.get(review["a"], {}).get("sha256") == review["a_sha256"]
                and lookup.get(review["b"], {}).get("sha256") == review["b_sha256"]):
            rejected.add(frozenset((review["a"], review["b"])))
    for pair in pairs:
        if frozenset((pair["a"], pair["b"])) in rejected:
            pair["decision"] = "visually_checked_distinct"
    pending_pairs = [p for p in pairs if p["decision"] != "visually_checked_distinct"]
    neighbors = defaultdict(set)
    for pair in pending_pairs:
        neighbors[pair["a"]].add(pair["b"])
        neighbors[pair["b"]].add(pair["a"])
    for item in assets:
        if item["source_type"] == "physical_photo":
            item["screening"] = "existing_local_photo"
            continue
        ident, h = item["id"], item["sha256"]
        score, reasons = priority({**manifest[ident], "bytes": item["bytes"],
                                   "width": item.get("width", 0), "height": item.get("height", 0)})
        item.update(priority=score, priority_reasons=reasons, near_duplicate_candidates=sorted(neighbors[ident]))
        if h in local_hashes: status = "exact_local_duplicate"
        elif h in reviews: status = "already_reviewed"
        elif h in pilot_hashes: status = "pilot_described"
        elif item.get("historical_hash_changed"): status = "version_review_needed"
        elif item["decode_state"] != "decoded": status = "format_or_size_review_needed"
        elif item.get("frames", 1) > 1: status = "animated_image_review_needed"
        elif score < 0: status = "low_priority_candidate"
        elif neighbors[ident]: status = "near_duplicate_review_needed"
        else: status = "ready_for_description"
        item["screening"] = status
    ready = sorted((a for a in assets if a["screening"] == "ready_for_description"),
                   key=lambda a: (-a["priority"], -a.get("width", 0)*a.get("height", 0), a["id"]))
    exact = defaultdict(list)
    for asset in assets:
        exact[asset["sha256"]].extend(asset.get("source_ids", [asset["id"]]))
    save(BULK / "screening.json", {"screened_at": now(), "assets": assets,
         "near_duplicate_candidates": pairs,
         "exact_duplicate_groups": [{"sha256": h, "source_ids": ids} for h, ids in exact.items() if len(ids)>1]})
    save(BULK / "description_queue.json", ready)
    similar_groups = candidate_groups(assets, pending_pairs)
    save(BULK / "similarity_groups.json", similar_groups)
    summary = {"completed_at": now(), "url_records": len(manifest),
               "unattempted_url_records": len(set(manifest) - set(state)),
               "download_status": dict(Counter(v["status"] for v in state.values())),
               "unique_downloaded_hashes": len(groups), "unique_downloaded_bytes": sum(a.get("bytes", 0) for a in assets),
               "local_photos_checked": sum(a["source_type"] == "physical_photo" for a in assets), "screening": dict(Counter(a["screening"] for a in assets)),
               "exact_duplicate_groups": sum(len(ids)>1 for ids in exact.values()),
               "raw_near_duplicate_candidates": len(pairs), "visually_rejected_pairs": len(pairs)-len(pending_pairs),
               "near_duplicate_pairs": len(pending_pairs), "cross_source_near_pairs": sum(p["cross_source"] for p in pending_pairs),
               "near_duplicate_candidate_groups": len(similar_groups),
               "new_descriptions_generated": 0, "database_modified": False}
    save(BULK / "summary.json", summary)
    lines = ["# 网站图片批量下载与筛选结果", "", "仅下载和本地筛选；未生成新描述，未修改数据库。", "",
             "```json", json.dumps(summary, ensure_ascii=False, indent=2), "```", "",
             "## 筛选分类", "", "| 类别 | 唯一图片数 |", "|---|---:|"]
    lines += [f"| {kind} | {count} |" for kind, count in sorted(summary["screening"].items())]
    lines += ["", "完全重复按实际文件哈希分组，保留所有来源。近似分组仅供核查，未删除原图。", "",
              "## 待描述队列前 30 张", "", "这里只是规则筛选结果，不代表已经核验图片内容。", "",
              "| 图片 ID | 优先级依据 | 原图 |", "|---|---|---|"]
    for item in ready[:30]:
        lines.append(f"| {item['id']} | {', '.join(item['priority_reasons'])} | [打开](../../../../{item['local_path']}) |")
    lines += ["", "## 未恢复的 URL", "", "| 图片 ID | 状态 | HTTP 状态 |", "|---|---|---|"]
    for ident, entry in sorted(state.items()):
        if entry["status"] != "recovered":
            lines.append(f"| {ident} | {entry['status']} | {entry.get('http_status', '')} |")
    lines += ["", "来源网址、文件路径和错误类型见 recovery.json；全部候选见 description_queue.json。",
              "原图被 Git 忽略，迁移 worktree 前需单独备份 recovered 目录。"]
    (BULK / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("plan", "download", "retry", "screen"))
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--retry-all", action="store_true", help="Explicitly include known permanent failures; external hosts remain excluded")
    parser.add_argument("--dry-run", action="store_true", help="Verify local files and write a plan without network requests")
    args = parser.parse_args()
    if args.dry_run and args.stage == "screen":
        parser.error("--dry-run is for download planning, not screening")
    with run_lock():
        if args.stage in ("plan", "download", "retry"):
            download(args.workers, retry_only=args.stage == "retry", retry_all=args.retry_all,
                     dry_run=args.dry_run or args.stage == "plan")
        else: screen()


if __name__ == "__main__":
    main()
