import os
import threading
import time

_watched_folders = {}

def start_watching(user_id: str, folder_path: str):
    """Registers folder for background sync."""
    _watched_folders[user_id] = {
        "folder_path": folder_path,
        "started_at": time.time()
    }
