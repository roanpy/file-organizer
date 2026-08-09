import argparse
import sys
from pathlib import Path

SELF_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(SELF_DIR / "src"))

from api_client import (  # noqa: E402
    scan_directory, analyze_software, analyze_duplicates,
    transfer, delete_files, scan_target_directories,
)
from config_manager import ensure_config, get_categories  # noqa: E402
from ai_helper import (  # noqa: E402
    build_decision_context,
    write_decision_file,
    read_decision_file,
    parse_decisions,
)


WORK_DIR = Path.home() / ".software_organizer-skill"
DECISIONS_FILE = WORK_DIR / "decisions.json"


def cmd_scan(args) -> None:
    config, _ = ensure_config()
    source_dir = config.get("source_dir", "")

    if not source_dir:
        print("ERROR: source_dir not set in config. Edit your config file.")
        sys.exit(1)

    data = scan_directory(source_dir)
    if "error" in data:
        print(f"ERROR: {data['error']}")
        sys.exit(1)

    software = data.get("software", [])
    counts = data.get("category_counts", {})

    print(f"\n{'=' * 60}")
    print("  Scan Results")
    print(f"{'=' * 60}")
    print(f"Source: {source_dir}")
    print(f"Total:  {len(software)}")
    for cat_id, info in counts.items():
        print(f"  {info['name']}: {info['count']}")

    print(f"\n{'─' * 60}")
    for item in software:
        name = item.get("filename", "")[:38]
        cat = item.get("category_name", "—")[:14]
        size = item.get("size_formatted", "?")[:9]
        print(f"{name:<38} {cat:<14} {size:<9}")

    unclassified = [s for s in software if not s.get("category")]
    if unclassified:
        print(f"\n⚠️  {len(unclassified)} unclassified")


def cmd_analyze(args) -> None:
    config, _ = ensure_config()
    categories = get_categories(config)
    source_dir = config.get("source_dir", "")
    target_dir = config.get("target_dir", "")

    if not source_dir:
        print("ERROR: source_dir not set in config.")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print("  Analyze")
    print(f"{'=' * 60}")

    # Scan source
    scan_data = scan_directory(source_dir)
    source_files = scan_data.get("software", [])

    # Analyze & classify
    result = analyze_software(source_files, config)
    groups = result.get("groups", [])

    source_only = [
        g for g in groups
        if any(f.get("location") == "source" for f in g.get("files", []))
    ]
    unclassified = [
        g for g in source_only if not any(f.get("category") for f in g.get("files", []))
    ]

    # Check duplicates in target if target_dir set
    dup_groups = []
    if target_dir:
        target_data = scan_target_directories(target_dir, categories)
        all_target_files = []
        for cat_id, cat_info in target_data.get("categories", {}).items():
            all_target_files.extend(cat_info.get("files", []))
        if all_target_files:
            combined = source_files + all_target_files
            dup_result = analyze_duplicates(combined)
            dup_groups = dup_result.get("groups", [])

    print(f"Unclassified: {len(unclassified)}")
    print(f"Duplicate groups: {len(dup_groups)}")

    if not unclassified and not dup_groups:
        print("\nAll files classified, no duplicates detected.")
        return

    WORK_DIR.mkdir(parents=True, exist_ok=True)

    context = build_decision_context(
        unclassified=[g.get("files", [{}])[0] for g in unclassified],
        duplicates=dup_groups,
        categories=categories,
        target_dir=target_dir,
    )

    write_decision_file(context, DECISIONS_FILE)

    print("\nDecision context written to:")
    print(f"  {DECISIONS_FILE}")
    print("\nTo let AI make decisions:")
    print("  1. Read the file")
    print("  2. For each item in 'decisions', fill in the 'decision' field")
    print("  3. Save the file")
    print("  4. Run: python SKILL_CLI.py execute")

    print(f"\n{'─' * 60}")
    print("Preview (first 3 items):")
    for item in context["decisions"][:3]:
        print(f"\n  [{item['type']}] {item.get('filename', item.get('software_name', ''))}")
        if item["type"] == "classify":
            print(f"    file_path: {item['file_path']}")
            print(f"    available categories: {list(item['available_categories'].keys())}")
        elif item["type"] == "dedup":
            for v in item["versions"]:
                print(f"    - {v['filename']} | {v['version']} | {v['file_path']}")


def cmd_execute(args) -> None:
    if not DECISIONS_FILE.exists():
        print("No decisions file found. Run 'analyze' first.")
        sys.exit(1)

    context = read_decision_file(DECISIONS_FILE)
    transfers, deletes = parse_decisions(context)

    print(f"\n{'=' * 60}")
    print("  Execute")
    print(f"{'=' * 60}")
    print(f"Transfers: {len(transfers)}")
    print(f"Deletions: {len(deletes)}")

    if not args.yes:
        for t in transfers:
            print(f"\n  [TRANSFER] {t['filename']}")
            print(f"    → {t['destination']}")
            print(f"    reason: {t['reason']}")
        for d in deletes:
            print(f"\n  [DELETE] {Path(d['file_path']).name}")
            print(f"    path: {d['file_path']}")
            print(f"    reason: {d['reason']}")
        print("\n⚠️  This cannot be undone! Proceed? (y/N): ", end="", flush=True)
        if input().strip().lower() != "y":
            print("Cancelled.")
            sys.exit(0)

    # Execute transfers
    transferred_ok, transferred_fail = 0, []
    grouped = {}
    for t in transfers:
        grouped.setdefault(t["destination"], []).append(t["file_path"])

    for dest, files in grouped.items():
        r = transfer(files, dest)
        transferred_ok += len(r.get("success", []))
        transferred_fail += [f["path"] for f in r.get("failed", [])]

    # Delete only after all transfers complete successfully.
    deleted_ok, deleted_fail = 0, []
    if deletes and not transferred_fail:
        paths = [d["file_path"] for d in deletes]
        r = delete_files(paths)
        deleted_ok = len(r.get("success", []))
        deleted_fail = [f["path"] for f in r.get("failed", [])]
    elif deletes:
        deleted_fail = [d["file_path"] for d in deletes]
        print("Deletion skipped because one or more transfers failed.")

    print(f"\n{'=' * 60}")
    print("  Results")
    print(f"{'=' * 60}")
    print(f"Deleted:    {deleted_ok}/{len(deletes)}")
    print(f"Transferred: {transferred_ok}/{len(transfers)}")
    if deleted_fail:
        print(f"Delete failed: {deleted_fail}")
    if transferred_fail:
        print(f"Transfer failed: {transferred_fail}")

    if args.yes and (deleted_ok or transferred_ok):
        DECISIONS_FILE.unlink(missing_ok=True)


def cmd_status(args) -> None:
    config, config_path = ensure_config()
    categories = get_categories(config)

    print(f"\n{'=' * 60}")
    print("  Status")
    print(f"{'=' * 60}")
    print("Mode:   local (no backend)")
    print(f"Config: {config_path}")
    print(f"Source: {config.get('source_dir', 'not set')}")
    print(f"Target: {config.get('target_dir', 'not set')}")
    print(f"Categories ({len(categories)}):")
    for cat_id, info in categories.items():
        print(f"  {cat_id}: {info.get('name', '')}  formats={info.get('formats', [])}")
    print(f"\nDecision file: {DECISIONS_FILE}")
    print(f"Exists: {DECISIONS_FILE.exists()}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="FileOrganizer CLI — local mode (no backend required)"
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Scan source directory for software files")
    sub.add_parser("analyze", help="Classify files and detect duplicates")
    p_execute = sub.add_parser("execute", help="Execute pending transfer/delete decisions")
    p_execute.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    sub.add_parser("status", help="Show current configuration")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    {
        "scan": cmd_scan,
        "analyze": cmd_analyze,
        "execute": cmd_execute,
        "status": cmd_status,
    }[args.command](args)


if __name__ == "__main__":
    main()
