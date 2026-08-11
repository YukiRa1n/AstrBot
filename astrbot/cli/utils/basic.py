from pathlib import Path

import click

# Static assets bundled inside the installed wheel (built by hatch_build.py).
_BUNDLED_DIST = Path(__file__).parent.parent.parent / "dashboard" / "dist"


def check_astrbot_root(path: str | Path) -> bool:
    """Check if the path is an AstrBot root directory"""
    if not isinstance(path, Path):
        path = Path(path)
    if not path.exists() or not path.is_dir():
        return False
    if not (path / ".astrbot").exists():
        return False
    return True


def get_astrbot_root() -> Path:
    """获取 AstrBot 根目录路径

    查找顺序：
    1. 环境变量 ASTRBOT_ROOT
    2. 从当前目录向上查找包含 .astrbot 标记的目录
    3. 通过包安装路径定位（editable install / 源码目录）
    4. 回退到当前工作目录
    """
    # 1. 环境变量
    import os

    env_root = os.environ.get("ASTRBOT_ROOT")
    if env_root:
        p = Path(env_root)
        if check_astrbot_root(p):
            return p

    # 2. 向上查找 .astrbot 标记。显式进入的实例应优先于源码安装目录。
    current = Path.cwd()
    for parent in [current, *current.parents]:
        if (parent / ".astrbot").exists():
            return parent

    # 3. 通过包安装路径定位（editable install 场景）
    # __file__ 在 astrbot/cli/utils/basic.py，向上 4 级到达项目根目录
    source_root = Path(__file__).resolve().parent.parent.parent.parent
    if check_astrbot_root(source_root):
        return source_root

    # 4. 回退到当前目录
    return current


async def check_dashboard(astrbot_root: Path) -> None:
    """Check if the dashboard is installed"""
    from astrbot.core.config.default import VERSION
    from astrbot.core.utils.io import download_dashboard, get_dashboard_version

    from .version_comparator import VersionComparator

    # If the wheel ships bundled dashboard assets, no network download is needed.
    if _BUNDLED_DIST.exists():
        click.echo("Dashboard is bundled with the package – skipping download.")
        return

    try:
        dashboard_version = await get_dashboard_version()
        match dashboard_version:
            case None:
                click.echo("Dashboard is not installed")
                if click.confirm(
                    "Install dashboard?",
                    default=True,
                ):
                    click.echo("Installing dashboard...")
                    await download_dashboard(
                        path="data/dashboard.zip",
                        extract_path=str(astrbot_root),
                        version=f"v{VERSION}",
                        latest=False,
                    )
                    click.echo("Dashboard installed successfully")

            case str():
                if VersionComparator.compare_version(VERSION, dashboard_version) <= 0:
                    click.echo("Dashboard is already up to date")
                    return
                try:
                    version = dashboard_version.split("v")[1]
                    click.echo(f"Dashboard version: {version}")
                    await download_dashboard(
                        path="data/dashboard.zip",
                        extract_path=str(astrbot_root),
                        version=f"v{VERSION}",
                        latest=False,
                    )
                except Exception as e:
                    click.echo(f"Failed to download dashboard: {e}")
                    return
    except FileNotFoundError:
        click.echo("Initializing dashboard directory...")
        try:
            await download_dashboard(
                path=str(astrbot_root / "dashboard.zip"),
                extract_path=str(astrbot_root),
                version=f"v{VERSION}",
                latest=False,
            )
            click.echo("Dashboard initialized successfully")
        except Exception as e:
            click.echo(f"Failed to download dashboard: {e}")
            return
