from __future__ import annotations

from pathlib import Path

from .paths import desktop_entry_path, data_dir


DESKTOP_TEMPLATE = """[Desktop Entry]
Type=Application
Name=LG TV Tools
Comment=Discover LG TVs and launch casting workflows
GenericName=LG TV casting utility
X-Author=Dantes de la Calle Frexes (Reyam)
X-AuthorEmail=rey.amado8509@gmail.com
X-AppVersion=0.1.3
X-AppID=lg-tv-tools
Exec={exec_path}
Icon={icon_path}
Terminal=false
Categories=Utility;Network;AudioVideo;
StartupNotify=true
"""


def render_desktop_entry(exec_path: str) -> str:
    return DESKTOP_TEMPLATE.format(
        exec_path=exec_path,
        icon_path=str(data_dir() / "icons" / "app.svg"),
    )


def desktop_file() -> Path:
    return desktop_entry_path()
