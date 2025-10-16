"""Sync engine for bidirectional synchronization."""

import json
import logging
import hashlib
import time
from pathlib import Path
from typing import Dict, Optional, Set, Any
from datetime import datetime
from collections import defaultdict

from drive_client import DriveClient
from file_monitor import FileMonitor
from config import Config

logger = logging.getLogger(__name__)


class SyncState:
    """Manages synchronization state."""

    def __init__(self, state_file: Path):
        """Initialize sync state."""
        self.state_file = state_file
        self.state: Dict[str, Dict[str, Any]] = {}
        self.load()

    def load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
                logger.debug(f"Loaded {len(self.state)} tracked files")
            except Exception as e:
                logger.error(f"Failed to load sync state: {e}")
                self.state = {}
        else:
            self.state = {}

    def save(self):
        """Save state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
            logger.debug("Sync state saved")
        except Exception as e:
            logger.error(f"Failed to save sync state: {e}")

    def get_file_state(self, relative_path: str) -> Optional[Dict[str, Any]]:
        """Get state for a file."""
        return self.state.get(relative_path)

    def update_file_state(
        self,
        relative_path: str,
        drive_id: Optional[str] = None,
        local_mtime: Optional[float] = None,
        drive_mtime: Optional[str] = None,
        checksum: Optional[str] = None
    ):
        """Update state for a file."""
        if relative_path not in self.state:
            self.state[relative_path] = {}

        state = self.state[relative_path]

        if drive_id is not None:
            state['drive_id'] = drive_id
        if local_mtime is not None:
            state['local_mtime'] = local_mtime
        if drive_mtime is not None:
            state['drive_mtime'] = drive_mtime
        if checksum is not None:
            state['checksum'] = checksum

        self.save()

    def remove_file_state(self, relative_path: str):
        """Remove state for a file."""
        if relative_path in self.state:
            del self.state[relative_path]
            self.save()

    def get_all_tracked_files(self) -> Set[str]:
        """Get all tracked file paths."""
        return set(self.state.keys())


class SyncEngine:
    """Bidirectional sync engine."""

    def __init__(self, drive_client: DriveClient):
        """Initialize sync engine."""
        self.drive_client = drive_client
        self.sync_state = SyncState(Config.SYNC_STATE_FILE)
        self.local_folder = Config.LOCAL_SYNC_FOLDER
        self.drive_folder_id = Config.DRIVE_FOLDER_ID
        self.file_monitor: Optional[FileMonitor] = None
        self.pending_changes: Dict[str, Set[str]] = defaultdict(set)
        self.running = False

    def _get_relative_path(self, absolute_path: Path) -> str:
        """Get path relative to sync folder."""
        return str(absolute_path.relative_to(self.local_folder))

    def _get_absolute_path(self, relative_path: str) -> Path:
        """Get absolute path from relative path."""
        return self.local_folder / relative_path

    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate MD5 checksum of a file."""
        md5 = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5.update(chunk)
        return md5.hexdigest()

    def _on_local_change(self, event_type: str, file_path: str):
        """Handle local file change."""
        try:
            path = Path(file_path)
            relative_path = self._get_relative_path(path)

            logger.info(f"Local change detected: {event_type} - {relative_path}")

            # Add to pending changes
            self.pending_changes[event_type].add(relative_path)

        except Exception as e:
            logger.error(f"Error handling local change: {e}")

    def _sync_local_to_drive(self, relative_path: str, event_type: str):
        """Sync local file to Google Drive."""
        try:
            local_path = self._get_absolute_path(relative_path)
            state = self.sync_state.get_file_state(relative_path)

            if event_type == 'deleted':
                # Delete from Drive
                if state and state.get('drive_id'):
                    self.drive_client.delete_file(state['drive_id'])
                    self.sync_state.remove_file_state(relative_path)
                    logger.info(f"Deleted from Drive: {relative_path}")
                return

            if not local_path.exists():
                return

            # Upload or update file
            drive_id = state.get('drive_id') if state else None
            uploaded_id = self.drive_client.upload_file(
                local_path,
                parent_id=self.drive_folder_id,
                file_id=drive_id
            )

            if uploaded_id:
                # Update state
                local_mtime = local_path.stat().st_mtime
                checksum = self._calculate_checksum(local_path)

                # Get Drive metadata
                metadata = self.drive_client.get_file_metadata(uploaded_id)
                drive_mtime = metadata.get('modifiedTime') if metadata else None

                self.sync_state.update_file_state(
                    relative_path,
                    drive_id=uploaded_id,
                    local_mtime=local_mtime,
                    drive_mtime=drive_mtime,
                    checksum=checksum
                )

        except Exception as e:
            logger.error(f"Error syncing to Drive: {e}")

    def _sync_drive_to_local(self):
        """Sync files from Google Drive to local."""
        try:
            # Get all files from Drive
            drive_files = self.drive_client.list_files(self.drive_folder_id)

            drive_file_ids = set()

            for file in drive_files:
                drive_file_ids.add(file['id'])

                # Find local path for this file
                relative_path = file['name']  # Simplified: just use filename
                local_path = self._get_absolute_path(relative_path)
                state = self.sync_state.get_file_state(relative_path)

                # Check if we need to download
                should_download = False

                if not local_path.exists():
                    # File doesn't exist locally
                    should_download = True
                elif state and state.get('drive_mtime') != file.get('modifiedTime'):
                    # Drive file is newer
                    should_download = True

                if should_download:
                    if self.drive_client.download_file(file['id'], local_path):
                        # Update state
                        local_mtime = local_path.stat().st_mtime
                        checksum = self._calculate_checksum(local_path)

                        self.sync_state.update_file_state(
                            relative_path,
                            drive_id=file['id'],
                            local_mtime=local_mtime,
                            drive_mtime=file.get('modifiedTime'),
                            checksum=checksum
                        )

            # Check for deleted files on Drive
            tracked_files = self.sync_state.get_all_tracked_files()
            for relative_path in tracked_files:
                state = self.sync_state.get_file_state(relative_path)
                if state and state.get('drive_id') not in drive_file_ids:
                    # File was deleted on Drive
                    local_path = self._get_absolute_path(relative_path)
                    if local_path.exists():
                        local_path.unlink()
                        logger.info(f"Deleted locally (removed from Drive): {relative_path}")
                    self.sync_state.remove_file_state(relative_path)

        except Exception as e:
            logger.error(f"Error syncing from Drive: {e}")

    def _process_pending_changes(self):
        """Process pending local changes."""
        if not self.pending_changes:
            return

        logger.info(f"Processing {sum(len(v) for v in self.pending_changes.values())} pending changes")

        # Process deletes first
        for relative_path in self.pending_changes.pop('deleted', set()):
            self._sync_local_to_drive(relative_path, 'deleted')

        # Process creates and modifies
        for event_type in ['created', 'modified']:
            for relative_path in self.pending_changes.pop(event_type, set()):
                self._sync_local_to_drive(relative_path, event_type)

        self.pending_changes.clear()

    def initial_sync(self):
        """Perform initial sync on startup."""
        logger.info("Starting initial sync...")

        # Sync from Drive first
        self._sync_drive_to_local()

        # Then sync local files that might not be on Drive
        for file_path in self.local_folder.rglob('*'):
            if file_path.is_file() and not file_path.name.startswith('.'):
                relative_path = self._get_relative_path(file_path)
                state = self.sync_state.get_file_state(relative_path)

                if not state or not state.get('drive_id'):
                    # File not tracked, upload it
                    logger.info(f"Uploading new local file: {relative_path}")
                    self._sync_local_to_drive(relative_path, 'created')

        logger.info("Initial sync complete")

    def start(self):
        """Start sync engine."""
        logger.info("Starting sync engine...")

        # Perform initial sync
        self.initial_sync()

        # Start file monitor
        self.file_monitor = FileMonitor(self.local_folder, self._on_local_change)
        self.file_monitor.start()

        self.running = True
        logger.info("Sync engine started")

        # Main sync loop
        try:
            while self.running:
                # Process pending local changes
                self._process_pending_changes()

                # Sync from Drive
                self._sync_drive_to_local()

                # Wait before next sync
                time.sleep(Config.SYNC_INTERVAL)

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
        finally:
            self.stop()

    def stop(self):
        """Stop sync engine."""
        logger.info("Stopping sync engine...")
        self.running = False

        if self.file_monitor:
            self.file_monitor.stop()

        # Process any remaining changes
        self._process_pending_changes()

        logger.info("Sync engine stopped")
