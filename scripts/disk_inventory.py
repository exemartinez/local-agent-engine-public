"""Read-only disk metadata inventory; never deletes or opens inventoried files."""
import heapq
import json
import os
from pathlib import Path
import shutil
import time
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parent.parent
DRIVE = Path("C:/")


def main():
    stamp = datetime.now().strftime("%Y_%m_%d__%H_%M_%S")
    report = ROOT / "documentation" / "archive" / "system-investigations" / (stamp + "__disk_inventory.md")
    report.parent.mkdir(parents=True, exist_ok=True)
    raw = ROOT / "benchmarks" / "results" / (stamp + "__disk_inventory.json")
    before = shutil.disk_usage(DRIVE)
    started = time.time()
    cutoff = started - 7 * 86400
    stack = [DRIVE]
    totals = {}
    recently_modified = {}
    largest = []
    recent_largest = []
    errors = []
    counters = {"files": 0, "directories": 0, "errors": 0, "reparse_points_skipped": 0, "hardlinks_deduplicated": 0}
    hardlinks_seen = set()

    def keep(heap, row, limit=60):
        heapq.heappush(heap, row)
        if len(heap) > limit:
            heapq.heappop(heap)

    while stack:
        folder = stack.pop()
        try:
            with os.scandir(folder) as entries:
                counters["directories"] += 1
                for entry in entries:
                    try:
                        info = entry.stat(follow_symlinks=False)
                        if info.st_file_attributes & 0x400:
                            counters["reparse_points_skipped"] += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        if info.st_nlink > 1 and info.st_ino:
                            key = (info.st_dev, info.st_ino)
                            if key in hardlinks_seen:
                                counters["hardlinks_deduplicated"] += 1
                                continue
                            hardlinks_seen.add(key)
                        counters["files"] += 1
                        path = Path(entry.path)
                        parts = path.relative_to(DRIVE).parts
                        for depth in range(1, min(4, len(parts) - 1) + 1):
                            label = str(DRIVE.joinpath(*parts[:depth]))
                            totals[label] = totals.get(label, 0) + info.st_size
                            if info.st_mtime >= cutoff:
                                recently_modified[label] = recently_modified.get(label, 0) + info.st_size
                        if info.st_size >= 512 * 1024 ** 2:
                            row = (info.st_size, str(path), datetime.fromtimestamp(info.st_mtime).isoformat(timespec="seconds"))
                            keep(largest, row)
                            if info.st_mtime >= cutoff:
                                keep(recent_largest, row)
                    except (OSError, AttributeError) as exc:
                        counters["errors"] += 1
                        if len(errors) < 20:
                            errors.append(f"{entry.path}: {exc}")
        except (OSError, PermissionError) as exc:
            counters["errors"] += 1
            if len(errors) < 20:
                errors.append(f"{folder}: {exc}")

    after = shutil.disk_usage(DRIVE)
    ranked = lambda d: sorted(d.items(), key=lambda x: x[1], reverse=True)[:50]
    data = {"started": datetime.fromtimestamp(started).isoformat(timespec="seconds"),
            "finished": datetime.now().isoformat(timespec="seconds"),
            "free_before_bytes": before.free, "free_after_bytes": after.free,
            "counts": counters, "errors_sample": errors,
            "largest_directory_prefixes": ranked(totals),
            "recently_modified_directory_prefixes": ranked(recently_modified),
            "largest_files": sorted(largest, reverse=True), "recent_largest_files": sorted(recent_largest, reverse=True)}
    raw.write_text(json.dumps(data, indent=2), encoding="utf-8")
    lines = ["# Read-only disk inventory", "", f"Started: {data['started']}; finished: {data['finished']}.",
             f"Free disk before: {before.free / 1e9:.2f} GB; after: {after.free / 1e9:.2f} GB.",
             f"Scanned {counters['files']} files and {counters['directories']} directories; {counters['errors']} access or metadata errors; {counters['reparse_points_skipped']} reparse points skipped.",
             "", "Sizes below are logical file sizes and may differ from allocated disk usage (sparse/compressed files, hardlinks, inaccessible system locations and ongoing downloads). Directory prefixes overlap; do not add them together.",
             "Recently modified means current file modification time, not proof the file was created or grew during the benchmark. No files were deleted.",
             "", "## Largest directory prefixes", "", "| Path | Logical GiB |", "| --- | ---: |"]
    lines += [f"| `{path}` | {size / 1024**3:.2f} |" for path, size in data["largest_directory_prefixes"]]
    lines += ["", "## Largest recently modified files", "", "| File | Logical GiB | Last modified |", "| --- | ---: | --- |"]
    lines += [f"| `{path}` | {size / 1024**3:.2f} | {modified} |" for size, path, modified in data["recent_largest_files"]]
    lines += ["", "Full inventory and access-error samples: `" + str(raw) + "`.",
              "", "Preserve all benchmark reports, logs, results and generated code. Do not delete personal files, games, mods, or system files. Review any cleanup candidate with the user before deletion."]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(report), "raw": str(raw), "counts": counters}), flush=True)


if __name__ == "__main__":
    main()
