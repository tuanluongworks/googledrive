"""Local file system monitoring using watchdog."""

import logging
from pathlib import Path
from typing import Callable, Set
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

logger = logging.getLogger(__name__)


class FileChangeHandler(FileSystemEventHandler):
    """Handler for file system events."""

    def __init__(self, on_change: Callable[[str, str], None], base_path: Path):
        """
        Initialize handler.

        Args:
            on_change: Callback function(event_type, file_path)
            base_path: Base path to monitor
        """
        super().__init__()
        self.on_change = on_change
        self.base_path = base_path
        self._ignored_events: Set[str] = set()

    def _should_ignore(self, src_path: str) -> bool:
        """Check if path should be ignored."""
        path = Path(src_path)

        # Ignore hidden files and system files
        if path.name.startswith('.'):
            return True

        # Ignore temporary files
        if path.name.endswith(('.tmp', '.swp', '~')):
            return True

        # Ignore sync state files
        if '.sync_state' in path.name:
            return True

        return False

    def on_created(self, event: FileSystemEvent):
        """Handle file creation."""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        logger.debug(f"File created: {event.src_path}")
        self.on_change('created', event.src_path)

    def on_modified(self, event: FileSystemEvent):
        """Handle file modification."""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        logger.debug(f"File modified: {event.src_path}")
        self.on_change('modified', event.src_path)

    def on_deleted(self, event: FileSystemEvent):
        """Handle file deletion."""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        logger.debug(f"File deleted: {event.src_path}")
        self.on_change('deleted', event.src_path)

    def on_moved(self, event: FileSystemEvent):
        """Handle file move/rename."""
        if event.is_directory or self._should_ignore(event.src_path):
            return

        logger.debug(f"File moved: {event.src_path} -> {event.dest_path}")
        self.on_change('deleted', event.src_path)
        self.on_change('created', event.dest_path)


class FileMonitor:
    """Monitor local file system for changes."""

    def __init__(self, watch_path: Path, on_change: Callable[[str, str], None]):
        """
        Initialize file monitor.

        Args:
            watch_path: Path to monitor
            on_change: Callback function(event_type, file_path)
        """
        self.watch_path = watch_path
        self.on_change = on_change
        self.observer = Observer()
        self.handler = FileChangeHandler(on_change, watch_path)

    def start(self):
        """Start monitoring."""
        logger.info(f"Starting file monitor on: {self.watch_path}")
        self.observer.schedule(self.handler, str(self.watch_path), recursive=True)
        self.observer.start()

    def stop(self):
        """Stop monitoring."""
        logger.info("Stopping file monitor")
        self.observer.stop()
        self.observer.join()

    def is_alive(self) -> bool:
        """Check if monitor is running."""
        return self.observer.is_alive()
