# -*- coding: utf-8 -*-
"""
Transfer Module - Handles moving and deletion of software packages.

Contains:
- Software move operations
- Software deletion operations
- Transfer logging
"""

import os
import shutil
import tempfile
from typing import Any, Dict, Optional

from .config import save_history_item


def move_software(
    source_path: str,
    destination_dir: str,
    new_filename: Optional[str] = None,
    overwrite: bool = False,
) -> Dict[str, Any]:
    """
    Move a software package to the target directory.

    Args:
        source_path: Path to the source file.
        destination_dir: Target destination directory.
        new_filename: Optional new filename (defaults to original).
        overwrite: Whether to overwrite existing files.

    Returns:
        Operation results dictionary.
    """
    if not os.path.isfile(source_path):
        return {"success": False, "error": f"Source file does not exist: {source_path}"}

    if not os.path.isdir(destination_dir):
        try:
            os.makedirs(destination_dir)
        except OSError as e:
            return {
                "success": False,
                "error": f"Could not create target directory: {e}",
            }

    filename = new_filename or os.path.basename(source_path)
    dest_path = os.path.join(destination_dir, filename)

    if os.path.exists(dest_path) and os.path.samefile(source_path, dest_path):
        return {
            "success": True,
            "source": source_path,
            "destination": dest_path,
            "unchanged": True,
        }

    # Check if target file already exists
    if os.path.exists(dest_path):
        if not overwrite:
            return {
                "success": False,
                "code": "target_exists",
                "error": f"Target file already exists: {dest_path}",
            }
        if not os.path.isfile(dest_path):
            return {
                "success": False,
                "error": f"Target path is not a file: {dest_path}",
            }

    temp_path = None
    try:
        if overwrite and os.path.exists(dest_path):
            fd, temp_path = tempfile.mkstemp(prefix=".file-organizer-", dir=destination_dir)
            os.close(fd)
            shutil.copy2(source_path, temp_path)
            os.replace(temp_path, dest_path)
            temp_path = None
            os.remove(source_path)
        else:
            shutil.move(source_path, dest_path)

        # Log transfer history (JSON)
        save_history_item(
            filename, "transferred", {"source": source_path, "destination": dest_path}
        )

        return {"success": True, "source": source_path, "destination": dest_path}
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def delete_software(file_path: str) -> Dict[str, Any]:
    """
    Delete a software package.

    Args:
        file_path: Path to the file.

    Returns:
        Operation results dictionary.
    """
    if not os.path.exists(file_path):
        return {"success": False, "error": f"File does not exist: {file_path}"}

    try:
        filename = os.path.basename(file_path)
        os.remove(file_path)

        # Log deletion history (JSON - legacy compatibility)
        save_history_item(filename, "deleted", {"path": file_path})

        return {"success": True, "deleted": file_path}
    except Exception as e:
        return {"success": False, "error": str(e)}


def batch_move(
    file_paths: list, destination_dir: str, overwrite: bool = False
) -> Dict[str, Any]:
    """
    Move software packages in a batch.

    Args:
        file_paths: List of source file paths.
        destination_dir: Target destination directory.
        overwrite: Whether to overwrite existing files.

    Returns:
        Operation results summary.
    """
    results = {"success": [], "failed": []}

    for path in file_paths:
        result = move_software(path, destination_dir, overwrite=overwrite)
        if result["success"]:
            results["success"].append(result)
        else:
            results["failed"].append(
                {
                    "path": path,
                    "code": result.get("code", "unknown_error"),
                    "error": result.get("error", "Unknown error"),
                }
            )

    return results


def batch_delete(file_paths: list) -> Dict[str, Any]:
    """
    Delete software packages in a batch.

    Args:
        file_paths: List of file paths to delete.

    Returns:
        Operation results summary.
    """
    results = {"success": [], "failed": []}

    for path in file_paths:
        result = delete_software(path)
        if result["success"]:
            results["success"].append(result)
        else:
            results["failed"].append(
                {"path": path, "error": result.get("error", "Unknown error")}
            )

    return results
