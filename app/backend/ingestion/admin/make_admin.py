"""
One-time script to grant admin access to a user by email.

Run:
    python -m app.backend.ingestion.admin.make_admin your_email@example.com
"""
import asyncio
import sys

from app.db.mongo import connect_db, close_db, get_db


async def main():
    if len(sys.argv) < 2:
        print("Usage: python -m app.backend.ingestion.admin.make_admin <email>")
        return

    email = sys.argv[1].strip().lower()

    await connect_db()
    db = get_db()

    result = await db["users"].update_one(
        {"email": email},
        {"$set": {"is_admin": True}}
    )

    await close_db()

    if result.matched_count == 0:
        print(f"❌ No user found with email: {email}")
    else:
        print(f"✅ {email} is now an admin")


if __name__ == "__main__":
    asyncio.run(main())