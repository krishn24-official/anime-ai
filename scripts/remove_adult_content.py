import asyncio
import io
import sys
from bson import ObjectId
from pathlib import Path

# Force UTF-8 output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.mongo import connect_db, get_db, close_db

MOVIE_IDS_TO_DELETE = [
    "movie_affair_at_the_nuns_temple_paradise_sex",
    "movie_erotic_ghost_story_iii",
    "movie_the_quest_of_the_sex_a_holly_hole",
    "movie_the_other_side_of_the_sex",
    "movie_sex_plate_17",
    "movie_sex_and_the_single_girl",
    "movie_sex_rider_wet_highway",
    "movie_erotic_ghost_story",
    "movie_idol_sex_la_korean_women",
    "movie_teenager_s_sex",
    "movie_sex_tape",
    "movie_sex_and_luc_a",
    "movie_sex_and_zen_iii",
    "movie_i_want_your_sex",
    "movie_the_karma_of_sex",
    "movie_dangerous_drugs_of_sex",
    "movie_sex_and_the_city",
    "movie_9to5_days_in_porn",
    "movie_god_sex_and_truth",
    "movie_teenage_sex_and_death_at_camp_miasma",
    "movie_gail_daughtry_and_the_celebrity_sex_pass",
    "movie_how_to_have_sex",
    "movie_sex_drive",
    "movie_sex_and_the_city_2",
    "movie_erotic_sister",
    "movie_freak_talks_about_sex",
    "movie_sex_rays_und_stop_motion_ein_gespr_ch_mit_dr_rolf_giesen_christian_genzel",
    "movie_revenge_porn_love_is_dead",
    "movie_sex_colored_hell",
    "movie_sex_shock_b_k",
    "movie_kinbaku_hentai_tsuma",
    "movie_it_s_only_sex",
    "movie_bizarre_body_sex",
    "movie_cleopatra_queen_of_sex",
    "movie_disco_sex_machine_la_naissance_du_porn_chic",
    "movie_netorare_y_gi_dangerous_thursday",
    "movie_porn",
    "movie_some_an_erotic_tale",
    "movie_crumpet_a_very_british_sex_symbol",
    "movie_just_for_sex",
    "movie_brain_sex",
    "movie_outspoken_the_porn_academy",
    "movie_erotic_scalp_care_shop",
    "movie_sex_and_death_101",
    "movie_erotic_blossoms_in_a_dream",
    "movie_hollywood_sex_wars",
    "movie_saishin_f_zoku_hentai_hotel_j",
    "movie_sex_symbol_dynasty_women_behind_the_dynasty",
    "movie_sex_and_the_friend_group",
    "movie_pray_for_sex",
    "movie_liebesgr_e_aus_der_lederhose_3_teil_sex_express_in_oberbayern",
    "movie_real_doll_sex_mannequin",
    "movie_in_the_realm_of_sex",
    "movie_the_second_greatest_sex",
    "movie_fuku_man_fujin_nettori_netorare",
    "movie_damasu_ij_hentai",
    "movie_sex_b_s",
    "movie_seishun_sex_hana_gassen",
]

TV_SERIES_IDS_TO_DELETE = [
    "tv_selling_sex",
    "tv_friends_sex_and_games",
    "tv_sex_murder",
    "tv_safe_sex",
    "tv_let_s_talk_about_sex",
    "tv_sex_and_the_city",
    "tv_porn_king_the_rise_fall_of_ron_jeremy",
    "tv_sex_insta_zno",
]

MANGA_IDS_TO_DELETE = [
    "manga_betrayed_by_the_hero_i_formed_a_milf_party_with_his_mom",
    "manga_the_villainous_noble_is_way_too_fond_of_milf_heroines",
    "manga_sex_dungeon_wagaya_no_chika_ni_h_kaisuu_level_no_dungeon_ga_shutsugen_shita",
    "manga_jk_haru_is_a_sex_worker_in_another_world",
    "manga_isekai_ntr_shinyuu_no_onna_wo_saikyou_skill_de_otosu_houhou",
    "manga_vr_eroge_yattetara_isekai_ni_tensei_shita_no_de_bishoujo_maou_wo_doreika_suru_cross_out_saber",
    "manga_netorare_manga_no_kuzu_otoko_ni_tensei_shita_hazu_ga_heroine_ga_yotte_kuru_ken",
    "manga_ntr_netsuzou_trap",
    "manga_hiota_no_kanojo_ga_ore_no_motteru_eroge_ni_kyoumi_shinshin_nanda_ga",
]

NEWS_IDS_TO_DELETE = [
    "6a393b0f2818ac8eeb8e6f0a",
    "6a3f713fbb689922ff140f44",
    "6a5064e6b5dd0195d32d51a7",
    "6a51089515731816e31b8206",
    "6a56524a335ac9f492318a88",
    "6a5c3417c08cea54c8241101",
    "6a5fa633de0f73e5492314c6",
    "6a607ce2487347379ee2a5a0",
    "6a69cd3287e313289d585d5c",
    "6a6d4a23bf4e714aa5857750",
    "6a700c51600a09c7bcec87d0",
    "6a76829a0d8f1b551beacc8a",
    "6a77f682619b98efb5fa6171",
    "6a77f687619b98efb5fa6182",
    "6a905a218e05b8c7fef22ba2",
    "6a905a368e05b8c7fef22bec",
    "6a905a5a8e05b8c7fef22c48",
    "6a9953a262d7852ed2e0a866",
    "6a9a3fe5a342c97db6e40f70",
    "6aaa25b4fcd2eaeb4d1abd22",
    "6aad4775cc8465c43e02dad5",
    "6ad2d21df320b7622de2fbfb",
    "6ad2d322f320b7622de2fd66",
    "6ad2d328f320b7622de2fd88",
    "6ad73dad9e2e7c65e001ff29",
    "6ad8c9e63d7fca5f45032883",
    "6ad8ca5395462459991951bd",
    "6ad8e4122b7bcae826a1c0d3",
    "6add6ef92490b26a379502fe",
    "6adf6b57bf11817293f7cbef",
    "6adf6bbbbf11817293f7cc7a",
]

CHARACTER_IDS_TO_DELETE = [
    "char_female_porn_star",
]

async def purge_adult_content():
    await connect_db()
    db = get_db()
    
    print("=" * 80)
    print("PURGING ADULT CONTENT FROM DATABASE")
    print("=" * 80)

    # 1. Purge Movies
    res_movies = await db.movies.delete_many({"_id": {"$in": MOVIE_IDS_TO_DELETE}})
    print(f"Movies deleted: {res_movies.deleted_count}/{len(MOVIE_IDS_TO_DELETE)}")

    # 2. Purge TV Series
    res_tv = await db.tv_series.delete_many({"_id": {"$in": TV_SERIES_IDS_TO_DELETE}})
    print(f"TV series deleted: {res_tv.deleted_count}/{len(TV_SERIES_IDS_TO_DELETE)}")

    # 3. Purge Manga
    res_manga = await db.manga.delete_many({"_id": {"$in": MANGA_IDS_TO_DELETE}})
    print(f"Manga deleted: {res_manga.deleted_count}/{len(MANGA_IDS_TO_DELETE)}")

    # 4. Purge Characters
    res_chars = await db.characters.delete_many({"_id": {"$in": CHARACTER_IDS_TO_DELETE}})
    print(f"Characters deleted: {res_chars.deleted_count}/{len(CHARACTER_IDS_TO_DELETE)}")

    # 5. Purge News
    news_obj_ids = []
    for nid in NEWS_IDS_TO_DELETE:
        try:
            news_obj_ids.append(ObjectId(nid))
        except Exception:
            pass
    res_news = await db.news.delete_many({
        "$or": [
            {"_id": {"$in": news_obj_ids}},
            {"_id": {"$in": NEWS_IDS_TO_DELETE}}
        ]
    })
    print(f"News articles deleted: {res_news.deleted_count}/{len(NEWS_IDS_TO_DELETE)}")

    # 6. Cleanup any dangling references in related collections
    all_content_ids = MOVIE_IDS_TO_DELETE + TV_SERIES_IDS_TO_DELETE + MANGA_IDS_TO_DELETE
    
    del_events = await db.events.delete_many({
        "$or": [
            {"movie_id": {"$in": all_content_ids}},
            {"tv_series_id": {"$in": all_content_ids}},
            {"manga_id": {"$in": all_content_ids}},
            {"content_id": {"$in": all_content_ids}},
            {"entity_id": {"$in": all_content_ids}},
        ]
    })
    print(f"Associated events deleted: {del_events.deleted_count}")

    del_trending = await db.trending.delete_many({
        "$or": [
            {"item_id": {"$in": all_content_ids}},
            {"content_id": {"$in": all_content_ids}},
            {"_id": {"$in": all_content_ids}}
        ]
    })
    print(f"Associated trending items deleted: {del_trending.deleted_count}")

    del_tr_content = await db.trending_content.delete_many({
        "$or": [
            {"content_id": {"$in": all_content_ids}},
            {"_id": {"$in": all_content_ids}}
        ]
    })
    print(f"Associated trending_content items deleted: {del_tr_content.deleted_count}")

    del_comments = await db.comments.delete_many({
        "content_id": {"$in": all_content_ids}
    })
    print(f"Associated comments deleted: {del_comments.deleted_count}")

    del_ratings = await db.ratings.delete_many({
        "content_id": {"$in": all_content_ids}
    })
    print(f"Associated ratings deleted: {del_ratings.deleted_count}")

    del_watchlist = await db.watchlist.delete_many({
        "content_id": {"$in": all_content_ids}
    })
    print(f"Associated watchlist entries deleted: {del_watchlist.deleted_count}")

    del_chapters = await db.chapters.delete_many({
        "manga_id": {"$in": MANGA_IDS_TO_DELETE}
    })
    print(f"Associated chapters deleted: {del_chapters.deleted_count}")

    print("=" * 80)
    print("PURGE COMPLETE AND VERIFIED!")
    print("=" * 80)

    await close_db()

if __name__ == "__main__":
    asyncio.run(purge_adult_content())
