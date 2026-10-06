import asyncio
import sys
import io
from pymongo import AsyncMongoClient

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from app.config import MONGO_URI, MONGO_DB_NAME

ADULT_TV_SERIES_TO_DELETE = [
    ("tv_dark_chapel", "Dark Chapel", 90149),
    ("tv_love_me_hide_and_seek", "Love Me: Hide and Seek", 295025),
    ("tv__55", "妻ネトリ", 327897),
    ("tv__61", "妻ネトリ 零-僕の過ち 彼女の選択-", 328348),
    ("tv_kiken_na_mori_onigokko", "Kiken na Mori Onigokko", 238280),
    ("tv_imouto_bitch_ni_shiboraretai", "Imouto Bitch ni Shiboraretai", 74480),
    ("tv_onichichi_harem_story", "Onichichi Harem Story", 271230),
    ("tv_four_for_foreplay", "Four for Foreplay", 83253),
    ("tv_rakuen_shinshoku_island_of_the_dead", "Rakuen Shinshoku: Island of the Dead", 222928),
    ("tv_semen_extraction_ward", "Semen Extraction Ward", 124867),
    ("tv_bakunyuu_maid_gari", "Bakunyuu Maid Gari", 116746),
    ("tv_maid_to_please", "Maid to Please", 124966),
    ("tv_maid_for_pleasure", "Maid for Pleasure", 125214),
    ("tv_reika_wa_karei_na_boku_no_joou", "Reika wa Karei na Boku no Joou", 297313),
    ("tv_sister_breeder", "Sister Breeder", 297314),
    ("tv_binkan_athlete", "Binkan Athlete", 280981),
    ("tv_slave_maid_princess", "Slave Maid Princess", 100827),
    ("tv_love_me_kaede_to_suzu_the_animation", "Love Me: Kaede to Suzu the Animation", 158208),
    ("tv_onahole_classroom_all_girls_pregnancy_plan", "Onahole Classroom: All Girls Pregnancy Plan", 133805),
    ("tv_sakuramiya_shimai_no_netorare_kiroku", "Sakuramiya Shimai no Netorare Kiroku", 93080),
]

async def main():
    mongo_client = AsyncMongoClient(MONGO_URI)
    db = mongo_client[MONGO_DB_NAME]
    print("Connected to MongoDB.", flush=True)

    tv_ids = [item[0] for item in ADULT_TV_SERIES_TO_DELETE]

    # 1. Delete from tv_series
    tv_del_res = await db["tv_series"].delete_many({"_id": {"$in": tv_ids}})
    print(f"Deleted {tv_del_res.deleted_count} adult TV series from tv_series collection.", flush=True)

    # 2. Delete episodes
    ep_del_res = await db["episodes"].delete_many({
        "$or": [
            {"parent_id": {"$in": tv_ids}},
            {"tv_series_id": {"$in": tv_ids}}
        ]
    })
    print(f"Deleted {ep_del_res.deleted_count} associated episodes.", flush=True)

    # 3. Delete events
    ev_del_res = await db["events"].delete_many({
        "$or": [
            {"content_id": {"$in": tv_ids}},
            {"tv_id": {"$in": tv_ids}},
            {"tv_series_id": {"$in": tv_ids}}
        ]
    })
    print(f"Deleted {ev_del_res.deleted_count} associated events.", flush=True)

    # 4. Delete relationships
    rel_del_res = await db["relationships"].delete_many({
        "$or": [
            {"source_id": {"$in": tv_ids}},
            {"target_id": {"$in": tv_ids}}
        ]
    })
    print(f"Deleted {rel_del_res.deleted_count} associated relationships.", flush=True)

    # 5. Delete watchlist & ratings & trending
    await db["watchlist"].delete_many({"content_id": {"$in": tv_ids}})
    await db["ratings"].delete_many({"content_id": {"$in": tv_ids}})
    await db["trending"].delete_many({"content_id": {"$in": tv_ids}})

    print("Cleanup completed successfully!", flush=True)
    await mongo_client.close()

if __name__ == "__main__":
    asyncio.run(main())
