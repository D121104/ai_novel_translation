import asyncio

from neo4j import GraphDatabase

from src.core.config import Settings


async def check(settings: Settings) -> bool:
    def ping() -> bool:
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password.get_secret_value()),
        )
        try:
            driver.verify_connectivity()
            return True
        finally:
            driver.close()

    return await asyncio.wait_for(asyncio.to_thread(ping), settings.health_timeout_seconds)
