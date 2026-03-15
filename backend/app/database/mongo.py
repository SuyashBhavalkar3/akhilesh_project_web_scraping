from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")

client = None

def get_client() -> MongoClient:
    global client
    if client is None:
        client = MongoClient(MONGO_URI)
    return client

def close_client():
    global client
    if client is not None:
        try:
            client.close()
        finally:
            client = None

client = get_client()
db = client[MONGO_DB]