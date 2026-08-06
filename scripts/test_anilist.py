import asyncio
import httpx

query = """
query ($anime: String) {
  Media(search: $anime, type: ANIME) {
    id
    characters(page: 1, perPage: 1) {
      edges {
        role
        voiceActors(language: JAPANESE) {
          id
          name {
            full
            native
          }
          languageV2
        }
        node {
          name {
            full
          }
        }
      }
    }
  }
}
"""

async def test():
    async with httpx.AsyncClient() as client:
        resp = await client.post("https://graphql.anilist.co", json={"query": query, "variables": {"anime": "Naruto"}})
        print(resp.json())

asyncio.run(test())
