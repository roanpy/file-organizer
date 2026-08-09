"""
AI Helper - formats structured context for AI agent decisions.

The calling AI agent will read this context, use its own AI to make decisions,
and return a JSON decisions file that Python will execute.
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def build_decision_context(
    unclassified: List[Dict],
    duplicates: List[Dict],
    categories: Dict[str, Any],
    target_dir: str,
) -> Dict[str, Any]:
    """
    Build a structured decision context that AI agent will reason over.
    AI agent reads this, makes decisions, and writes them to a JSON file.
    Python then executes the decisions.
    """
    decisions = []

    for item in unclassified:
        decisions.append(
            {
                "type": "classify",
                "filename": item.get("filename", ""),
                "file_path": item.get("path", ""),
                "size": item.get("size_formatted", ""),
                "current_category": item.get("category", ""),
                "available_categories": {
                    cat_id: {
                        "name": info.get("name", cat_id),
                        "formats": info.get("formats", []),
                        "target_dir": info.get("target_dir", ""),
                    }
                    for cat_id, info in categories.items()
                },
                "decision": {
                    "action": "",  # "transfer" or "skip"
                    "target_category": "",  # category_id
                    "target_dir": "",  # absolute path
                    "reason": "",
                },
            }
        )

    for group in duplicates:
        decisions.append(
            {
                "type": "dedup",
                "software_name": group.get("software_name", ""),
                "versions": [
                    {
                        "filename": f.get("filename", ""),
                        "file_path": f.get("path", ""),
                        "version": f.get("version", ""),
                        "size": f.get("size_formatted", ""),
                        "is_kept": f.get("is_kept", False),
                    }
                    for f in group.get("files", [])
                ],
                "decision": {
                    "keep_file_path": "",  # which one to keep
                    "delete_file_paths": [],  # which ones to delete
                    "reason": "",
                },
            }
        )

    return {
        "target_dir": target_dir,
        "decisions": decisions,
        "meta": {
            "unclassified_count": len(unclassified),
            "duplicate_groups_count": len(duplicates),
        },
    }


def write_decision_file(context: Dict[str, Any], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(context, f, ensure_ascii=False, indent=2)


def read_decision_file(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_decisions(context: Dict[str, Any]) -> tuple[List[Dict], List[Dict]]:
    """
    Parse filled decision context into executable actions.
    Returns (transfer_actions, delete_actions).
    """
    transfers = []
    deletes = []

    for item in context.get("decisions", []):
        d = item.get("decision", {})

        if item["type"] == "classify":
            action = d.get("action", "")
            if action == "transfer" and d.get("target_dir"):
                transfers.append(
                    {
                        "file_path": item["file_path"],
                        "filename": item["filename"],
                        "destination": d["target_dir"],
                        "reason": d.get("reason", ""),
                    }
                )

        elif item["type"] == "dedup":
            if d.get("delete_file_paths"):
                for fp in d["delete_file_paths"]:
                    deletes.append(
                        {
                            "file_path": fp,
                            "reason": d.get("reason", ""),
                        }
                    )

    return transfers, deletes
