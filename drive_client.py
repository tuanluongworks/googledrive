"""Google Drive API client implementation."""

import io
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from config import Config

logger = logging.getLogger(__name__)


class DriveClient:
    """Google Drive API client with file operations."""

    def __init__(self):
        """Initialize Drive client."""
        self.service = None
        self.creds = None

    def authenticate(self) -> bool:
        """Authenticate with Google Drive API."""
        try:
            # Load existing credentials
            if Config.TOKEN_FILE.exists():
                self.creds = Credentials.from_authorized_user_file(
                    str(Config.TOKEN_FILE), Config.SCOPES
                )

            # Refresh or create new credentials
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    logger.info("Refreshing access token...")
                    self.creds.refresh(Request())
                else:
                    logger.info("Starting OAuth flow...")
                    flow = InstalledAppFlow.from_client_config(
                        Config.get_client_config(), Config.SCOPES
                    )
                    self.creds = flow.run_local_server(port=8080)

                # Save credentials
                Config.TOKEN_FILE.write_text(self.creds.to_json())
                logger.info("Credentials saved")

            # Build service
            self.service = build('drive', 'v3', credentials=self.creds)
            logger.info("Successfully authenticated with Google Drive")
            return True

        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return False

    def list_files(
        self,
        folder_id: Optional[str] = None,
        page_size: int = 100
    ) -> List[Dict[str, Any]]:
        """List files in a folder."""
        try:
            query = []
            if folder_id:
                query.append(f"'{folder_id}' in parents")
            else:
                query.append("'root' in parents")

            query.append("trashed = false")
            query_string = " and ".join(query)

            results = self.service.files().list(
                q=query_string,
                pageSize=page_size,
                fields="nextPageToken, files(id, name, mimeType, modifiedTime, md5Checksum, size)"
            ).execute()

            return results.get('files', [])

        except HttpError as e:
            logger.error(f"Failed to list files: {e}")
            return []

    def get_file_metadata(self, file_id: str) -> Optional[Dict[str, Any]]:
        """Get file metadata."""
        try:
            file = self.service.files().get(
                fileId=file_id,
                fields="id, name, mimeType, modifiedTime, md5Checksum, size, parents"
            ).execute()
            return file
        except HttpError as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None

    def download_file(self, file_id: str, local_path: Path) -> bool:
        """Download a file from Google Drive."""
        try:
            request = self.service.files().get_media(fileId=file_id)

            local_path.parent.mkdir(parents=True, exist_ok=True)

            with io.FileIO(str(local_path), 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        logger.debug(f"Download {int(status.progress() * 100)}%")

            logger.info(f"Downloaded: {local_path.name}")
            return True

        except HttpError as e:
            logger.error(f"Failed to download file: {e}")
            return False

    def upload_file(
        self,
        local_path: Path,
        parent_id: Optional[str] = None,
        file_id: Optional[str] = None
    ) -> Optional[str]:
        """Upload or update a file to Google Drive."""
        try:
            file_metadata = {
                'name': local_path.name
            }

            if parent_id:
                file_metadata['parents'] = [parent_id]

            media = MediaFileUpload(
                str(local_path),
                resumable=True,
                chunksize=Config.CHUNK_SIZE
            )

            if file_id:
                # Update existing file
                file = self.service.files().update(
                    fileId=file_id,
                    media_body=media,
                    fields='id, name, modifiedTime'
                ).execute()
                logger.info(f"Updated: {local_path.name}")
            else:
                # Create new file
                file = self.service.files().create(
                    body=file_metadata,
                    media_body=media,
                    fields='id, name, modifiedTime'
                ).execute()
                logger.info(f"Uploaded: {local_path.name}")

            return file.get('id')

        except HttpError as e:
            logger.error(f"Failed to upload file: {e}")
            return None

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Create a folder in Google Drive."""
        try:
            file_metadata = {
                'name': name,
                'mimeType': 'application/vnd.google-apps.folder'
            }

            if parent_id:
                file_metadata['parents'] = [parent_id]

            file = self.service.files().create(
                body=file_metadata,
                fields='id, name'
            ).execute()

            logger.info(f"Created folder: {name}")
            return file.get('id')

        except HttpError as e:
            logger.error(f"Failed to create folder: {e}")
            return None

    def delete_file(self, file_id: str) -> bool:
        """Delete a file from Google Drive."""
        try:
            self.service.files().delete(fileId=file_id).execute()
            logger.info(f"Deleted file: {file_id}")
            return True
        except HttpError as e:
            logger.error(f"Failed to delete file: {e}")
            return False

    def search_file_by_name(
        self,
        name: str,
        parent_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Search for a file by name in a specific folder."""
        try:
            query = [f"name = '{name}'", "trashed = false"]

            if parent_id:
                query.append(f"'{parent_id}' in parents")

            query_string = " and ".join(query)

            results = self.service.files().list(
                q=query_string,
                pageSize=1,
                fields="files(id, name, mimeType, modifiedTime, md5Checksum, size)"
            ).execute()

            files = results.get('files', [])
            return files[0] if files else None

        except HttpError as e:
            logger.error(f"Failed to search file: {e}")
            return None
