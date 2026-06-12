#!/usr/bin/env python3
"""
Project Health Monitor
Files · Git · MongoDB · PostgreSQL
bike_store / mongo_to_postgres

Usage:
  python health_check.py              # run from project root
  python health_check.py /path/to/project
"""

import os
import sys
import json
import subprocess
import importlib.util
from datetime import datetime, timezone
from pathlib import Path

# ──────────────────────────────────────────────────────────────────
# Auto-install missing packages
# ──────────────────────────────────────────────────────────────────
def ensure_packages():
    mapping = {
        "rich":           "rich",
        "python-dotenv":  "dotenv",
        "pymongo":        "pymongo",
        "psycopg2-binary":"psycopg2",
        "gitpython":      "git",
    }
    missing = [pkg for pkg, mod in mapping.items()
               if importlib.util.find_spec(mod) is None]
    if missing:
        print(f"Installing: {', '.join(missing)} ...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", *missing, "-q",
             "--break-system-packages"],
            check=True,
        )

ensure_packages()

# ──────────────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────────────
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

console = Console()

# ──────────────────────────────────────────────────────────────────
# PROJECT-SPECIFIC FILE MANIFEST
#    Tuned to: driver/ logs/ notebooks/ scripts/ sql/ utils/
# ──────────────────────────────────────────────────────────────────

# Root-level critical files
ROOT_FILES = [
    ".env",
    ".gitignore",
    ".python-version",
    "main.py",
    "pyproject.toml",
    "README.md",
    "uv.lock",
]

# Per-directory files  {display_label: relative_path}
MODULE_FILES = {
    # driver
    "driver/postgresql.jar":          "driver/postgresql.jar",
    # scripts
    "scripts/__init__.py":            "scripts/__init__.py",
    "scripts/mongo_to_postgres.py":   "scripts/mongo_to_postgres.py",
    # utils
    "utils/__init__.py":              "utils/__init__.py",
    "utils/connection.py":            "utils/connection.py",
    "utils/engine.py":                "utils/engine.py",
    "utils/logger.py":                "utils/logger.py",
    "utils/README.md":                "utils/README.md",
}

# Directories that must exist
REQUIRED_DIRS = [
    "driver",
    "logs",
    "logs/extraction",
    "notebooks",
    "scripts",
    "sql",
    "utils",
    ".venv",
]

LAST_RUN_FILE = ".health_last_run"

# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────
def fmt_bytes(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"

def save_last_run(root: Path):
    now = datetime.now(timezone.utc)
    data = {
        "last_run": now.isoformat(),
        "last_run_human": now.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "project": str(root),
        "run_count": _increment_run_count(root),
    }
    (root / LAST_RUN_FILE).write_text(json.dumps(data, indent=2))

def _increment_run_count(root: Path) -> int:
    p = root / LAST_RUN_FILE
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return int(data.get("run_count", 0)) + 1
        except (json.JSONDecodeError, ValueError):
            pass
    return 1

def get_last_run(root: Path) -> str:
    p = root / LAST_RUN_FILE
    if p.exists():
        try:
            data = json.loads(p.read_text())
            return data.get("last_run_human", "Unknown")
        except (json.JSONDecodeError, KeyError):
            # fallback: old plain-text format
            try:
                dt = datetime.fromisoformat(p.read_text().strip())
                return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
            except ValueError:
                pass
    return "Never"

def get_run_count(root: Path) -> int:
    p = root / LAST_RUN_FILE
    if p.exists():
        try:
            return int(json.loads(p.read_text()).get("run_count", 0))
        except (json.JSONDecodeError, ValueError):
            pass
    return 0

# ──────────────────────────────────────────────────────────────────
# 1. FILE & DIRECTORY HEALTH
# ──────────────────────────────────────────────────────────────────
def check_files(root: Path):
    console.print(Rule("[bold magenta]File & Directory Health[/bold magenta]"))

    # ── Directories ──────────────────────────────────────────────
    dir_tbl = Table(
        title="Required Directories",
        box=box.SIMPLE_HEAD, header_style="bold magenta", show_lines=False,
    )
    dir_tbl.add_column("Directory", style="white", no_wrap=True)
    dir_tbl.add_column("Status", justify="center")
    dir_tbl.add_column("Contents", justify="right", style="dim")

    for dname in REQUIRED_DIRS:
        dpath = root / dname
        if dpath.exists() and dpath.is_dir():
            items = len(list(dpath.iterdir()))
            dir_tbl.add_row(dname + "/", "[green]✓ Exists[/green]", f"{items} items")
        else:
            dir_tbl.add_row(dname + "/", "[red]✗ Missing[/red]", "—")

    console.print(dir_tbl)
    console.print()

    # ── Root files ───────────────────────────────────────────────
    root_tbl = Table(
        title="Root Files",
        box=box.ROUNDED, header_style="bold cyan", show_lines=False,
    )
    root_tbl.add_column("File", style="white", no_wrap=True)
    root_tbl.add_column("Status", justify="center")
    root_tbl.add_column("Size", justify="right", style="dim")
    root_tbl.add_column("Last Modified", style="dim")

    found = missing = 0
    for fname in ROOT_FILES:
        fpath = root / fname
        if fpath.exists():
            stat = fpath.stat()
            root_tbl.add_row(
                fname,
                "[green]✓ Found[/green]",
                fmt_bytes(stat.st_size),
                datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            )
            found += 1
        else:
            root_tbl.add_row(fname, "[red]✗ Missing[/red]", "—", "—")
            missing += 1

    console.print(root_tbl)
    console.print(f"  [green]✓ {found} present[/green]   [red]✗ {missing} missing[/red]")
    console.print()

    # ── Module files ─────────────────────────────────────────────
    mod_tbl = Table(
        title="Module / Script Files",
        box=box.ROUNDED, header_style="bold cyan", show_lines=False,
    )
    mod_tbl.add_column("File", style="white", no_wrap=True)
    mod_tbl.add_column("Status", justify="center")
    mod_tbl.add_column("Size", justify="right", style="dim")
    mod_tbl.add_column("Last Modified", style="dim")

    found2 = missing2 = 0
    for label, rel in MODULE_FILES.items():
        fpath = root / rel
        if fpath.exists():
            stat = fpath.stat()
            mod_tbl.add_row(
                label,
                "[green]✓ Found[/green]",
                fmt_bytes(stat.st_size),
                datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            )
            found2 += 1
        else:
            mod_tbl.add_row(label, "[red]✗ Missing[/red]", "—", "—")
            missing2 += 1

    console.print(mod_tbl)
    console.print(f"  [green]✓ {found2} present[/green]   [red]✗ {missing2} missing[/red]\n")


# ──────────────────────────────────────────────────────────────────
# 2. GIT HEALTH
# ──────────────────────────────────────────────────────────────────
def check_git(root: Path):
    console.print(Rule("[bold yellow]Git Health[/bold yellow]"))

    try:
        import git as gitlib

        repo     = gitlib.Repo(root, search_parent_directories=True)
        branch   = repo.active_branch.name
        dirty    = repo.is_dirty(untracked_files=True)
        untracked= len(repo.untracked_files)
        total    = sum(1 for _ in repo.iter_commits())
        recent   = list(repo.iter_commits(max_count=5))

        console.print(Panel(
            f"[bold]Branch:[/bold]              [cyan]{branch}[/cyan]\n"
            f"[bold]Total Commits:[/bold]       {total}\n"
            f"[bold]Working Tree:[/bold]        {'[red]Dirty  (uncommitted changes)[/red]' if dirty else '[green]Clean ✓[/green]'}\n"
            f"[bold]Untracked Files:[/bold]     {untracked}",
            title="Git Summary", border_style="yellow", expand=False,
        ))

        tbl = Table(
            title="Recent Commits (last 5)",
            box=box.SIMPLE_HEAD, header_style="bold yellow",
        )
        tbl.add_column("Hash",    style="dim",  no_wrap=True)
        tbl.add_column("Author",  style="cyan", no_wrap=True)
        tbl.add_column("Date",    style="dim",  no_wrap=True)
        tbl.add_column("Message", style="white")

        for c in recent:
            tbl.add_row(
                c.hexsha[:7],
                c.author.name[:22],
                datetime.fromtimestamp(c.committed_date).strftime("%Y-%m-%d %H:%M"),
                c.message.strip().splitlines()[0][:65],
            )
        console.print(tbl)
        console.print()

    except Exception as exc:
        console.print(f"[red]  ✗ Git check failed: {exc}[/red]\n")


# ──────────────────────────────────────────────────────────────────
# 3. PYSPARK CONFIG CHECK
# ──────────────────────────────────────────────────────────────────
def check_pyspark(root: Path):
    console.print(Rule("[bold bright_yellow]PySpark Config[/bold bright_yellow]"))

    py_path    = os.getenv("PYSPARK_PYTHON", "")
    driver_py  = os.getenv("PYSPARK_DRIVER_PYTHON", "")
    jar_path   = root / "driver" / "postgresql.jar"

    rows = [
        ("PYSPARK_PYTHON",        py_path),
        ("PYSPARK_DRIVER_PYTHON", driver_py),
    ]

    tbl = Table(box=box.SIMPLE_HEAD, header_style="bold bright_yellow", show_header=True)
    tbl.add_column("Key",    style="white",  no_wrap=True)
    tbl.add_column("Value",  style="dim",    no_wrap=True)
    tbl.add_column("Exists", justify="center")

    for key, val in rows:
        if not val:
            tbl.add_row(key, "[dim]not set[/dim]", "[yellow]?[/yellow]")
            continue
        # Normalise Windows backslashes to the current OS
        resolved = root / Path(val.replace("\\", os.sep))
        exists   = resolved.exists()
        tbl.add_row(
            key,
            val,
            "[green]✓[/green]" if exists else "[red]✗ path not found[/red]",
        )

    # PostgreSQL JDBC driver
    tbl.add_row(
        "driver/postgresql.jar",
        str(jar_path.relative_to(root)),
        "[green]✓[/green]" if jar_path.exists() else "[red]✗ Missing[/red]",
    )

    console.print(tbl)
    console.print()


# ──────────────────────────────────────────────────────────────────
# 4. MONGODB HEALTH
#    Reads:  MONGO_URI  +  MONGO_DB  (your exact .env keys)
# ──────────────────────────────────────────────────────────────────
def check_mongodb():
    console.print(Rule("[bold green]MongoDB Health[/bold green]"))

    uri     = os.getenv("MONGO_URI") or os.getenv("MONGODB_URI")
    db_name = os.getenv("MONGO_DB")  or os.getenv("MONGODB_DB")

    if not uri:
        console.print("[red]  ✗ MONGO_URI not set in .env — skipping.[/red]\n")
        return

    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.server_info()
        console.print(f"[green]  ✓ Connection OK  {uri}[/green]")

        if not db_name:
            db_name = uri.rstrip("/").split("/")[-1].split("?")[0] or "test"

        db    = client[db_name]
        stats = db.command("dbstats")

        console.print(Panel(
            f"[bold]Database:[/bold]     [cyan]{db_name}[/cyan]\n"
            f"[bold]Data Size:[/bold]    {fmt_bytes(int(stats.get('dataSize',    0)))}\n"
            f"[bold]Storage Size:[/bold] {fmt_bytes(int(stats.get('storageSize', 0)))}\n"
            f"[bold]Collections:[/bold]  {stats.get('collections', 0)}\n"
            f"[bold]Indexes:[/bold]      {stats.get('indexes', 0)}",
            title="MongoDB  ·  bike_store", border_style="green", expand=False,
        ))

        collections = sorted(db.list_collection_names())
        if not collections:
            console.print("[dim]  (no collections found)[/dim]\n")
            client.close()
            return

        tbl = Table(
            title=f"Collections in '{db_name}'",
            box=box.ROUNDED, header_style="bold green",
        )
        tbl.add_column("Collection",    style="white")
        tbl.add_column("Doc Count",     justify="right", style="cyan")
        tbl.add_column("Size",          justify="right", style="dim")
        tbl.add_column("Last Inserted", justify="right", style="dim")

        for cname in collections:
            coll  = db[cname]
            count = coll.count_documents({})
            try:
                cs    = db.command("collstats", cname)
                csize = fmt_bytes(int(cs.get("size", 0)))
            except Exception:
                csize = "—"
            tbl.add_row(cname, f"{count:,}", csize, _mongo_last_inserted(coll))

        console.print(tbl)
        console.print()
        client.close()

    except Exception as exc:
        console.print(f"[red]  ✗ MongoDB Connection Failed: {exc}[/red]\n")


def _mongo_last_inserted(coll) -> str:
    TS_FIELDS = ["createdAt", "created_at", "timestamp", "date", "insertedAt", "updatedAt"]
    for field in TS_FIELDS:
        try:
            doc = coll.find_one(sort=[(field, -1)], projection={field: 1})
            if doc and field in doc:
                val = doc[field]
                return val.strftime("%Y-%m-%d %H:%M") if isinstance(val, datetime) else str(val)[:16]
        except Exception:
            continue
    # ObjectId fallback — always works for standard Mongo collections
    try:
        doc = coll.find_one(sort=[("_id", -1)], projection={"_id": 1})
        if doc and hasattr(doc["_id"], "generation_time"):
            return doc["_id"].generation_time.strftime("%Y-%m-%d %H:%M")
    except Exception:
        pass
    return "—"


# ──────────────────────────────────────────────────────────────────
# 5. POSTGRESQL HEALTH
#    Reads:  POSTGRES_USERNAME  POSTGRES_PASSWORD  POSTGRES_DATABASE
#            POSTGRES_HOST      POSTGRES_PORT
#    (your exact .env keys — note USERNAME not USER, DATABASE not DB)
# ──────────────────────────────────────────────────────────────────
def check_postgresql():
    console.print(Rule("[bold blue]PostgreSQL Health[/bold blue]"))

    host  = os.getenv("POSTGRES_HOST",     "localhost")
    port  = os.getenv("POSTGRES_PORT",     "5432")
    user  = os.getenv("POSTGRES_USERNAME") or os.getenv("POSTGRES_USER")
    pwd   = os.getenv("POSTGRES_PASSWORD", "")
    db    = os.getenv("POSTGRES_DATABASE") or os.getenv("POSTGRES_DB")

    # Fallback to full URI vars
    pg_uri = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URI")

    if not pg_uri:
        if not (user and db):
            console.print(
                "[red]  ✗ POSTGRES_USERNAME / POSTGRES_DATABASE not set in .env — skipping.[/red]\n"
            )
            return

    try:
        import psycopg2

        # Connect using individual params (avoids URL-encoding issues with
        # DB names that contain spaces, e.g. "Bike Store Relational Database")
        if pg_uri:
            conn = psycopg2.connect(pg_uri, connect_timeout=5)
        else:
            conn = psycopg2.connect(
                host=host, port=int(port),
                user=user, password=pwd,
                dbname=db, connect_timeout=5,
            )
        console.print(f"[green]  ✓ Connection OK -> {host}:{port} / {db}[/green]")
        cur  = conn.cursor()

        cur.execute(
            "SELECT current_database(), "
            "pg_size_pretty(pg_database_size(current_database())), "
            "version()"
        )
        db_name, db_size, version = cur.fetchone()
        pg_ver = version.split(",")[0]

        console.print(Panel(
            f"[bold]Database:[/bold]    [cyan]{db_name}[/cyan]\n"
            f"[bold]Version:[/bold]     {pg_ver}\n"
            f"[bold]Total Size:[/bold]  {db_size}",
            title="PostgreSQL  ·  Bike Store Relational Database",
            border_style="blue", expand=False,
        ))

        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type   = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = [r[0] for r in cur.fetchall()]

        if not tables:
            console.print("[dim]  (no tables found in public schema)[/dim]\n")
            cur.close(); conn.close()
            return

        tbl = Table(
            title=f"Tables in '{db_name}'",
            box=box.ROUNDED, header_style="bold blue",
        )
        tbl.add_column("Table",         style="white")
        tbl.add_column("Row Count",     justify="right", style="cyan")
        tbl.add_column("Size",          justify="right", style="dim")
        tbl.add_column("Last Inserted", justify="right", style="dim")

        for tname in tables:
            # Approximate row count first (fast), exact if needed
            try:
                cur.execute(
                    "SELECT reltuples::bigint FROM pg_class WHERE relname = %s", (tname,)
                )
                approx = cur.fetchone()[0]
                if approx <= 0:
                    cur.execute(f'SELECT COUNT(*) FROM "{tname}"')
                    row_count = f"{cur.fetchone()[0]:,}"
                else:
                    row_count = f"~{approx:,}"
            except Exception:
                row_count = "?"

            try:
                cur.execute("SELECT pg_size_pretty(pg_total_relation_size(%s))", (tname,))
                tsize = cur.fetchone()[0]
            except Exception:
                tsize = "—"

            tbl.add_row(tname, row_count, tsize, _pg_last_inserted(cur, tname))

        console.print(tbl)
        console.print()
        cur.close()
        conn.close()

    except Exception as exc:
        console.print(f"[red]  ✗ PostgreSQL Connection Failed: {exc}[/red]\n")


def _pg_last_inserted(cur, tname: str) -> str:
    TS_COLS = ["created_at", "createdAt", "inserted_at", "timestamp", "date", "updated_at"]
    try:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name   = %s
              AND table_schema = 'public'
              AND column_name  = ANY(%s)
            LIMIT 1
            """,
            (tname, TS_COLS),
        )
        row = cur.fetchone()
        if row:
            cur.execute(f'SELECT MAX("{row[0]}") FROM "{tname}"')
            val = cur.fetchone()[0]
            if val:
                return str(val)[:16]
    except Exception:
        pass
    return "—"


# ──────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────
def main():
    project_root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(".").resolve()

    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        console.print(f"[yellow]  No .env found at {env_path}[/yellow]")

    now       = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_run  = get_last_run(project_root)
    run_count = get_run_count(project_root)

    console.print()
    console.print(Panel.fit(
        f"[bold white]Project Health Monitor[/bold white]\n"
        f"[dim]Project  : {project_root}[/dim]\n"
        f"[dim]Run Time : {now}[/dim]\n"
        f"[dim]Last Run : {last_run}[/dim]\n"
        f"[dim]Run #    : {run_count + 1}[/dim]",
        border_style="bright_white",
    ))
    console.print()

    check_files(project_root)
    check_git(project_root)
    check_pyspark(project_root)
    check_mongodb()
    check_postgresql()

    save_last_run(project_root)
    console.print(
        Panel("[bold green]✓ Health check complete![/bold green]",
              border_style="green", expand=False)
    )
    console.print()


if __name__ == "__main__":
    main()