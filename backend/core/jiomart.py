import os
import time
import json
import uuid
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


class JioMartScraper:
    def __init__(self, headless=True, delay=2):
        self.delay = delay
        self.driver = self.create_driver(headless)
        self.wait = WebDriverWait(self.driver, 20)

    def create_driver(self, headless=True):
        options = webdriver.ChromeOptions()
        if headless:
            # options.add_argument("--headless=new")
            pass

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        return webdriver.Chrome(options=options)

    def extract_specifications(self, psoup):
        text = psoup.get_text(" ", strip=True).lower()
        specs = {"ram": "", "storage": "", "display": "", "camera": "", "battery": ""}

        ram_match = re.search(r'(\d+\s?gb\s?ram)', text)
        if ram_match:
            specs["ram"] = ram_match.group(1).upper()

        storage_match = re.search(r'(\d+\s?gb\s?(internal|rom|storage)[^.,]*)', text)
        expandable_match = re.search(r'(expandable[^.,]*)', text)
        storage_parts = []
        if storage_match:
            storage_parts.append(storage_match.group(1).strip().title())
        if expandable_match:
            storage_parts.append(expandable_match.group(1).strip().title())
        specs["storage"] = ", ".join(storage_parts)

        resolution = re.search(r'screen resolution[:\-]?\s*(\d+\s?[x×]\s?\d+)', text)
        screen_size = re.search(r'screen size.*?(\d{1,2}\.\d{1,2}\s?cm\s?-\s?\d{1,2}\.\d{1,2}\s?inch)', text)
        display_parts = []
        if resolution:
            display_parts.append(f"Resolution: {resolution.group(1).upper()}")
        if screen_size:
            display_parts.append(screen_size.group(1).title())
        specs["display"] = ", ".join(display_parts)

        rear = re.search(r'rear camera[:\-]?\s*(\d+\s?mp)', text)
        front = re.search(r'front camera[:\-]?\s*(\d+\s?mp)', text)
        rear_text = rear.group(1).upper() if rear else ""
        front_text = front.group(1).upper() if front else ""
        if rear_text and front_text:
            specs["camera"] = f"Rear {rear_text} | Front {front_text}"
        elif rear_text:
            specs["camera"] = f"Rear {rear_text}"
        elif front_text:
            specs["camera"] = f"Front {front_text}"

        battery_match = re.search(r'(\d{4,5}\s?mah)', text)
        if battery_match:
            specs["battery"] = battery_match.group(1).upper()

        return specs

    def extract_image_url(self, psoup):
        image_block = psoup.select_one(
            "body > main > section > section.pdp-content > div.jm-mt-m > div.jm-row > div:nth-child(1) > div > div.product-media > div.product-image-carousel > div.product-image-carousel-thumb.jm-mr-base > div.swiper.swiper-thumb.swiper-initialized.swiper-vertical.swiper-pointer-events.swiper-backface-hidden.swiper-thumbs"
        )
        urls = []

        if image_block:
            thumbs = image_block.select("div.swiper-slide")
            for thumb in thumbs:
                img_tag = thumb.select_one("img.swiper-thumb-slides-img")
                if img_tag and img_tag.get("src"):
                    urls.append(img_tag["src"].strip())

        return {
            "thumbnail": urls[0] if urls else "",
            "urls": urls
        }

    def extract_offers(self, offer_section):
        offers = []
        current_section = None
        for element in offer_section.find_all(["div", "h4", "p", "li", "span"]):
            text = element.get_text(strip=True)
            if not text:
                continue
            if text.upper().endswith("OFFERS") and "AVAILABLE" not in text.upper():
                current_section = text.title().replace(" ", "_")
            elif current_section and "Offer/s Available" not in text and "View All" not in text:
                if text not in offers:
                    offers.append(text)
        return offers

    def extract_rating(self, psoup):
        try:
            rating_container = psoup.find("div", class_="feedback-service-rating-content")
            if rating_container:
                inner_div = rating_container.find("div")
                if inner_div:
                    rating_span = inner_div.find("span", class_="feedback-service-avg-rating-font feedback-service-top-text")
                    if rating_span:
                        return rating_span.get_text(strip=True)
        except Exception:
            pass
        return ""

    def extract_mobile_features(self, psoup):
        features = {
            "type": "mobile",
            "details": {
                "Storage": {"RAM": "", "ROM": ""},
                "Design": {"Dimensions": "", "Weight": "", "Form Factor": "", "Stylus Support": "", "Color": ""},
                "Display": {"Screen Size": "", "Screen Resolution": "", "Touch Screen": "", "Display Features": ""},
                "Performance": {"Processor": "", "Cores": "", "GPU": "", "Operating System": "", "Model Number": ""},
                "Network & Connectivity": {"Wireless Tech": "", "Connectivity": "", "GPS": "", "SIM": "", "Mobile Hotspot": ""},
                "Camera": {"Rear Camera": "", "Front Camera": "", "Camera Features": ""},
                "Battery": {"Battery Capacity": "", "Battery Type": "", "Fast Charging": ""},
                "Audio": {"Audio Jack": ""},
                "Box Contents": {"In the Box": ""},
                "Manufacturer": {"Brand": ""}
            }
        }

        specs_section = psoup.find("section", class_="product-specifications border-default jm-pt-m jm-pb-base")
        raw_specs = {}
        if specs_section:
            for tr in specs_section.find_all("tr", class_="product-specifications-table-item"):
                th = tr.find("th", class_="product-specifications-table-item-header")
                td = tr.find("td", class_="product-specifications-table-item-data")
                if th and td:
                    raw_specs[th.get_text(strip=True).upper()] = td.get_text(strip=True)

        f = features["details"]
        f["Storage"]["RAM"] = raw_specs.get("MEMORY (RAM)", "")
        f["Storage"]["ROM"] = raw_specs.get("INTERNAL STORAGE", "")
        f["Manufacturer"]["Brand"] = raw_specs.get("BRAND", "")
        f["Display"]["Screen Resolution"] = raw_specs.get("SCREEN RESOLUTION", "")
        f["Display"]["Screen Size"] = raw_specs.get("SCREEN SIZE (DIAGONAL)", "")
        f["Battery"]["Battery Capacity"] = raw_specs.get("BATTERY CAPACITY", "")
        f["Display"]["Touch Screen"] = "Yes" if "TOUCHSCREEN" in raw_specs else ""
        f["Design"]["Color"] = raw_specs.get("COLOR", "").capitalize()
        f["Display"]["Display Features"] = raw_specs.get("DISPLAY TYPE", "")
        f["Design"]["Dimensions"] = raw_specs.get("DIMENSIONS", "")
        f["Design"]["Weight"] = raw_specs.get("NET WEIGHT", "")
        f["Performance"]["Processor"] = raw_specs.get("PROCESSOR", "")
        f["Performance"]["Cores"] = raw_specs.get("CORES", "")
        f["Performance"]["GPU"] = raw_specs.get("GPU", "")
        f["Network & Connectivity"]["SIM"] = raw_specs.get("SIM TYPE", "")
        f["Network & Connectivity"]["Connectivity"] = raw_specs.get("BLUETOOTH", "")
        f["Network & Connectivity"]["GPS"] = raw_specs.get("GPS", "")
        f["Network & Connectivity"]["Mobile Hotspot"] = raw_specs.get("WI-FI", "")
        f["Performance"]["Operating System"] = raw_specs.get("OPERATING SYSTEM", "")
        f["Performance"]["Model Number"] = raw_specs.get("MODEL", "")
        f["Battery"]["Fast Charging"] = raw_specs.get("QUICK CHARGE", "")
        f["Battery"]["Battery Type"] = raw_specs.get("BATTERY TYPE", "")
        f["Camera"]["Rear Camera"] = raw_specs.get("REAR CAMERA", "")
        f["Camera"]["Front Camera"] = raw_specs.get("SELFIE CAMERA", "")
        f["Camera"]["Camera Features"] = raw_specs.get("CAMERA FEATURES", "")
        f["Audio"]["Audio Jack"] = raw_specs.get("AUDIO JACK", "")
        f["Design"]["Form Factor"] = raw_specs.get("FORM FACTOR", "")
        f["Box Contents"]["In the Box"] = raw_specs.get("IN THE BOX", "")

        return features

    def scrape_products(self, max_scrolls=80):
        self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ais-InfiniteHits-item")))

        products = []
        last_count = 0
        product_selector = "li.ais-InfiniteHits-item"

        for _ in range(max_scrolls):
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(self.delay)
            new_count = len(self.driver.find_elements(By.CSS_SELECTOR, product_selector))
            if new_count == last_count:
                break
            last_count = new_count

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        product_items = soup.select(product_selector)

        for item in product_items:
            title_tag = item.find("div", class_="plp-card-details-name")
            price_tag = item.find("span", class_="jm-heading-xxs")
            actual_price_tag = item.find("span", class_="line-through")
            a_tag = item.find("a", href=True)
            title = title_tag.get_text(strip=True) if title_tag else "N/A"
            if "ram" not in title.lower():
                continue

            product_name = " ".join(title.split(" ", 3)[0:3])
            print(f"Processing product: {product_name}")
            brand = product_name.split()[0] if product_name else " "
            print(f"Extracted brand: {brand}")
            product_url = "https://www.jiomart.com" + a_tag['href'] if a_tag else None
            print(f"Extracted URL: {product_url}")

            if not product_url:
                continue

            product_id = str(uuid.uuid4())
            discounted_price = price_tag.text.strip() if price_tag else "N/A"
            print(f"Extracted price: {discounted_price}")
            actual_price = actual_price_tag.get_text(strip=True) if actual_price_tag else discounted_price
            print(f"Extracted actual price: {actual_price}")
            try:
                self.driver.get(product_url)
                time.sleep(self.delay)
                psoup = BeautifulSoup(self.driver.page_source, "html.parser")
                offer_section = psoup.find("div", class_="product-offers-list jm-mb-xs")
                offers = self.extract_offers(offer_section) if offer_section else []
                print(f"Extracted offers: {offers}")
                rating = self.extract_rating(psoup)
                print(f"Extracted rating: {rating}")
                image = self.extract_image_url(psoup)
                print(f"Extracted image URL: {image['thumbnail']}")
                features = self.extract_mobile_features(psoup)
                print(f"Extracted features: {features['details']['Storage']}")
                specifications = self.extract_specifications(psoup)
                print(f"Extracted specifications: {specifications}")

                if specifications["ram"]:
                    features["details"]["Storage"]["RAM"] = specifications["ram"]
                if specifications["storage"]:
                    features["details"]["Storage"]["ROM"] = specifications["storage"]
            except Exception as e:
                print(f"Error loading product page: {e}")
                continue

            products.append({
                "product_id": product_id,
                "title": product_name,
                "discounted_price": discounted_price,
                "price": actual_price,
                "image": image,
                "rating": rating,
                "brand": brand,
                "offers": offers,
                "features": features,
                "affiliatelink": product_url,
                "category": "smartphone"
            })

        return products

    def save_to_json(self, data, filename=None):
        if not filename:
            filename = os.path.join(os.path.dirname(__file__), "jiomart_mobile.json")
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    brand_list = ['samsung mobiles']
    max_scrolls = 60
    all_products = []

    for brand in brand_list:
        print(f"\nScraping brand: {brand}")
        scraper = JioMartScraper(headless=False)
        brand_url = f"https://www.jiomart.com/search/{brand}"
        scraper.driver.get(brand_url)
        time.sleep(scraper.delay)

        try:
            products = scraper.scrape_products(max_scrolls=max_scrolls)
            all_products.extend(products)
        except Exception as e:
            print(f" Failed to scrape brand '{brand}': {e}")
        finally:
            scraper.close()

    output_file = os.path.join(os.path.dirname(__file__), "jiomart_mobile.json")
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_products, f, indent=4, ensure_ascii=False)

    print(f"\n Scraping complete. Total products scraped: {len(all_products)}")