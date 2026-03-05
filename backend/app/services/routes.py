import os
from fastapi import FastAPI, APIRouter
from utils.mongo import client as mongo_client
from pydantic import BaseModel
from typing import List, Optional, Any
from pymongo import ASCENDING, DESCENDING
from fastapi.responses import JSONResponse

import json
from fastapi import Query, HTTPException
from .task import load_all_data_json
import re
import traceback
from bson import ObjectId
from bson.errors import InvalidId

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

router = APIRouter()
DB_NAME = "ecommerce"
COLLECTION_NAME = "ecommerce_data"
# collection_name = get_collection(DB_NAME, COLLECTION_NAME)



@router.get("/")
def read_root():
    return {"message": "Welcome to the E-commerce API!"}


def ensure_serializable(data: Any):
    if isinstance(data, list):
        return [ensure_serializable(item) for item in data]
    elif isinstance(data, dict):
        return {k: ensure_serializable(v) for k, v in data.items()}
    elif isinstance(data, (int, float, str, bool)) or data is None:
        return data
    else:
        return str(data)

@router.get("/productlisting")
async def product_listing(
    category: Optional[str] = "",
    brand: Optional[str] = "",
    minPrice: Optional[float] = 0,
    maxPrice: Optional[float] = float("inf"),
    features: Optional[str] = {},
    query: Optional[str] = "",
    page: int = 1,
    limit: int = 24,
    sortby: Optional[int] = -1 #dfault is -1 for descending order
):
    try:
        collection = mongo_client[DB_NAME][COLLECTION_NAME]
        match_conditions = {}

        
        if category:
            match_conditions["category"] = category.lower()

      
        if brand:
            match_conditions["brand"] = {"$in": [b.strip().lower() for b in brand.split(",")]}

        # Price filter for all products
        # match_conditions["vendorsdiscountprice"] = {"$gte": minPrice, "$lte": maxPrice}

        if image_thumbnail := match_conditions.get("image.thumbnail"):
            if isinstance(image_thumbnail, dict):
                image_thumbnail["$exists"] = True
                image_thumbnail["$ne"] = ""
            else:
                match_conditions["image.thumbnail"] = {"$exists": True, "$ne": ""}
 
        # Text search
        if query:
            match_conditions["$or"] = [
                {"title": {"$regex": query, "$options": "i"}},
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
                    match_conditions["features.details.performance.processor"] = {"$in": features_dict["processor"]}
                if "ram" in features_dict:
                    match_conditions["features.details.storage.ram"] = {"$in": features_dict["ram"]}
                if "storage" in features_dict:
                    match_conditions["features.details.storage.rom"] = {"$in": features_dict["storage"]}
                if "dimensions" in features_dict:
                    match_conditions["features.details.display.dimensions"] = {"$in": features_dict["dimensions"]}
                if "operatingSystem" in features_dict:
                    match_conditions["features.details.performance.operating_system"] = {"$in": features_dict["operatingSystem"]}
                if "camera_features" in features_dict:
                    match_conditions["features.details.camera.camera_features"] = {"$in": features_dict["camera_features"]}

            elif category == "laptop":
                if "processor" in features_dict:
                    match_conditions["features.details.performance.processor"] = {"$in": features_dict["processor"]}
                if "ram" in features_dict:
                    match_conditions["features.details.storage.ram"] = {"$in": features_dict["ram"]}
                if "storage" in features_dict:
                    match_conditions["features.details.storage.rom"] = {"$in": features_dict["storage"]}
                if "screenSize" in features_dict:
                    match_conditions["features.details.display.screen_size"] = {"$in": features_dict["screenSize"]}
                if "operatingSystem" in features_dict:
                    match_conditions["features.details.performance.operating_system"] = {"$in": features_dict["operatingSystem"]}
                if "features" in features_dict:
                    match_conditions["features.features"] = {"$in": features_dict["features"]}

            elif category == "mobile accessories":
                if "type" in features_dict:
                    match_conditions["features.type"] = {"$in": features_dict["type"]}
                if "connectivity" in features_dict:
                    match_conditions["features.details.general.connectivity"] = {
                        "$regex": "|".join(features_dict["connectivity"]),
                        "$options": "i"
                    }
                if "description" in features_dict:
                    match_conditions["features.details.general.description"] = {
                        "$regex": "|".join(features_dict["description"]),
                        "$options": "i"
                    }

            elif category == "laptop accessories":
                if "type" in features_dict:
                    match_conditions["features.type"] = {"$in": features_dict["type"]}
                if "connectivity" in features_dict:
                    match_conditions["features.details.general.connectivity"] = {
                        "$regex": "|".join(features_dict["connectivity"]),
                        "$options": "i"
                    }
                if "description" in features_dict:
                    match_conditions["features.details.general.description"] = {
                        "$regex": "|".join(features_dict["description"]),
                        "$options": "i"
                    }

        elif features_dict:
            # Generic feature filter if no category is given
            for key, value in features_dict.items():
                if isinstance(value, dict):
                    for sub_key, sub_val in value.items():
                        if sub_val:
                            match_conditions[f"features.details.{key}.{sub_key}"] = {"$regex": sub_val, "$options": "i"}
                elif isinstance(value, list):
                    match_conditions[f"features.{key}"] = {"$in": value}
                elif isinstance(value, str):
                    match_conditions[f"features.{key}"] = {"$regex": value, "$options": "i"}

        # Pagination and Sorting
        skip = (page - 1) * limit
        sort_order = [("discountprice", sortby)] if sortby else None

        cursor = collection.find(match_conditions)
        if sort_order:
            cursor = cursor.sort(sort_order)

        total_count = await collection.count_documents(match_conditions)
        results = await cursor.skip(skip).limit(limit).to_list(length=limit)

        return {
            "total": total_count,
            "page": page,
            "limit": limit,
            "products": [{**product, "_id": str(product["_id"])} for product in results]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/product/{mongo_id}")
async def get_product(mongo_id: str):
    try:
        obj_id = ObjectId(mongo_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid ObjectId format")

    collection = mongo_client[DB_NAME][COLLECTION_NAME]

    
    product = await collection.find_one({
        "_id": obj_id,
        "image.thumbnail": {"$exists": True, "$ne": ""}
    })

    if not product:
        raise HTTPException(status_code=404, detail="Product not found or image missing")

    # Convert ObjectId to string
    product["_id"] = str(product["_id"])

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
        "brand": [
            "Apple", "Samsung", "OnePlus", "Xiaomi", "Realme", "HP", "Dell", "Lenovo",
            "Acer", "ASUS", "boAt", "Zebronics", "Portronics", "Noise", "Fire-Boltt",
            "Logitech", "Cosmic Byte", "GenericBrand", "pTron", "JBL", "Sony", "Boult",
            "Infinix", "Redmi","Nothing","Google","Oppo","Vivo"
        ],
        "pricerange": {
            "min": 199,
            "max": 199900.00, #need to change in future 
        },
        "ratings": [
            1.0, 2.0, 2.5, 3.0, 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9,
            4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8, 4.9, 5.0
        ],
        "sortoptions": [
            "Price: Low to High",
            "Price: High to Low",
           
        ],
        "specificfilters": {
            "smartphone": {
                "processor": [
                    "Apple M1", "Apple M2", "Apple M3", "Snapdragon 8 Gen 2",
                    "Snapdragon 8 Gen 3", "Snapdragon 7+ Gen 2",
                    "MediaTek Dimensity 9200", "MediaTek Dimensity 8200",
                    "MediaTek Helio G99", "Exynos 2100", "snapdragon 695",
                    "Snapdragon 870", "Unisoc T610"
                ],
                "storage": ["64 GB", "128 GB", "256 GB", "512 GB", "1 TB"],
                "ram": ["4 GB", "6 GB", "8 GB", "12 GB", "16 GB"],
                # "screenSize": ["<6 inch", "6-6.5 inch", ">6.5 inch", "Foldable"],
                "operating_system": ["Android", "iOS"],
                "features": [
                    "5G Capable", "Dual SIM", "Fast Charging", "Water Resistant",
                    "NFC", "Wireless Charging"
                ],
                "camerafeatures": [
                    "dual camera", "Triple Camera", "Quad Camera",
                    "Optical Zoom", "Ultrawide Lens"
                ],
                "brand":["Apple", "Samsung", "OnePlus", "Xiaomi", "Realme","Redmi","Infinix","Sony","Nothing","Google","Oppo","Vivo"],
            },
            "laptop accessories": {
                "accessorytype": [
                    "mouse", "keyboard", "external hard drive",
                    "docking station", "laptop stand", "webcam"
                ],
                "connectivity": ["USB", "bluetooth", "wireless (2.4GHz)"],
                "compatibility": ["Universal", "Mac Compatible", "Windows Compatible"],
                "features": ["Ergonomic", "Gaming Optimized", "Portable"],
                "brand":[
                    "ASUS",
                    "ZEBRONICS",
                    "Portronics",
                    "Logitech",
                    "HP",
                    "Lenovo",
                    "Quantum",
                    "AmazonBasics",
                    "iBall",
                    "Amkette",
                    "Redragon",
                    "Lapcare",
                    "Dell",
                    "Targus",
                    "Frontech",
                    "Tukzer",
                    "Cosmic Byte",
                    "Live Tech",
                    "Intex",
                    "Artis",
                    "Flipkart SmartBuy",
                    "Foxin",
                    "TechNet",
                    "TeckNet",
                    "Belkin",
                    "Fingers"
                ],
            },
            "mobile accessories": {
                "accessorytype": [
                    "Cases & Covers", "Screen Protectors", "Chargers & Cables",
                    "Power Banks", "Gimbals & Tripods", "Car Mounts"
                ],
                "compatibility": ["iPhone", "Android (USB-C)", "Android (Micro USB)"],
                "features": [
                    "Fast Charging", "MagSafe Compatible", "Wireless Charging Compatible"
                ],
                "material": ["Silicone", "Leather", "Hard Plastic", "Tempered Glass"],
                "brand" :[
                    "boAt",
                    "realme",
                    "Samsung",
                    "MI",
                    "Apple",
                    "Ambrane",
                    "Portronics",
                    "Noise",
                    "Boult Audio",
                    "OnePlus",
                    "Zebronics",
                    "OPPO",
                    "pTron",
                    "Mivi",
                    "Spigen",
                    "Stuffcool",
                    "Flipkart SmartBuy",
                    "URBN",
                    "Belkin",
                    "iBall",
                    "Anker",
                    "Callmate",
                    "Molife",
                    "Ubon",
                    "Vivo",
                    "Inbase",
                    "Infinix",
                    "Itel"
                ],
            },
            "laptop": {
                "processor": [
                    "Intel Core i3", "Intel Core i5", "Intel Core i7", "Intel Core i9",
                    "AMD Ryzen 3", "AMD Ryzen 5", "AMD Ryzen 7", "AMD Ryzen 9",
                    "Apple M1", "Apple M2", "Apple M3"
                ],
                "ram": ["4 GB", "8 GB", "16 GB", "32 GB", "64 GB"],
                # "storageType": ["SSD", "HDD", "Hybrid"],
                "storagecapacity": ["256 GB", "512 GB", "1 TB", "2 TB", "4 TB"],
                "screen_size": ["<13 inch", "13-14 inch", "15-16 inch", "17+ inch"],
                "graphicscard": ["Integrated", "Dedicated (NVIDIA)", "Dedicated (AMD)"],
                "operating_system": ["Windows", "macOS", "Linux", "Chrome OS"],
                "features": ["Touchscreen", "2-in-1", "Backlit Keyboard", "Fingerprint Reader"],
                "brand" : [
                    "ASUS",
                    "HP",
                    "Dell",
                    "Lenovo",
                    "Acer",
                    "MSI",
                    "Apple",
                    "Infinix",
                    "Avita",
                    "Samsung",
                    "Honor",
                    "LG",
                    "Nokia",
                    "Chuwi",
                    "Fujitsu",
                    "Realme",
                    "Primebook"
                ],
            }
        }
    }