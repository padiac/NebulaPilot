import typer
from rich.console import Console
from rich.table import Table
from .db import init_db, get_targets, get_target_progress
from .scanner import scan_directory

app = typer.Typer(help="nebulaPilot CLI - Astrophotography exposure tracking.")
console = Console()

@app.command()
def scan(directory: str = typer.Argument(..., help="Directory to scan for FITS files")):
    """Scan a directory and update the database."""
    init_db()
    console.print(f"Scanning directory: [bold blue]{directory}[/bold blue]...")
    scan_directory(directory)
    console.print("[bold green]Scan complete![/bold green]")

@app.command()
def status():
    """Show the current progress of all targets."""
    init_db()
    targets = get_targets()
    
    table = Table(title="nebulaPilot - Target Progress")
    table.add_column("Target", style="cyan")
    table.add_column("L (min)", justify="right")
    table.add_column("R (min)", justify="right")
    table.add_column("G (min)", justify="right")
    table.add_column("B (min)", justify="right")
    table.add_column("Status", style="magenta")
    
    for target in targets:
        name = target["name"]
        goals = (target["goal_l"], target["goal_r"], target["goal_g"], target["goal_b"])
        progress = get_target_progress(name)
        
        table.add_row(
            name,
            f"{progress['L']:.1f}/{goals[0]:.1f}",
            f"{progress['R']:.1f}/{goals[1]:.1f}",
            f"{progress['G']:.1f}/{goals[2]:.1f}",
            f"{progress['B']:.1f}/{goals[3]:.1f}",
            target["status"]
        )
    
    console.print(table)

def main():
    app()

if __name__ == "__main__":
    main()
