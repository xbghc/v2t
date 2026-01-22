"""存储抽象层"""

from app.storage.file_storage import FileStorage
from app.storage.local_file import LocalFileStorage

__all__ = ["FileStorage", "LocalFileStorage"]
