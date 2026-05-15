import asyncio
import os

from dotenv import load_dotenv, find_dotenv
from pymongo import AsyncMongoClient

from app.core.config import get_settings


async def main():
    env_file = find_dotenv(get_settings().Config.env_file)
    load_dotenv(env_file)

    uri = os.getenv("MONGODB_URI")
    client = AsyncMongoClient(uri)

    try:
        database = client.get_database(os.getenv("MONGODB_DB_NAME"))
        movies = database.get_collection("movies")

        # Query for a movie that has the title 'Scarface'
        query = {"title": "Scarface"}
        movie = await movies.find_one(query)

        print(movie)

        # await client.admin.command("ping")
        # print("Pinged your deployment. You successfully connected to MongoDB!")

        await client.close()

    except Exception as e:
        raise Exception("Unable to find the document due to the following error: ", e)

# Run the async function
asyncio.run(main())