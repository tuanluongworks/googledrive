#!/usr/bin/env python3
"""Google Drive Sync - Console Application."""

import sys
import logging
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from config import Config
from drive_client import DriveClient
from sync_engine import SyncEngine

# Setup console
console = Console()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)

logger = logging.getLogger(__name__)


def print_banner():
    """Print application banner."""
    console.print(Panel.fit(
        "[bold cyan]Google Drive Sync[/bold cyan]\n"
        "[dim]Bidirectional sync between Google Drive and local folder[/dim]",
        border_style="cyan"
    ))


def print_config():
    """Print current configuration."""
    table = Table(title="Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="yellow")

    table.add_row("Local Folder", str(Config.LOCAL_SYNC_FOLDER))
    table.add_row("Drive Folder ID", Config.DRIVE_FOLDER_ID or "[root]")
    table.add_row("Sync Interval", f"{Config.SYNC_INTERVAL} seconds")
    table.add_row("Token File", str(Config.TOKEN_FILE))
    table.add_row("State File", str(Config.SYNC_STATE_FILE))

    console.print(table)


def setup_environment():
    """Setup and validate environment."""
    # Check if .env exists
    if not Path('.env').exists():
        console.print("[yellow]Warning: .env file not found[/yellow]")
        console.print("Please copy .env.example to .env and configure your settings")
        console.print("\nRequired settings:")
        console.print("  - GOOGLE_CLIENT_ID")
        console.print("  - GOOGLE_CLIENT_SECRET")
        console.print("  - LOCAL_SYNC_FOLDER")
        return False

    # Validate configuration
    if not Config.validate():
        console.print("[red]Error: Invalid configuration[/red]")
        console.print("Please check your .env file")
        return False

    # Ensure sync folder exists
    Config.LOCAL_SYNC_FOLDER.mkdir(parents=True, exist_ok=True)

    return True


def main():
    """Main entry point."""
    print_banner()

    # Setup environment
    if not setup_environment():
        sys.exit(1)

    print_config()

    console.print("\n[bold green]Initializing...[/bold green]")

    try:
        # Initialize Drive client
        drive_client = DriveClient()

        console.print("Authenticating with Google Drive...")
        if not drive_client.authenticate():
            console.print("[red]Authentication failed[/red]")
            sys.exit(1)

        console.print("[green]Authentication successful[/green]")

        # Initialize sync engine
        sync_engine = SyncEngine(drive_client)

        console.print("\n[bold cyan]Starting sync engine...[/bold cyan]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Start syncing
        sync_engine.start()

    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down gracefully...[/yellow]")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    console.print("[green]Sync stopped. Goodbye![/green]")


if __name__ == '__main__':
    main()
