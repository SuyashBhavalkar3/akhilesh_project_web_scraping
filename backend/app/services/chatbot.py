import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from database.mongo import client as mongo_client
from bson import ObjectId

load_dotenv()

DB_NAME = os.getenv("MONGO_DB", "ecommerce")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "ecommerce_data")

openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


FILTER_PROMPT = """You are a filter extractor for an electronics store. Extract search filters from the user's query.
Return ONLY a valid JSON object with these optional fields:
{
  "category": "smartphone" | "laptop" | "laptop accessories" | "mobile accessories" | null,
  "brand": "brand name or null",
  "min_price": number or null,
  "max_price": number or null,
  "ram": "e.g. 8GB or null",
  "storage": "e.g. 128GB or null",
  "processor": "e.g. snapdragon or null",
  "query": "short keyword for title search or null"
}
Do not include any explanation outside the JSON."""


CHAT_PROMPT = """You are a helpful electronics store assistant for Vishal Sales.
Answer the customer's question using the product data provided.
Give a detailed, friendly, textual response covering:
- Product name and brand
- Price (original and discounted if available)
- Key specifications: RAM, storage, display, camera, battery, processor
- Available offers and bank discounts
- Rating if available
- Any notable features

If multiple products are found, summarize the top options and highlight differences.
If no products are found, politely say so and suggest the customer refine their search.
Keep the response conversational and helpful. Do not use markdown tables."""


def convert_objectid(doc):
    if isinstance(doc, dict):
        return {k: convert_objectid(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [convert_objectid(i) for i in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)
    return doc


def extract_intent(user_message: str) -> dict:
    response = openai_client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL"),
        messages=[
            {"role": "system", "content": FILTER_PROMPT},
            {"role": "user", "content": user_message}
        ],
        temperature=0,
        max_tokens=200,
        timeout=10
    )
    raw = response.choices[0].message.content.strip()
    return json.loads(raw)


def build_mongo_filter(intent: dict) -> dict:
    filters = {}

    if intent.get("category"):
        filters["category"] = intent["category"].lower()

    if intent.get("brand"):
        filters["brand"] = {"$regex": intent["brand"], "$options": "i"}

    min_p = intent.get("min_price")
    max_p = intent.get("max_price")
    if min_p is not None or max_p is not None:
        price_cond = {}
        if min_p is not None:
            price_cond["$gte"] = min_p
        if max_p is not None:
            price_cond["$lte"] = max_p
        filters["discounted_price"] = price_cond

    def make_regex(value: str) -> dict:
        # Normalize "8GB" -> "8" so it matches "8 GB RAM", "8GB", "8 gb" etc.
        number = "".join(filter(str.isdigit, value))
        pattern = number if number else value
        return {"$regex": pattern, "$options": "i"}

    and_conditions = []

    if intent.get("ram"):
        ram_regex = make_regex(intent["ram"])
        and_conditions.append({"$or": [
            {"features.details.storage.ram": ram_regex},
            {"features.details.Storage.RAM": ram_regex},
            {"title": {"$regex": intent["ram"].replace("GB", "").replace("gb", "").strip() + r"\s*gb\s*ram", "$options": "i"}},
        ]})

    if intent.get("storage"):
        rom_regex = make_regex(intent["storage"])
        and_conditions.append({"$or": [
            {"features.details.storage.rom": rom_regex},
            {"features.details.Storage.ROM": rom_regex},
            {"title": {"$regex": intent["storage"].replace("GB", "").replace("gb", "").strip() + r"\s*gb", "$options": "i"}},
        ]})

    if intent.get("processor"):
        proc_regex = {"$regex": intent["processor"], "$options": "i"}
        and_conditions.append({"$or": [
            {"features.details.performance.processor": proc_regex},
            {"features.details.Performance.processor": proc_regex},
            {"title": proc_regex},
        ]})

    if and_conditions:
        filters["$and"] = and_conditions

    if intent.get("query"):
        filters["title"] = {"$regex": intent["query"], "$options": "i"}

    return filters


def iget(d: dict, key: str, default="") -> str:
    """Case-insensitive dict lookup."""
    key_lower = key.lower()
    for k, v in d.items():
        if k.lower() == key_lower:
            return v or default
    return default


def format_product_summary(products: list) -> str:
    """Serialize only the relevant fields to keep the prompt concise."""
    summaries = []
    for p in products[:5]:
        details = p.get("features", {}).get("details", {}) or {}

        # Case-insensitive section lookup
        storage = iget(details, "storage") or {}
        performance = iget(details, "performance") or {}
        display = iget(details, "display") or {}
        camera = iget(details, "camera") or {}
        battery = iget(details, "battery") or {}

        # Handle thumbnail across all scraper schemas
        image_field = p.get("image") or p.get("image_url") or {}
        if isinstance(image_field, dict):
            thumbnail = image_field.get("thumbnail", "")
        elif isinstance(image_field, list):
            thumbnail = image_field[0] if image_field else ""
        else:
            thumbnail = str(image_field) if image_field else ""

        summary = {
            "title": p.get("title", ""),
            "brand": p.get("brand", ""),
            "price": p.get("price", ""),
            "discounted_price": p.get("discounted_price", ""),
            "rating": p.get("rating", ""),
            "thumbnail": thumbnail,
            "offers": p.get("offers", []),
            "specs": {
                "ram": iget(storage, "ram"),
                "storage": iget(storage, "rom"),
                "processor": iget(performance, "processor"),
                "os": iget(performance, "operating_system") or iget(performance, "operating system"),
                "display": iget(display, "resolution") or iget(display, "screen_resolution") or iget(display, "screen resolution"),
                "rear_camera": iget(camera, "rear_camera") or iget(camera, "rear camera"),
                "front_camera": iget(camera, "front_camera") or iget(camera, "front camera"),
                "battery": iget(battery, "battery_capacity") or iget(battery, "battery capacity"),
                "fast_charging": iget(battery, "fast_charging") or iget(battery, "fast charging"),
            }
        }
        summaries.append(summary)
    return json.dumps(summaries, indent=2)


def generate_chat_response(user_message: str, products: list, conversation_history: list) -> str:
    product_context = format_product_summary(products) if products else "No matching products found."

    messages = [{"role": "system", "content": CHAT_PROMPT}]
    for msg in conversation_history[-6:]:
        messages.append(msg)

    messages.append({
        "role": "user",
        "content": f"Customer question: {user_message}\n\nProduct data from our store:\n{product_context}"
    })

    response = openai_client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL"),
        messages=messages,
        temperature=0.7,
        max_tokens=800,
        timeout=15
    )
    return response.choices[0].message.content.strip()


def chat_with_products(user_message: str, conversation_history: list = []) -> dict:
    intent = extract_intent(user_message)
    mongo_filter = build_mongo_filter(intent)

    collection = mongo_client[DB_NAME][COLLECTION_NAME]
    products = list(collection.find(mongo_filter).limit(10))
    products = [convert_objectid(p) for p in products]

    # Fallback: title search using query or ram/brand keywords
    if not products:
        fallback_keyword = (
            intent.get("query")
            or intent.get("brand")
            or (intent.get("ram", "").replace("GB", "").replace("gb", "").strip() + " gb ram" if intent.get("ram") else None)
        )
        if fallback_keyword:
            fallback = {"title": {"$regex": fallback_keyword, "$options": "i"}}
            if intent.get("category"):
                fallback["category"] = intent["category"].lower()
            products = list(collection.find(fallback).limit(10))
            products = [convert_objectid(p) for p in products]

    chat_response = generate_chat_response(user_message, products, conversation_history)

    return {
        "message": chat_response,
        "products": products,
    }


def get_chatbot_response(message: str) -> str:
    """Simple chatbot response without OpenAI dependency"""
    message_lower = message.lower()
    
    # Simple keyword-based responses
    if any(word in message_lower for word in ['hello', 'hi', 'hey']):
        return "Hello! I'm here to help you find the perfect products. What are you looking for today?"
    
    if any(word in message_lower for word in ['laptop', 'computer']):
        return "Great! We have a wide range of laptops. Are you looking for gaming laptops, business laptops, or something else?"
    
    if any(word in message_lower for word in ['mobile', 'phone', 'smartphone']):
        return "We have excellent smartphones available! Are you interested in any particular brand like Samsung, Apple, or OnePlus?"
    
    if any(word in message_lower for word in ['price', 'cost', 'budget']):
        return "I can help you find products within your budget. What's your price range?"
    
    if any(word in message_lower for word in ['thank', 'thanks']):
        return "You're welcome! Feel free to ask if you need anything else."
    
    # Default response
    return "I'm here to help you find products! You can ask me about laptops, mobiles, accessories, or any specific brand you're interested in."
