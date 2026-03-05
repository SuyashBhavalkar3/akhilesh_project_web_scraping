from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient
import ssl
print(ssl.OPENSSL_VERSION)
import asyncio

import json

#  Use your MongoDB Atlas connection string
MONGO_URL = "MONGO_URI_REMOVED"

# Initialize MongoDB client and select database
client = AsyncIOMotorClient(MONGO_URL)
# db = client["ecommerce_db"]  

def get_collection(db_name,collection_name):
    db = client[db_name]
    return db[collection_name]

async def insert_json_to_mongo(json_path, db_name, collection_name):
    """Inserts data from a JSON file into the specified MongoDB collection
       only if the collection does not already exist."""
    db = client[db_name]

    #  Check if collection already exists
    if collection_name in db.list_collection_names():
        print(f"Collection '{collection_name}' already exists in database '{db_name}'. Skipping insertion.")
        return

    collection = db[collection_name]

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        collection.insert_many(data)
    else:
        collection.insert_one(data)