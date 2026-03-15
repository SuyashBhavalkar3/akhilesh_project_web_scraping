from pymongo import MongoClient

MONGO_URI = "MONGO_URI_REMOVED"
MONGO_DB = "ecommerce"

# Connect to MongoDB
client = MongoClient(MONGO_URI)

# Select database
db = client[MONGO_DB]

# List collections
collections = db.list_collection_names()
data=db[collections[0]].find_one() if collections else None
print("Collections:", collections)
print("Data:", data)