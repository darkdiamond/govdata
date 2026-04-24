"""
CLI entry point for the Scanner Service.

Provides a command-line interface to scan datasets from data.gov.il,
detect changes, and download resources.
"""

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.panel import Panel

from .client import CKANClient
from .config import ScannerSettings, settings
from .detector import ChangeDetector
from .downloader import ResourceDownloader, SkippedFormatError, InvalidContentError
from .filters import DatasetFilter, create_filter
from .models import Dataset, DatasetStatus, Resource, ScanResult, ScanSummary
from .state import StateDB

# Initialize CLI app
app = typer.Typer(
    name="scanner",
    help="Scan datasets from data.gov.il CKAN API",
    add_completion=False,
)

console = Console()


class ScanCallbacks:
    """
    Callback handlers for scan events.
    
    Override these methods to integrate with downstream services
    like page generation and analysis.
    """
    
    async def on_new_dataset(
        self, 
        dataset: Dataset, 
        resources: list[Resource],
        downloaded_paths: dict[str, Path],
    ) -> None:
        """Called when a new dataset is discovered and downloaded."""
        console.print(
            f"  [bold green]→ NEW[/bold green] Trigger new page flow for: {dataset.title}"
        )
    
    async def on_updated_dataset(
        self, 
        dataset: Dataset, 
        resources: list[Resource],
        downloaded_paths: dict[str, Path],
    ) -> None:
        """Called when an existing dataset has been updated."""
        console.print(
            f"  [bold yellow]→ UPDATED[/bold yellow] Trigger update flow for: {dataset.title}"
        )
    
    async def on_unchanged_dataset(self, dataset: Dataset) -> None:
        """Called when dataset hasn't changed (optional)."""
        pass


class HttpWebhookCallbacks(ScanCallbacks):
    """Forwards NEW/UPDATED dataset events to the page-builder Cloud Function."""

    def __init__(self, webhook_url: str, timeout: float = 15.0) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    async def _post(self, dataset: Dataset) -> None:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                r = await client.post(
                    self.webhook_url,
                    json={"dataset_id": dataset.id},
                )
                r.raise_for_status()
            console.print(f"  [cyan]→ webhook posted for {dataset.id[:8]}…[/cyan]")
        except Exception as e:
            console.print(f"  [red]→ webhook failed: {e}[/red]")

    async def on_new_dataset(
        self,
        dataset: Dataset,
        resources: list[Resource],
        downloaded_paths: dict[str, Path],
    ) -> None:
        await super().on_new_dataset(dataset, resources, downloaded_paths)
        await self._post(dataset)

    async def on_updated_dataset(
        self,
        dataset: Dataset,
        resources: list[Resource],
        downloaded_paths: dict[str, Path],
    ) -> None:
        await super().on_updated_dataset(dataset, resources, downloaded_paths)
        await self._post(dataset)


class Scanner:
    """Main scanner orchestrator."""
    
    def __init__(
        self,
        config: Optional[ScannerSettings] = None,
        callbacks: Optional[ScanCallbacks] = None,
    ):
        """
        Initialize the scanner.
        
        Args:
            config: Scanner settings.
            callbacks: Event callbacks for downstream integration.
        """
        self.config = config or settings
        self.callbacks = callbacks or ScanCallbacks()
        self.config.ensure_directories()
        self.db = StateDB(self.config.db_path)
    
    async def scan(
        self,
        limit: int = 5,
        filter_config: Optional[DatasetFilter] = None,
        download: bool = True,
        force: bool = False,
    ) -> ScanSummary:
        """
        Run the scanner.
        
        Args:
            limit: Maximum number of datasets to process.
            filter_config: Optional filter configuration.
            download: Whether to download resources.
            force: Re-process even if unchanged.
        
        Returns:
            ScanSummary with results.
        """
        summary = ScanSummary(started_at=datetime.now(timezone.utc))
        scan_id = self.db.start_scan()
        
        detector = ChangeDetector(self.db)
        
        console.print(Panel.fit(
            f"[bold]GovData Scanner[/bold]\n"
            f"Limit: {limit} datasets\n"
            f"Download: {'Yes' if download else 'No'}\n"
            f"Force: {'Yes' if force else 'No'}\n"
            f"Filters: {filter_config.describe() if filter_config else 'None'}",
            title="Configuration",
        ))
        
        async with CKANClient(self.config) as client:
            # Get total count for context
            total_available = await client.get_package_count()
            console.print(f"\n[dim]Total datasets available: {total_available}[/dim]\n")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                
                fetch_task = progress.add_task(
                    "[cyan]Fetching datasets...", 
                    total=limit
                )
                
                datasets_processed = 0
                
                async for dataset in client.iter_all_packages(limit=limit * 3):
                    # Skip excluded datasets
                    if dataset.id in self.config.EXCLUDED_DATASET_IDS:
                        continue
                    
                    # Apply filters
                    if filter_config and not filter_config.matches(dataset):
                        continue
                    
                    datasets_processed += 1
                    progress.update(fetch_task, completed=datasets_processed)
                    
                    # Detect status
                    status = detector.detect_status(dataset, force=force)
                    
                    result = ScanResult(
                        dataset=dataset,
                        status=status,
                    )
                    
                    # Status display
                    status_style = {
                        DatasetStatus.NEW: "[bold green]NEW[/bold green]",
                        DatasetStatus.UPDATED: "[bold yellow]UPDATED[/bold yellow]",
                        DatasetStatus.UNCHANGED: "[dim]UNCHANGED[/dim]",
                    }
                    
                    console.print(
                        f"\n{status_style[status]} {dataset.title[:60]}..."
                        if len(dataset.title) > 60 
                        else f"\n{status_style[status]} {dataset.title}"
                    )
                    console.print(f"  [dim]ID: {dataset.id}[/dim]")
                    console.print(f"  [dim]Resources: {len(dataset.resources)}[/dim]")
                    
                    # Update counts
                    summary.datasets_scanned += 1
                    if status == DatasetStatus.NEW:
                        summary.datasets_new += 1
                    elif status == DatasetStatus.UPDATED:
                        summary.datasets_updated += 1
                    else:
                        summary.datasets_unchanged += 1
                    
                    # Process based on status
                    downloaded_paths = {}
                    
                    if status in (DatasetStatus.NEW, DatasetStatus.UPDATED):
                        resources_to_download = []
                        
                        # Always save dataset first for state tracking
                        self.db.save_dataset(dataset)
                        for resource in dataset.resources:
                            self.db.save_resource(dataset.id, resource)
                        
                        if download:
                            # Get resources to download
                            resources_to_download = detector.get_resources_to_download(
                                dataset, status, force=force
                            )
                            
                            # Apply format filter if active
                            if filter_config and resources_to_download:
                                resources_to_download = filter_config.filter_resources(dataset)
                            
                            if resources_to_download:
                                # Filter out excluded formats
                                excluded_formats = set(self.config.EXCLUDED_FORMATS)
                                filtered_resources = [
                                    r for r in resources_to_download
                                    if r.format.upper() not in excluded_formats
                                ]
                                skipped_count = len(resources_to_download) - len(filtered_resources)
                                
                                if skipped_count > 0:
                                    console.print(
                                        f"  [dim]Skipping {skipped_count} excluded format(s) "
                                        f"(PDF, DOC, etc.)[/dim]"
                                    )
                                
                                if filtered_resources:
                                    console.print(
                                        f"  [cyan]Downloading {len(filtered_resources)} resource(s)...[/cyan]"
                                    )
                                    
                                    async with ResourceDownloader(self.config, self.db) as downloader:
                                        downloaded_paths = await downloader.download_resources(
                                            filtered_resources,
                                            dataset.id,
                                            on_resource_complete=lambda r, p: console.print(
                                                f"    ✓ {r.name} ({r.format})"
                                            ),
                                            on_resource_error=lambda r, e: (
                                                console.print(
                                                    f"    ⚠ {r.name}: Invalid content (bot protection page)", 
                                                    style="yellow"
                                                ) if isinstance(e, InvalidContentError)
                                                else console.print(
                                                    f"    ✗ {r.name}: {e}", style="red"
                                                )
                                            ),
                                        )
                                    
                                    result.resources_downloaded = len(downloaded_paths)
                        
                        # Trigger callbacks
                        if status == DatasetStatus.NEW:
                            await self.callbacks.on_new_dataset(
                                dataset, 
                                resources_to_download,
                                downloaded_paths,
                            )
                        else:
                            await self.callbacks.on_updated_dataset(
                                dataset,
                                resources_to_download, 
                                downloaded_paths,
                            )
                    
                    elif status == DatasetStatus.UNCHANGED:
                        await self.callbacks.on_unchanged_dataset(dataset)
                    
                    summary.results.append(result)
                    
                    # Check limit
                    if datasets_processed >= limit:
                        break
        
        # Complete scan
        summary.completed_at = datetime.now(timezone.utc)
        
        self.db.complete_scan(
            scan_id,
            summary.datasets_scanned,
            summary.datasets_new,
            summary.datasets_updated,
            summary.datasets_unchanged,
            summary.errors,
        )
        
        return summary


def print_summary(summary: ScanSummary) -> None:
    """Print a formatted scan summary."""
    table = Table(title="Scan Summary")
    
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    
    table.add_row("Datasets Scanned", str(summary.datasets_scanned))
    table.add_row("New Datasets", f"[green]{summary.datasets_new}[/green]")
    table.add_row("Updated Datasets", f"[yellow]{summary.datasets_updated}[/yellow]")
    table.add_row("Unchanged Datasets", f"[dim]{summary.datasets_unchanged}[/dim]")
    
    if summary.errors:
        table.add_row("Errors", f"[red]{len(summary.errors)}[/red]")
    
    duration = (
        (summary.completed_at - summary.started_at).total_seconds()
        if summary.completed_at else 0
    )
    table.add_row("Duration", f"{duration:.1f}s")
    
    console.print("\n")
    console.print(table)


@app.command()
def scan(
    limit: int = typer.Option(
        5, "--limit", "-l",
        help="Maximum number of datasets to process",
    ),
    format: Optional[str] = typer.Option(
        None, "--format", "-f",
        help="Filter by resource format (comma-separated, e.g., csv,json)",
    ),
    name_contains: Optional[str] = typer.Option(
        None, "--name-contains", "-n",
        help="Filter datasets by name/title containing this string",
    ),
    name_regex: Optional[str] = typer.Option(
        None, "--name-regex",
        help="Filter datasets by regex pattern",
    ),
    org: Optional[str] = typer.Option(
        None, "--org", "-o",
        help="Filter by organization name",
    ),
    tags: Optional[str] = typer.Option(
        None, "--tags", "-t",
        help="Filter by tags (comma-separated)",
    ),
    download: bool = typer.Option(
        True, "--download/--no-download", "-d",
        help="Download resources for new/updated datasets",
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Force re-process even if unchanged",
    ),
    db_path: Optional[str] = typer.Option(
        None, "--db-path",
        help="Custom database path",
    ),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir",
        help="Custom output directory for downloads",
    ),
    webhook_url: Optional[str] = typer.Option(
        None, "--webhook-url",
        help="Page-builder webhook URL (overrides PAGE_BUILDER_URL env var)",
    ),
) -> None:
    """
    Scan datasets from data.gov.il CKAN API.
    
    Detects new and updated datasets, downloads resources,
    and triggers appropriate downstream actions.
    """
    # Configure settings
    config = ScannerSettings()
    
    if db_path:
        config.db_path = Path(db_path)
    
    if output_dir:
        config.downloads_dir = Path(output_dir)
    
    # Create filter
    filter_config = None
    if any([format, name_contains, name_regex, org, tags]):
        filter_config = create_filter(
            name_contains=name_contains,
            name_regex=name_regex,
            formats=format,
            organization=org,
            tags=tags,
        )
    
    # Callbacks: webhook if URL available, otherwise default (console-logging)
    hook = webhook_url or config.page_builder_url
    callbacks: ScanCallbacks = HttpWebhookCallbacks(hook) if hook else ScanCallbacks()

    # Run scanner
    scanner = Scanner(config=config, callbacks=callbacks)
    summary = asyncio.run(
        scanner.scan(
            limit=limit,
            filter_config=filter_config,
            download=download,
            force=force,
        )
    )
    
    # Print summary
    print_summary(summary)


@app.command()
def stats() -> None:
    """Show database statistics."""
    config = ScannerSettings()
    db = StateDB(config.db_path)
    
    stats = db.get_stats()
    
    table = Table(title="Database Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Count", justify="right")
    
    table.add_row("Total Datasets", str(stats["datasets_count"]))
    table.add_row("Total Resources", str(stats["resources_count"]))
    table.add_row("Completed Downloads", str(stats["completed_downloads"]))
    
    console.print(table)


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-l", help="Number of records to show"),
) -> None:
    """Show scan history."""
    config = ScannerSettings()
    db = StateDB(config.db_path)
    
    records = db.get_scan_history(limit=limit)
    
    if not records:
        console.print("[dim]No scan history found[/dim]")
        return
    
    table = Table(title="Scan History")
    table.add_column("ID", style="dim")
    table.add_column("Started")
    table.add_column("Scanned", justify="right")
    table.add_column("New", justify="right", style="green")
    table.add_column("Updated", justify="right", style="yellow")
    table.add_column("Unchanged", justify="right", style="dim")
    
    for record in records:
        table.add_row(
            str(record["id"]),
            record["started_at"][:19] if record["started_at"] else "-",
            str(record["datasets_scanned"] or 0),
            str(record["datasets_new"] or 0),
            str(record["datasets_updated"] or 0),
            str(record["datasets_unchanged"] or 0),
        )
    
    console.print(table)


@app.command()
def reset() -> None:
    """Reset the database (delete all tracking data)."""
    confirm = typer.confirm("Are you sure you want to reset the database?")
    
    if confirm:
        config = ScannerSettings()
        if config.db_path.exists():
            config.db_path.unlink()
            console.print("[green]Database reset successfully[/green]")
        else:
            console.print("[dim]No database found[/dim]")


def main() -> None:
    """Main entry point."""
    app()


if __name__ == "__main__":
    main()

