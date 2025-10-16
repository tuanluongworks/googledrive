# Google Drive Sync

A console application for bidirectional synchronization between Google Drive and a local folder.

## Architecture

### Design Philosophy

This application follows a **design-first approach** with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│              Main Application                    │
│              (main.py)                          │
└───────────┬─────────────────────────────────────┘
            │
            ├──► DriveClient (drive_client.py)
            │    └─► Google Drive API operations
            │
            ├──► FileMonitor (file_monitor.py)
            │    └─► Local file system watching
            │
            └──► SyncEngine (sync_engine.py)
                 ├─► SyncState management
                 ├─► Conflict resolution
                 └─► Bidirectional sync coordination
```

### Key Components

1. **DriveClient**: Encapsulates all Google Drive API interactions
   - Authentication & OAuth flow
   - File upload/download operations
   - Metadata management
   - File search and listing

2. **FileMonitor**: Monitors local file system changes
   - Uses watchdog library for efficient event watching
   - Filters system and temporary files
   - Provides callbacks for file events

3. **SyncEngine**: Orchestrates bidirectional synchronization
   - Manages sync state persistence
   - Handles conflict resolution (timestamp-based)
   - Coordinates local-to-Drive and Drive-to-local sync
   - Processes changes in batches

4. **SyncState**: Persistent state management
   - Tracks file metadata (checksums, timestamps, Drive IDs)
   - Enables intelligent sync decisions
   - JSON-based storage

## Features

- Bidirectional sync between Google Drive and local folder
- Real-time monitoring of local file changes
- Periodic polling of Google Drive changes
- Conflict resolution based on modification timestamps
- MD5 checksum verification
- Automatic OAuth2 authentication
- Rich console output with progress indicators
- Configurable sync intervals

## Prerequisites

- Python 3.8+
- Google Cloud Project with Drive API enabled
- OAuth 2.0 credentials

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable Google Drive API:
   - Navigate to "APIs & Services" > "Library"
   - Search for "Google Drive API"
   - Click "Enable"

4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Choose "Desktop app" as application type
   - Download the credentials

5. Note your Client ID and Client Secret

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set:

```bash
GOOGLE_CLIENT_ID=your_client_id_here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret_here
GOOGLE_REDIRECT_URI=http://localhost:8080/

# Local folder to sync
LOCAL_SYNC_FOLDER=/path/to/your/sync/folder

# Optional: specific Drive folder ID (leave empty for root)
DRIVE_FOLDER_ID=
```

### 4. First Run - Authentication

```bash
python main.py
```

On first run:
1. Browser will open for Google authentication
2. Grant permissions to the application
3. Token will be saved to `token.json`
4. Future runs will use the saved token

## Usage

### Start Sync

```bash
python main.py
```

Or use the executable:

```bash
./main.py
```

### Stop Sync

Press `Ctrl+C` to gracefully stop the sync engine.

## Configuration

Edit `config.py` or `.env` to customize:

- `SYNC_INTERVAL`: Seconds between Drive sync checks (default: 30)
- `MAX_RETRIES`: Maximum retry attempts for failed operations
- `CHUNK_SIZE`: Upload chunk size in bytes (default: 256KB)

## How It Works

### Initial Sync
1. Downloads all files from Google Drive to local folder
2. Uploads any local files not present on Drive
3. Establishes baseline sync state

### Continuous Sync

**Local to Drive:**
- File monitor detects local changes in real-time
- Changes are queued and processed periodically
- Files are uploaded/updated/deleted on Drive

**Drive to Local:**
- Periodically polls Google Drive for changes
- Compares modification timestamps
- Downloads new/updated files
- Removes files deleted on Drive

### Conflict Resolution

When both local and Drive versions change:
- Timestamp-based resolution (newer wins)
- Original file is not backed up (future enhancement)

## File Structure

```
googledrive/
├── main.py              # Entry point
├── config.py            # Configuration management
├── drive_client.py      # Google Drive API client
├── file_monitor.py      # Local file system monitor
├── sync_engine.py       # Sync orchestration
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
├── .gitignore          # Git ignore rules
└── README.md           # This file

Generated at runtime:
├── .env                # Your configuration (git-ignored)
├── token.json          # OAuth token (git-ignored)
├── .sync_state.json    # Sync state (git-ignored)
└── sync_folder/        # Your synced files (configurable)
```

## Limitations

- Currently syncs only files in a single folder (not recursive subdirectories)
- No conflict backup mechanism (uses last-write-wins)
- Google Drive folder structure is flattened to filenames only
- No support for Google Workspace files (Docs, Sheets, etc.)

## Future Enhancements

1. Recursive folder sync with hierarchy preservation
2. Conflict backup and manual resolution UI
3. Selective sync (include/exclude patterns)
4. Bandwidth throttling
5. Google Workspace file export
6. Change notifications via Drive API push notifications
7. Multi-folder sync support
8. Dry-run mode

## Security Notes

- Never commit `.env`, `token.json`, or `credentials.json` to version control
- Credentials are stored locally only
- OAuth tokens are refreshed automatically
- Application requests minimal Drive API scopes

## Troubleshooting

### Authentication Fails
- Check Client ID and Secret in `.env`
- Ensure redirect URI matches Google Cloud Console settings
- Delete `token.json` and re-authenticate

### Files Not Syncing
- Check log output for errors
- Verify Drive API quota limits
- Ensure local folder permissions are correct

### High CPU Usage
- Increase `SYNC_INTERVAL` in config
- Reduce number of files being monitored

## License

MIT License - feel free to modify and distribute.

## Contributing

Contributions welcome! Please ensure:
- Code follows existing architecture patterns
- Changes are accompanied by design rationale
- Error handling is comprehensive
- Logging is informative
