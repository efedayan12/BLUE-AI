"""
BLUE_AI CLI — Rich + Typer komut satırı arayüzü.

Tüm BLUE_AI işlevlerini komut satırından yönetir.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

import os
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

console = Console(force_terminal=True)
cli_app = typer.Typer(
    name="blue",
    help="BLUE_AI -- Bilgisayar Yonetim Yapay Zekasi",
    no_args_is_help=True,
)

# Engine singleton
_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from blue_ai.core.engine import BlueAIEngine
        _engine = BlueAIEngine()
    return _engine


def _run_async(coro):
    """Async fonksiyonu çalıştır."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return loop.run_until_complete(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


# =================== STATUS ===================


@cli_app.command()
def status():
    """Genel sistem durumunu goster."""
    import psutil
    from blue_ai.utils.helpers import bytes_to_human, seconds_to_human
    from blue_ai.utils.win_api import get_system_power_status
    import time

    console.print()
    console.print(Panel.fit(
        "[bold cyan]BLUE_AI -- Sistem Durumu[/bold cyan]",
        border_style="cyan",
    ))

    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_freq = psutil.cpu_freq()
    cpu_count = psutil.cpu_count()

    # RAM
    ram = psutil.virtual_memory()

    # Disk
    disk = psutil.disk_usage("C:\\")

    # Network
    net = psutil.net_io_counters()

    # Boot time
    boot_time = time.time() - psutil.boot_time()

    # Power
    power = get_system_power_status()

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Bilesen", style="bold")
    table.add_column("Durum", justify="right")
    table.add_column("Detay", style="dim")

    # CPU bar
    cpu_bar = _make_bar(cpu_percent)
    table.add_row("[CPU]", f"{cpu_bar} {cpu_percent:.1f}%", f"{cpu_count} core, {cpu_freq.current:.0f} MHz" if cpu_freq else "")

    # RAM bar
    ram_bar = _make_bar(ram.percent)
    table.add_row("[RAM]", f"{ram_bar} {ram.percent:.1f}%", f"{bytes_to_human(ram.used)} / {bytes_to_human(ram.total)}")

    # Disk bar
    disk_bar = _make_bar(disk.percent)
    table.add_row("[DISK]", f"{disk_bar} {disk.percent:.1f}%", f"{bytes_to_human(disk.used)} / {bytes_to_human(disk.total)}")

    # Network
    table.add_row("[NET]", f"UP:{bytes_to_human(net.bytes_sent)} DN:{bytes_to_human(net.bytes_recv)}", "")

    # Power
    if power.get("has_battery"):
        bat = power["battery_percent"]
        bat_bar = _make_bar(bat) if bat >= 0 else "N/A"
        ac = "[+] Charging" if power["ac_plugged"] else "[-] Battery"
        table.add_row("[BAT]", f"{bat_bar} {bat}%", ac)

    # Uptime
    table.add_row("[TIME]", seconds_to_human(boot_time), "")

    console.print(table)
    console.print()


def _make_bar(percent: float, width: int = 20) -> str:
    """Yüzde değerini görsel çubuğa çevir."""
    filled = int(width * percent / 100)
    empty = width - filled

    if percent >= 90:
        color = "red"
    elif percent >= 70:
        color = "yellow"
    else:
        color = "green"

    return f"[{color}]{'#' * filled}{'.' * empty}[/{color}]"


# =================== PROCESSES ===================


@cli_app.command()
def processes(
    top: int = typer.Option(15, help="Gösterilecek süreç sayısı"),
    sort: str = typer.Option("cpu", help="Sıralama: cpu veya ram"),
):
    """Calisan surecleri listele."""
    import psutil
    from blue_ai.utils.helpers import bytes_to_human

    table = Table(
        title="BLUE_AI Calisan Surecler",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("PID", style="dim", justify="right")
    table.add_column("Name", style="bold")
    table.add_column("CPU %", justify="right")
    table.add_column("RAM", justify="right")
    table.add_column("Status", style="dim")

    procs = []
    for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
        try:
            info = proc.info
            mem = info.get("memory_info")
            procs.append({
                "pid": info["pid"],
                "name": info["name"] or "Unknown",
                "cpu": info.get("cpu_percent", 0) or 0,
                "ram": mem.rss if mem else 0,
                "status": info.get("status", ""),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if sort == "ram":
        procs.sort(key=lambda p: p["ram"], reverse=True)
    else:
        procs.sort(key=lambda p: p["cpu"], reverse=True)

    for p in procs[:top]:
        cpu_str = f"{p['cpu']:.1f}%"
        if p["cpu"] > 50:
            cpu_str = f"[red]{cpu_str}[/red]"
        elif p["cpu"] > 20:
            cpu_str = f"[yellow]{cpu_str}[/yellow]"

        table.add_row(
            str(p["pid"]),
            p["name"][:30],
            cpu_str,
            bytes_to_human(p["ram"]),
            p["status"],
        )

    console.print(table)


# =================== CLEAN ===================


@cli_app.command()
def clean(
    full: bool = typer.Option(False, help="Tam temizlik (tarayıcı cache + WU cache)"),
):
    """Disk temizligi yap."""
    from blue_ai.core.event_bus import EventBus
    from blue_ai.plugins.cleaner import CleanerPlugin
    from blue_ai.core.config import load_config

    config = load_config()
    bus = EventBus()
    cleaner = CleanerPlugin(bus, config)

    console.print("[bold cyan]BLUE_AI Disk Temizligi[/bold cyan]")
    console.print()

    with console.status("[bold green]Temizlik yapiliyor..."):
        if full:
            result = _run_async(cleaner.full_cleanup())
        else:
            result = _run_async(cleaner.clean_temp_files())

    if full:
        table = Table(box=box.ROUNDED, show_header=True, header_style="bold green")
        table.add_column("Temizlik Türü", style="bold")
        table.add_column("Temizlenen", justify="right")

        if "temp_files" in result:
            table.add_row("Temp Dosyalar", result["temp_files"]["total_human"])
        if "browser_cache" in result:
            table.add_row("Tarayıcı Cache", result["browser_cache"]["total_human"])
        if "windows_update" in result:
            table.add_row("Windows Update", result["windows_update"]["total_human"])

        table.add_row("[bold]TOPLAM[/bold]", f"[bold green]{result['total_human']}[/bold green]")
        console.print(table)
    else:
        console.print(f"✅ Temizlendi: [bold green]{result['total_human']}[/bold green] ({result['files_deleted']} dosya)")


# =================== OPTIMIZE ===================


@cli_app.command()
def optimize():
    """Sistem optimizasyonu yap."""
    from blue_ai.core.event_bus import EventBus
    from blue_ai.plugins.performance import PerformancePlugin
    from blue_ai.core.config import load_config

    config = load_config()
    bus = EventBus()
    perf = PerformancePlugin(bus, config)

    console.print("[bold cyan]BLUE_AI Optimizasyon[/bold cyan]")

    with console.status("[bold green]Optimizasyon yapiliyor..."):
        result = _run_async(perf.optimize_now())

    console.print(f"[OK] RAM temizlendi: [bold green]{result['ram_processes_cleaned']}[/bold green] surec optimize edildi")


# =================== NETWORK ===================


@cli_app.command()
def network():
    """Ag durumunu goster."""
    from blue_ai.core.event_bus import EventBus
    from blue_ai.plugins.network import NetworkPlugin
    from blue_ai.core.config import load_config

    config = load_config()
    bus = EventBus()
    net = NetworkPlugin(bus, config)

    console.print("[bold cyan]BLUE_AI Ag Durumu[/bold cyan]")

    with console.status("[bold green]Ag taraniyor..."):
        _run_async(net.on_start())
        diagnosis = _run_async(net.diagnose())

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("Metrik", style="bold")
    table.add_column("Deger", justify="right")

    table.add_row("Internet", "[green][OK] Bagli[/green]" if diagnosis["internet_connected"] else "[red][X] Bagli Degil[/red]")
    table.add_row("Toplam Baglanti", str(diagnosis["total_connections"]))

    for target, ms in diagnosis["ping"].items():
        color = "green" if ms < 50 else "yellow" if ms < 100 else "red"
        table.add_row(f"Ping -> {target}", f"[{color}]{ms:.0f}ms[/{color}]" if ms > 0 else "[red]Timeout[/red]")

    console.print(table)

    if diagnosis["top_processes"]:
        proc_table = Table(title="Top Connection Processes", box=box.SIMPLE)
        proc_table.add_column("Process")
        proc_table.add_column("Connections", justify="right")

        for p in diagnosis["top_processes"][:5]:
            proc_table.add_row(p["process"], str(p["connection_count"]))

        console.print(proc_table)


# =================== SECURITY ===================


@cli_app.command()
def security():
    """Guvenlik taramasi yap."""
    from blue_ai.core.event_bus import EventBus
    from blue_ai.plugins.security import SecurityPlugin
    from blue_ai.core.config import load_config

    config = load_config()
    bus = EventBus()
    sec = SecurityPlugin(bus, config)

    console.print("[bold cyan]BLUE_AI Guvenlik Taramasi[/bold cyan]")

    with console.status("[bold green]Tarama yapiliyor..."):
        _run_async(sec.on_start())

    ports = sec.get_open_ports()

    table = Table(title="Open Ports", box=box.ROUNDED, show_header=True, header_style="bold yellow")
    table.add_column("Port", justify="right")
    table.add_column("Address")
    table.add_column("Process")
    table.add_column("PID", justify="right")

    for p in ports:
        table.add_row(str(p["port"]), p["address"], p["process"], str(p["pid"]))

    console.print(table)
    console.print(f"\nTotal open ports: [bold]{len(ports)}[/bold]")


# =================== STARTUP ===================


@cli_app.command()
def startup():
    """Baslangic uygulamalarini listele."""
    from blue_ai.core.event_bus import EventBus
    from blue_ai.plugins.startup import StartupPlugin
    from blue_ai.core.config import load_config

    config = load_config()
    bus = EventBus()
    start = StartupPlugin(bus, config)

    with console.status("[bold green]Baslangic uygulamalari taraniyor..."):
        _run_async(start.on_start())

    items = start.get_startup_items()
    boot = start.get_boot_time()

    console.print(Panel.fit(
        f"[bold cyan]Baslangic Yonetimi[/bold cyan]\n"
        f"Boot Time: [bold]{boot['boot_time_human']}[/bold] | "
        f"Startup Apps: [bold]{len(items)}[/bold]",
        border_style="cyan",
    ))

    table = Table(box=box.ROUNDED, show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Uygulama", style="bold")
    table.add_column("Kaynak", style="dim")

    for i, item in enumerate(items, 1):
        table.add_row(str(i), item["name"][:40], item["source"])

    console.print(table)

    # Optimizasyon önerileri
    suggestions = start.get_optimization_suggestions()
    if suggestions:
        console.print(f"\n[yellow][!] {len(suggestions)} optimization suggestions:[/yellow]")
        for s in suggestions:
            console.print(f"  [dim]-[/dim] [yellow]{s['name']}[/yellow] -- {s['reason']}")


# =================== SOFTWARE ===================


@cli_app.command()
def software(
    query: Optional[str] = typer.Argument(None, help="Arama sorgusu"),
):
    """Yuklu yazilimlari listele."""
    from blue_ai.core.event_bus import EventBus
    from blue_ai.plugins.updater import UpdaterPlugin
    from blue_ai.core.config import load_config

    config = load_config()
    bus = EventBus()
    updater = UpdaterPlugin(bus, config)

    with console.status("[bold green]Yazilimlar taraniyor..."):
        _run_async(updater.on_start())

    if query:
        items = updater.search_software(query)
        console.print(f"[cyan]Search: '{query}' -- {len(items)} results[/cyan]")
    else:
        items = updater.get_installed_software()

    table = Table(
        title=f"Installed Software ({len(items)})",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Software", style="bold")
    table.add_column("Version")
    table.add_column("Publisher", style="dim")

    for item in items[:50]:
        table.add_row(item["name"][:50], item["version"][:15], item["publisher"][:30])

    console.print(table)


# =================== PROFILE ===================


@cli_app.command()
def profile(
    name: str = typer.Argument(..., help="Profil: balanced, gaming, work, power_saver"),
):
    """Sistem profilini degistir."""
    from blue_ai.core.config import get_profile
    from blue_ai.utils.win_api import set_power_scheme

    valid_profiles = {"balanced", "gaming", "work", "power_saver"}
    if name not in valid_profiles:
        console.print(f"[red]Invalid profile![/red] Options: {', '.join(valid_profiles)}")
        raise typer.Exit(1)

    p = get_profile(name)
    power_plan = p.get("power_plan", "balanced")
    set_power_scheme(power_plan)

    console.print(f"[OK] Profile changed: [bold cyan]{p.get('name', name)}[/bold cyan]")
    console.print(f"   Power plan: {power_plan}")


# =================== RULES ===================


@cli_app.command()
def rules():
    """Aktif kurallari listele."""
    from blue_ai.core.rule_engine import RuleEngine

    engine = RuleEngine()
    rules_path = Path(__file__).parent.parent / "rules" / "default_rules.toml"
    if rules_path.exists():
        engine.load_rules_from_toml(rules_path)

    all_rules = engine.get_rules()

    table = Table(
        title="Automation Rules",
        box=box.ROUNDED,
        show_header=True,
        header_style="bold cyan",
    )
    table.add_column("Rule", style="bold")
    table.add_column("Condition")
    table.add_column("Action", style="green")
    table.add_column("Priority", justify="center")
    table.add_column("Cooldown", justify="right", style="dim")

    priority_colors = {"critical": "red", "high": "yellow", "normal": "green", "low": "dim"}

    for r in all_rules:
        color = priority_colors.get(r.priority, "white")
        table.add_row(
            r.name,
            r.condition[:35],
            r.action,
            f"[{color}]{r.priority}[/{color}]",
            f"{r.cooldown:.0f}s",
        )

    console.print(table)


# =================== RUN ===================


@cli_app.command()
def run():
    """BLUE_AI motorunu baslat (arka plan modu)."""
    from blue_ai.core.engine import BlueAIEngine

    engine = BlueAIEngine()

    try:
        asyncio.run(engine.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]BLUE_AI durduruluyor...[/yellow]")
        asyncio.run(engine.stop())
        console.print("[green]BLUE_AI durduruldu.[/green]")


# =================== DASHBOARD ===================


@cli_app.command()
def dashboard(
    host: str = typer.Option("127.0.0.1", help="Sunucu adresi"),
    port: int = typer.Option(8484, help="Port numarası"),
):
    """Web Dashboard'u baslat."""
    import uvicorn
    from blue_ai.dashboard.server import create_app

    console.print(f"[bold cyan]BLUE_AI Dashboard starting -> http://{host}:{port}[/bold cyan]")
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="warning")


# =================== MAIN ===================


def main():
    cli_app()


if __name__ == "__main__":
    main()
