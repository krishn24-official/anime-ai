"""Set up / rebuild the Atlas Search catalog used by GET /search.

    python -m app.scripts.build_search_catalog --check    # estimate size vs. storage quota (no writes)
    python -m app.scripts.build_search_catalog            # rebuild catalog + create index if missing
    python -m app.scripts.build_search_catalog --wait     # ...and wait until the index is queryable
    python -m app.scripts.build_search_catalog --status   # only show index status

The build refuses to run if it would push the cluster past ATLAS_STORAGE_LIMIT_MB
(Atlas blocks ALL writes when the quota is reached). Until the index is queryable,
/search automatically uses regex search instead. Requires MongoDB Atlas.
"""

import argparse
import asyncio
import time

from app import container
from app.config import ATLAS_STORAGE_LIMIT_MB
from app.db.mongo import close_db, connect_db
from app.infrastructure.mongo.search_catalog import StorageQuotaError


async def main(check_only: bool, wait: bool, status_only: bool) -> int:
    await connect_db()
    catalog = container.search_catalog()
    try:
        if status_only:
            print("index:", await catalog.index_status())
            return 0

        print(f"catalog kinds: {', '.join(catalog.kinds)}")
        try:
            report = await catalog.check_quota(ATLAS_STORAGE_LIMIT_MB)
            print("storage check OK:", report)
        except StorageQuotaError as exc:
            print("REFUSING TO BUILD:", exc)
            return 1
        if check_only:
            return 0

        started = time.monotonic()
        print("rebuilding search catalog...")
        print(await catalog.rebuild(), f"({time.monotonic() - started:.0f}s)")
        print("index status:", await catalog.ensure_index())

        while wait:
            info = await catalog.index_status() or {}
            print(f"  status={info.get('status')} queryable={info.get('queryable')}")
            if info.get("queryable"):
                break
            await asyncio.sleep(10)
        return 0
    finally:
        await close_db()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only estimate size vs. quota")
    parser.add_argument("--wait", action="store_true", help="wait until the index is queryable")
    parser.add_argument("--status", action="store_true", help="only print the index status")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.check, args.wait, args.status)))
