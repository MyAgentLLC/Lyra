"""
Filesystem operations module — read, write, search, and manage files.
"""

import os
import shutil
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class FilesystemControl:
    def __init__(self, allowed_roots: list = None, blocked_paths: list = None):
        self.allowed_roots = [os.path.expanduser(r) for r in (allowed_roots or [])]
        self.blocked_paths = [os.path.expanduser(p) for p in (blocked_paths or [])]

    def _check_path(self, path: str) -> bool:
        """Check if a path is allowed."""
        full_path = os.path.abspath(os.path.expanduser(path))
        
        # Check blocked paths
        for blocked in self.blocked_paths:
            if full_path.startswith(blocked):
                return False
        
        # Check allowed roots (if specified)
        if self.allowed_roots:
            for root in self.allowed_roots:
                if full_path.startswith(root):
                    return True
            return False
        
        return True

    def read_file(self, path: str, encoding: str = "utf-8") -> dict:
        """Read a text file."""
        if not self._check_path(path):
            return {"error": "Access denied: path is blocked or outside allowed roots"}
        
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            return {"status": "success", "path": path, "content": content[:50000],
                    "truncated": len(content) > 50000}
        except FileNotFoundError:
            return {"error": "File not found"}
        except PermissionError:
            return {"error": "Permission denied"}
        except Exception as e:
            return {"error": str(e)}

    def write_file(self, path: str, content: str, create_dirs: bool = True) -> dict:
        """Write content to a file."""
        if not self._check_path(path):
            return {"error": "Access denied: path is blocked or outside allowed roots"}
        
        try:
            if create_dirs:
                os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "path": path, "bytes": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def append_file(self, path: str, content: str) -> dict:
        """Append content to a file."""
        if not self._check_path(path):
            return {"error": "Access denied"}
        
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return {"status": "success", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def delete_file(self, path: str) -> dict:
        """Delete a file."""
        if not self._check_path(path):
            return {"error": "Access denied"}
        
        try:
            os.remove(path)
            return {"status": "success", "deleted": path}
        except FileNotFoundError:
            return {"error": "File not found"}
        except Exception as e:
            return {"error": str(e)}

    def create_directory(self, path: str) -> dict:
        """Create a directory."""
        if not self._check_path(path):
            return {"error": "Access denied"}
        
        try:
            os.makedirs(path, exist_ok=True)
            return {"status": "success", "path": path}
        except Exception as e:
            return {"error": str(e)}

    def list_directory(self, path: str = ".", recursive: bool = False, max_depth: int = 3) -> dict:
        """List directory contents."""
        if not self._check_path(path):
            return {"error": "Access denied"}
        
        try:
            entries = []
            if recursive:
                for root, dirs, files in os.walk(path):
                    depth = root.replace(path, "").count(os.sep)
                    if depth >= max_depth:
                        dirs.clear()
                        continue
                    for name in dirs + files:
                        entries.append({
                            "name": name,
                            "path": os.path.join(root, name),
                            "type": "directory" if os.path.isdir(os.path.join(root, name)) else "file",
                            "size": os.path.getsize(os.path.join(root, name))
                                    if os.path.isfile(os.path.join(root, name)) else None,
                        })
            else:
                for name in os.listdir(path):
                    full = os.path.join(path, name)
                    entries.append({
                        "name": name,
                        "path": full,
                        "type": "directory" if os.path.isdir(full) else "file",
                        "size": os.path.getsize(full) if os.path.isfile(full) else None,
                    })
            return {"status": "success", "path": path, "entries": entries}
        except Exception as e:
            return {"error": str(e)}

    def copy_file(self, src: str, dst: str) -> dict:
        """Copy a file."""
        if not self._check_path(src) or not self._check_path(dst):
            return {"error": "Access denied"}
        
        try:
            shutil.copy2(src, dst)
            return {"status": "success", "src": src, "dst": dst}
        except Exception as e:
            return {"error": str(e)}

    def move_file(self, src: str, dst: str) -> dict:
        """Move/rename a file."""
        if not self._check_path(src) or not self._check_path(dst):
            return {"error": "Access denied"}
        
        try:
            shutil.move(src, dst)
            return {"status": "success", "src": src, "dst": dst}
        except Exception as e:
            return {"error": str(e)}

    def search_files(self, directory: str, pattern: str = "*", content_pattern: str = None,
                     max_results: int = 100) -> dict:
        """Search for files by name pattern and optionally content."""
        if not self._check_path(directory):
            return {"error": "Access denied"}
        
        import fnmatch
        results = []
        try:
            for root, dirs, files in os.walk(directory):
                for name in files:
                    if fnmatch.fnmatch(name, pattern):
                        results.append(os.path.join(root, name))
                        if len(results) >= max_results:
                            return {"status": "success", "results": results, "truncated": True}
                
                if content_pattern:
                    for name in files:
                        full = os.path.join(root, name)
                        if content_pattern and name not in [r.split(os.sep)[-1] for r in results]:
                            try:
                                with open(full, "r", errors="ignore") as f:
                                    if content_pattern.lower() in f.read().lower():
                                        results.append(full)
                                        if len(results) >= max_results:
                                            return {"status": "success", "results": results, "truncated": True}
                            except:
                                continue
            
            return {"status": "success", "results": results, "count": len(results)}
        except Exception as e:
            return {"error": str(e)}

    def get_file_info(self, path: str) -> dict:
        """Get detailed file information."""
        if not self._check_path(path):
            return {"error": "Access denied"}
        
        try:
            stat = os.stat(path)
            return {
                "status": "success",
                "path": path,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "is_dir": os.path.isdir(path),
                "is_file": os.path.isfile(path),
                "permissions": oct(stat.st_mode)[-3:],
            }
        except Exception as e:
            return {"error": str(e)}
