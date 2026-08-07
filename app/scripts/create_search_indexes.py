import asyncio
from app.db.mongo import connect_db, close_db, get_db

async def create_indexes():
    print("Starting Atlas Search index creation...")
    await connect_db()
    db = get_db()
    
    indexes_to_create = [
        {
            "collection": "movies",
            "name": "title_search",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "title": {"type": "string", "analyzer": "lucene.standard"},
                        "original_title": {"type": "string", "analyzer": "lucene.standard"}
                    }
                }
            }
        },
        {
            "collection": "tv_series",
            "name": "title_search",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "title": {"type": "string", "analyzer": "lucene.standard"},
                        "original_title": {"type": "string", "analyzer": "lucene.standard"}
                    }
                }
            }
        },
        {
            "collection": "characters",
            "name": "name_search",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "name": {"type": "string", "analyzer": "lucene.standard"}
                    }
                }
            }
        },
        {
            "collection": "actors",
            "name": "name_search",
            "definition": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "name": {"type": "string", "analyzer": "lucene.standard"}
                    }
                }
            }
        }
    ]
    
    for idx in indexes_to_create:
        coll = idx["collection"]
        name = idx["name"]
        print(f"Checking indexes for {coll}...")
        
        # Check if index already exists
        cursor = await db[coll].list_search_indexes(name)
        existing = await cursor.to_list(None)
        
        if existing:
            print(f"Index '{name}' already exists on {coll}.")
        else:
            print(f"Creating index '{name}' on {coll}...")
            try:
                res = await db[coll].create_search_index({
                    "name": name,
                    "definition": idx["definition"]
                })
                print(f"Created: {res}")
            except Exception as e:
                print(f"Failed to create index on {coll}: {e}")

    await close_db()
    print("Done triggering index creation.")

if __name__ == "__main__":
    asyncio.run(create_indexes())
