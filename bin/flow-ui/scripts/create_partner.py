#!/usr/bin/env python3
"""
create_partner.py — CLI utility to create a new partner.

Usage:
  python scripts/create_partner.py --code alexander-sansan1005 \\
    --name "Александр (@sansan1005)" --tg-handle sansan1005

Output: magic-link URL to send to partner in Telegram.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent dir to path so `app.partners` importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import load_config
from app.partners import create_partner, get_partner_by_token, list_partners


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a new Flow WSCK partner")
    parser.add_argument("--code", required=True, help="Unique partner code (URL-safe)")
    parser.add_argument("--name", required=True, help="Human-readable name")
    parser.add_argument("--tg-handle", default=None, help="Telegram @handle")
    parser.add_argument("--folder", default=None, help="Custom folder path (default: code)")
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().parent.parent / "config.yml"),
        help="Path to config.yml",
    )
    parser.add_argument(
        "--base-url",
        default="https://flow.vschk.online",
        help="Base URL for magic link generation",
    )
    parser.add_argument("--list", action="store_true", help="List existing partners and exit")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        config_path = config_path.parent / "config.example.yml"
    cfg = load_config(config_path)

    partners_db = getattr(cfg.paths, "partners_db", None)
    if not partners_db:
        # Fallback path if config not yet updated with partners_db
        partners_db = config_path.parent / "data" / "partners.db"
    partners_db = Path(partners_db).expanduser()

    if args.list:
        rows = list_partners(partners_db)
        if not rows:
            print("(no partners registered)")
            return
        for r in rows:
            print(f"{r['code']:30s} | {r['name']:40s} | active={r['is_active']}")
        return

    partner = create_partner(
        db_path=partners_db,
        code=args.code,
        name=args.name,
        tg_handle=args.tg_handle,
        folder_path=args.folder,
    )

    print(f"✅ Partner created:")
    print(f"   Code:       {partner['code']}")
    print(f"   Name:       {partner['name']}")
    print(f"   TG:         @{partner.get('tg_handle') or '—'}")
    print(f"   Folder:     partner-content/{partner['folder_path']}/")
    print(f"   Token:      {partner['magic_token']}")
    print()
    print(f"🔗 Magic-link URL:")
    print(f"   {args.base_url}/partner/{partner['magic_token']}/")


if __name__ == "__main__":
    main()
