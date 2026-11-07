# Architecture

The backend is being migrated, module by module, to a **clean architecture**: business
logic does not depend on FastAPI, MongoDB, Cloudinary or any other technology. To change
a technology you write new adapters; the business logic stays untouched.

**Status:** pilot complete (Trending). Other modules still use the legacy layout
(`app/api/routes`, `app/services`, `app/repositories`). See [Migration status](#migration-status).

## Layers

```
app/
  domain/            Entities, business rules, ports (interfaces). Pure Python.
  application/       Use cases. Orchestrate domain objects through ports.
  infrastructure/    Port implementations: MongoDB, Cloudinary, external APIs.
  interfaces/http/   FastAPI routers + request/response schemas. Thin.
  container.py       Composition root: builds use cases from implementations.
```

Dependencies point **inward only**:

```
interfaces/http ──► application ──► domain ◄── infrastructure
        └──────────── container.py wires them together ────────┘
```

| Layer | May import | Must NOT import |
|---|---|---|
| `domain` | standard library | FastAPI, pydantic, pymongo/bson, SDKs, any other `app.*` layer |
| `application` | `domain` | frameworks, drivers, `infrastructure`, `interfaces`, `container`, legacy packages |
| `infrastructure` | `domain`, drivers/SDKs | FastAPI, `application`, `interfaces` |
| `interfaces/http` | `application`, `domain`, `container`, FastAPI | database drivers |

These rules are enforced by `tests/unit/test_architecture.py`; a violation fails the test suite.

## Where things go

| You are writing… | Put it in |
|---|---|
| A business rule ("auto entries never overwrite an admin pin") | `domain/<module>/rules.py` |
| A data shape the business talks about (`TrendingEntry`) | `domain/<module>/entities.py` (dataclass) |
| "I need to store/fetch X" | a `Protocol` in `domain/<module>/ports.py` |
| A user action ("pin an item") | a method on the use-case class in `application/<module>/service.py` |
| A MongoDB query | `infrastructure/mongo/<module>_repository.py` |
| An HTTP endpoint / JSON shape | `interfaces/http/<module>/router.py` and `schemas.py` |
| Error for "not found" / "invalid input" | raise `NotFoundError` / `InvalidInputError` from `application/errors.py`; the HTTP layer maps them to 404/400 |

Use cases never raise `HTTPException` and never see Mongo documents. Routers never
contain business rules or queries.

## Swapping a technology

**Database (e.g. MongoDB → PostgreSQL):**
1. Implement each port in `domain/*/ports.py` under `infrastructure/postgres/`.
2. Change the constructors in `app/container.py`.
3. Run the unit tests (unchanged) plus new integration tests for the new repositories.

**Image storage (e.g. Cloudinary → S3):** implement `ImageStorage`
(`domain/shared/ports.py`) and change `container.image_storage()`.

**Web framework (e.g. FastAPI → another):** rewrite only `interfaces/http/` and keep the
same JSON contract (field names in `schemas.py`), so the frontend keeps working.

## Testing

- `tests/unit/` runs use cases against in-memory fakes (`tests/fakes/`). No database;
  milliseconds per test. Put business-logic tests here.
- `tests/test_<module>.py` holds integration tests for the MongoDB repositories
  (test database `anime_ai_test`).

## Recipe: migrating a module

Follow the Trending module as the reference implementation.

1. **Snapshot** the module's current HTTP responses (status codes and bodies) so the
   API contract can be compared afterwards.
2. **Domain:** entities (dataclasses), pure rules, and ports for every storage or
   external call the module makes.
3. **Application:** one service class whose constructor takes the ports. Move logic
   here from `app/services/<module>_service.py`. Raise application errors, not HTTP errors.
4. **Infrastructure:** Mongo repositories implementing the ports; move queries here
   from `app/repositories/<module>_repository.py`. Collection names go in
   `infrastructure/mongo/collections.py`.
5. **Interfaces:** router + pydantic schemas with the **same paths and field names**.
   Register it in `app/api/router.py`; delete the old route functions.
6. **Container:** add a factory for the service; point schedulers/pipelines at it.
7. **Delete** the legacy service/repository modules. If other unmigrated modules still
   use a helper, leave a thin re-export marked `LEGACY` (see `app/services/content_lookup.py`).
8. **Tests:** unit tests with fakes, repository integration tests, then re-run the
   snapshot comparison and the API smoke tests.
9. **Frontend:** in `anime_ai_FE`, add the app model in `src/domain/`, a DTO + mapper in
   `src/services/<module>Mapper.ts`, and switch components to the model.

## Migration status

| Module | Status |
|---|---|
| Trending (pins, trending list, news/search signals) | ✅ migrated |
| Search (global search bar, `GET /search`) | ✅ migrated (see [Global search](#global-search)) |
| Auth & users | ⏳ legacy |
| Content: ratings, watchlist, comments, releases | ⏳ legacy |
| Anime, manga, movies, TV series (+ admin) | ⏳ legacy |
| Characters, relationships, organizations (+ admin) | ⏳ legacy |
| Actors, voice actors (+ admin) | ⏳ legacy |
| Episodes & chapters (+ admin) | ⏳ legacy |
| News (pipeline, admin news, scheduler) | ⏳ legacy |
| Home, events, search, tier lists, game | ⏳ legacy |
| Chat, agent, lore (AI) | ⏳ legacy, planned to move to a separate project |

## Global search

- **Ranking** lives in `domain/search/rules.py`: exact > starts with whole words >
  contains whole words > starts with > a word starts with > (weak) contains > (weak) typo.
  Aliases (synonyms, native/original titles) are searched too; weak matches only show
  when nothing strong matched. Both index implementations share these rules.
- **Two `SearchIndex` implementations**, combined by `FallbackSearchIndex`:
  - `infrastructure/mongo/regex_search_index.py`: works on any MongoDB, no setup.
  - `infrastructure/mongo/atlas_search_index.py`: Atlas Search on the `search_catalog`
    collection (one index for all kinds). Used for the kinds in `SEARCH_CATALOG_KINDS`
    once the index is queryable; everything else falls back to regex automatically.
- **Catalog upkeep:** admin create/update/delete routes are decorated with
  `@keeps_search_in_sync(kind)`; a scheduler job rebuilds the catalog every
  `SEARCH_CATALOG_REBUILD_HOURS` (only once the index exists).
- **Setup (Atlas only):** `python -m app.scripts.build_search_catalog --check`, then
  `python -m app.scripts.build_search_catalog --wait`. The build refuses to run if it
  would exceed `ATLAS_STORAGE_LIMIT_MB`: **Atlas blocks every write on the cluster when
  the storage quota is reached.**
- `SEARCH_BACKEND=regex` disables Atlas entirely.
- **One search for everything:** `SearchService.search()` serves the header search bar;
  `SearchService.search_kind()` serves every other title/character/actor search
  (Library lists, `/characters/search`, `/actors/search`, `/anime|manga/search`, the
  admin relationship picker, tier lists), via `app/services/search_listing.py` for the
  legacy endpoints. Admin list filters use the same matcher (`app/utils/search_utils.py`).
  Never write a new regex search: call the service.
- **Frontend:** every search box is `components/search/SearchInput`; debouncing is
  `hooks/useDebouncedValue`; search-as-you-type with stale-response protection is
  `hooks/useSearchResults` (`useSearch` for non-list results); pickers that choose a
  title use `components/search/ContentSearchPicker`.

## Frontend counterpart (`anime_ai_FE`)

```
src/domain/      App models (camelCase). Components and the store use only these.
src/services/    The only code that knows the API: DTO types, mappers, HTTP calls.
src/features/    UI. Never builds request payloads or reads wire fields.
```

A backend replacement only has to honour the documented JSON contract; any wire
change is absorbed in one mapper per module.
