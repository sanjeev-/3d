"""
File management utilities.
"""

import shutil
from pathlib import Path
from typing import List, Optional


class FileManager:
    """
    Utilities for managing files and directories in movie projects.
    """

    @staticmethod
    def ensure_directory(path: str) -> Path:
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path

        Returns:
            Path object for the directory
        """
        dir_path = Path(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path

    @staticmethod
    def clean_directory(path: str, pattern: str = "*") -> int:
        """
        Remove files matching a pattern from a directory.

        Args:
            path: Directory path
            pattern: Glob pattern for files to remove (default: all files)

        Returns:
            Number of files removed
        """
        dir_path = Path(path)
        if not dir_path.exists():
            return 0

        count = 0
        for file_path in dir_path.glob(pattern):
            if file_path.is_file():
                file_path.unlink()
                count += 1

        return count

    @staticmethod
    def copy_file(src: str, dst: str, overwrite: bool = False) -> bool:
        """
        Copy a file from source to destination.

        Args:
            src: Source file path
            dst: Destination file path
            overwrite: Whether to overwrite existing file

        Returns:
            True if copy was successful
        """
        src_path = Path(src)
        dst_path = Path(dst)

        if not src_path.exists():
            raise FileNotFoundError(f"Source file not found: {src_path}")

        if dst_path.exists() and not overwrite:
            return False

        # Ensure destination directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(src_path, dst_path)
        return True

    @staticmethod
    def find_files(directory: str, pattern: str = "*",
                  recursive: bool = False) -> List[Path]:
        """
        Find files matching a pattern in a directory.

        Args:
            directory: Directory to search
            pattern: Glob pattern to match
            recursive: Whether to search recursively

        Returns:
            List of matching file paths
        """
        dir_path = Path(directory)
        if not dir_path.exists():
            return []

        if recursive:
            files = list(dir_path.rglob(pattern))
        else:
            files = list(dir_path.glob(pattern))

        return [f for f in files if f.is_file()]

    @staticmethod
    def get_file_size(path: str, human_readable: bool = False) -> str:
        """
        Get the size of a file.

        Args:
            path: File path
            human_readable: Return size in human-readable format

        Returns:
            File size as string
        """
        file_path = Path(path)
        if not file_path.exists():
            return "0"

        size = file_path.stat().st_size

        if not human_readable:
            return str(size)

        # Convert to human-readable format
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0

        return f"{size:.2f} PB"

    @staticmethod
    def get_directory_size(path: str, human_readable: bool = False) -> str:
        """
        Get the total size of all files in a directory.

        Args:
            path: Directory path
            human_readable: Return size in human-readable format

        Returns:
            Total size as string
        """
        dir_path = Path(path)
        if not dir_path.exists():
            return "0"

        total_size = sum(f.stat().st_size for f in dir_path.rglob('*') if f.is_file())

        if not human_readable:
            return str(total_size)

        # Convert to human-readable format
        size = float(total_size)
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0

        return f"{size:.2f} PB"

    @staticmethod
    def create_gitkeep(directory: str):
        """
        Create a .gitkeep file in a directory.

        Args:
            directory: Directory path
        """
        dir_path = Path(directory)
        dir_path.mkdir(parents=True, exist_ok=True)
        (dir_path / '.gitkeep').touch()
