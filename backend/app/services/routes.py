import json
from typing import List, Optional, Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bson import ObjectId
from bson.errors import InvalidId

from database.mongo import client as mongo_client
from services.chatbot import chat_with_products

router = APIRouter()

DB_NAME = "ecommerce"
COLLECTION_NAME = "ecommerce_data"


# Convert ObjectId to string
def convert_objectid(document):
    if isinstance(document, dict):
        return {k: convert_objectid(v) for k, v in document.items()}
    elif isinstance(document, list):
        return [convert_objectid(item) for item in document]
    elif isinstance(document, ObjectId):
        return str(document)
    return document


class PaginatedResponse(BaseModel):
    status: str
    total_items: int
    page: int
    limit: int
    total_pages: int
    data: List[Any]


@router.get("/")
def read_root():
    return {"message": "Welcome to the E-commerce API!"}


@router.get("/productlisting")
def product_listing(
    category: Optional[str] = "",
    brand: Optional[str] = "",
    minPrice: Optional[float] = 0,
    maxPrice: Optional[float] = float("inf"),
    features: Optional[str] = "",
    query: Optional[str] = "",
    page: int = 1,
    limit: int = 24,
    sortby: int = -1
):
    try:
        collection = mongo_client[DB_NAME][COLLECTION_NAME]
        match_conditions = {}

        # Category filter
        if category:
            match_conditions["category"] = category.lower()

        # Brand filter
        if brand:
            match_conditions["brand"] = {
                "$in": [b.strip().lower() for b in brand.split(",")]
            }

        # Text search
        if query:
            match_conditions["$or"] = [
                {"title": {"$regex": query, "$options": "i"}}
            ]

        # Features filter
        try:
            features_dict = json.loads(features) if features else {}
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid features JSON format")

        if category:
            category = category.lower()

            if category == "smartphone":
                if "processor" in features_dict:
                    match_conditions["features.details.performance.processor"] = {
                        "$in": features_dict["processor"]
                    }

                if "ram" in features_dict:
                    match_conditions["features.details.storage.ram"] = {
                        "$in": features_dict["ram"]
                    }

                if "storage" in features_dict:
                    match_conditions["features.details.storage.rom"] = {
                        "$in": features_dict["storage"]
                    }

                if "operatingSystem" in features_dict:
                    match_conditions["features.details.performance.operating_system"] = {
                        "$in": features_dict["operatingSystem"]
                    }

            elif category == "laptop":
                if "processor" in features_dict:
                    match_conditions["features.details.performance.processor"] = {
                        "$in": features_dict["processor"]
                    }

                if "ram" in features_dict:
                    match_conditions["features.details.storage.ram"] = {
                        "$in": features_dict["ram"]
                    }

                if "storage" in features_dict:
                    match_conditions["features.details.storage.rom"] = {
                        "$in": features_dict["storage"]
                    }

        # Pagination
        skip = (page - 1) * limit

        # Query MongoDB
        cursor = collection.find(match_conditions).sort("discountprice", sortby)

        total_count = collection.count_documents(match_conditions)

        results = list(cursor.skip(skip).limit(limit))

        results = convert_objectid(results)

        return {
            "status": "success",
            "total_items": total_count,
            "page": page,
            "limit": limit,
            "total_pages": (total_count + limit - 1) // limit,
            "products": results
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/product/{mongo_id}")
def get_product(mongo_id: str):

    try:
        obj_id = ObjectId(mongo_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    collection = mongo_client[DB_NAME][COLLECTION_NAME]

    product = collection.find_one({
        "_id": obj_id,
        "image.thumbnail": {"$exists": True, "$ne": ""}
    })

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product = convert_objectid(product)

    return JSONResponse(content=product)


@router.get("/filters")
def get_filters():
    return {
        "categories": [
            "laptop",
            "laptop accessories",
            "smartphone",
            "mobile accessories"
        ],
        "sortoptions": [
            "Price: Low to High",
            "Price: High to Low"
        ],
        "pricerange": {
            "min": 199,
            "max": 199900
        }
    }


class ChatRequest(BaseModel):
    message: str
    history: List[dict] = []


@router.post("/chat")
def chat(request: ChatRequest):
    try:
        result = chat_with_products(request.message, request.history)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))