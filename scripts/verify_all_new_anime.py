import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import connect_db, get_db, close_db
from app.services import lore_service

async def main():
    await connect_db()
    db = get_db()
    series_list = [
        ("Naruto", "anime_naruto"),
        ("Naruto Shippuden", "anime_naruto_shippuden"),
        ("Boruto", "anime_boruto"),
        ("Demon Slayer", "anime_demon_slayer"),
        ("Jujutsu Kaisen", "anime_jujutsu_kaisen"),
        ("Attack on Titan", "anime_attack_on_titan"),
        ("Bleach", "anime_bleach"),
        ("One Piece", "anime_one_piece"),
    ]
    print("=" * 75)
    print(f"{'Anime Series':<24} | {'Episodes':<10} | {'Events':<10} | {'Lore Chunks':<12}")
    print("-" * 75)
    total_eps = 0
    total_evs = 0
    total_lore = 0
    for name, aid in series_list:
        ep_c = await db["episodes"].count_documents({"anime_id": aid})
        ev_c = await db["events"].count_documents({"anime_id": aid})
        lore_c = await db["lore_chunks"].count_documents({"series_id": aid})
        total_eps += ep_c
        total_evs += ev_c
        total_lore += lore_c
        print(f"{name:<24} | {ep_c:<10} | {ev_c:<10} | {lore_c:<12}")
    print("=" * 75)
    print(f"{'TOTAL INGESTED':<24} | {total_eps:<10} | {total_evs:<10} | {total_lore:<12}")
    print("=" * 75)

    # Check generated PDF lore books
    pdf_dir = PROJECT_ROOT / "data" / "anime_episodes"
    print("\n" + "=" * 75)
    print("GENERATED PDF LORE BOOKS")
    print("=" * 75)
    for p in sorted(pdf_dir.glob("*.pdf")):
        print(f"  - {p.name:<38} ({p.stat().st_size / 1024:.1f} KB)")
    print("=" * 75)

    # Test RAG query on Demon Slayer
    q_ds = "What is the title and release date of Demon Slayer Episode 1?"
    print(f"\n[RAG Test Query]: '{q_ds}'")
    res_ds = await lore_service.query_lore(q_ds, series_id="anime_demon_slayer", top_k=1)
    if res_ds:
        print(f"  Found Section: '{res_ds[0].section_title}' (Score: {res_ds[0].score:.4f})")
        print(f"  Preview: {res_ds[0].chunk_text[:140].replace(chr(10), ' ')}...")

    # Test RAG query on Bleach
    q_bl = "Which manga chapter does Bleach episode 1 adapt?"
    print(f"\n[RAG Test Query]: '{q_bl}'")
    res_bl = await lore_service.query_lore(q_bl, series_id="anime_bleach", top_k=1)
    if res_bl:
        print(f"  Found Section: '{res_bl[0].section_title}' (Score: {res_bl[0].score:.4f})")
        print(f"  Preview: {res_bl[0].chunk_text[:140].replace(chr(10), ' ')}...")

    await close_db()

if __name__ == "__main__":
    asyncio.run(main())
