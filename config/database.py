import asyncio

from motor.motor_asyncio import AsyncIOMotorClient

from config.settings import settings


class Database:
    client: AsyncIOMotorClient = None


db = Database()


async def get_database():
    return db.client[settings.DATABASE_NAME]


async def connect_to_mongo(retries: int = 5, delay: float = 2.0) -> None:
    """
    Connect to MongoDB with retries.

    Docker on Windows can fail the first Atlas SRV DNS lookup
    (_mongodb._tcp....) before the network is ready — retry avoids crash loops.
    """
    last_error: Exception | None = None

    for attempt in range(1, retries + 1):
        try:
            client = AsyncIOMotorClient(settings.MONGODB_URL)
            await client.admin.command("ping")
            db.client = client
            print("Connected to MongoDB")
            return
        except Exception as exc:
            last_error = exc
            try:
                client.close()
            except Exception:
                pass
            db.client = None
            if attempt < retries:
                print(
                    f"MongoDB connect attempt {attempt}/{retries} failed: {exc}. "
                    f"Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

    raise last_error  # type: ignore[misc]


async def close_mongo_connection():
    if db.client is not None:
        db.client.close()
        db.client = None
    print("Closed MongoDB connection")
