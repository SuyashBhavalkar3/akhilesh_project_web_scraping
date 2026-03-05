from fastapi import FastAPI, Depends
from services.routes import router as chat_router
from fastapi.middleware.cors import CORSMiddleware
from utils. mongo import insert_json_to_mongo
import os

origins = ["*"]

app = FastAPI(
    title="Ecommerce api",
    description="Ecommerce api backend, with auto docs for the API and everything",
    version="0.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/ping")
async def ping():
    return {"res": True}

app.include_router(chat_router)

# Insert single JSON file into MongoDB on startup
@app.on_event("startup")
async def load_data_into_mongo():
    db_name = "ecommerce"
    collection_name = "ecommerce_data"
    json_path = "database\laptop\productlisting[1].json"

    if os.path.exists(json_path):
        try:
            await insert_json_to_mongo(json_path,db_name,collection_name)
            print(f" Data inserted from {json_path} into collection '{collection_name}'")
        except Exception as e:
            print(f" Failed to insert {json_path}: {e}")
    else:
        print(f"File not found: {json_path}")