from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import time
import json
import re
import uuid
import os


class VijaySalesScraper:
    def _init_(self):
        self.driver = webdriver.Chrome()
        self.wait = WebDriverWait(self.driver, 15)

    def get_product_links(self, query, max_pages=25):
        links = []
        for page in range(1, max_pages + 1):
            url = f"https://www.vijaysales.com/search-listing?q={quote_plus(query)}&Page={page}"
            self.driver.get(url)
            try:
                self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.product-card__link")))
                time.sleep(2)
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                for card in soup.find_all("a", class_="product-card__link"):
                    href = card.get("href")
                    if href:
                        if not href.startswith("http"):
                            href = "https://www.vijaysales.com" + href
                        links.append(href)
            except Exception as e:
                print(f"Error getting product links on page {page}: {e}")
        return links

    def extract_mobile_features(self, psoup):
        features = {
            "type": "mobile",
            "details": {
                "storage": {
                    "ram": "",
                    "rom": ""
                },
                "design": {
                    "dimensions": "",
                    "weight": "",
                    "form_factor": "",
                    "stylus_support": "",
                    "color": ""
                },
                "display": {
                    "resolution": "",
                    "touchscreen": "",
                    "display_features": ""
                },
                "performance": {
                    "processor": "",
                    "cores": "",
                    "gpu": "",
                    "operating_system": "",
                    "model_number": ""
                },
                "network&connectivity": {
                    "wireless_tech": "",
                    "connectivity": "",
                    "gps": "",
                    "sim": "",
                    "mobile_hotspot": ""
                },
                "camera": {
                    "rear_camera": "",
                    "front_camera": "",
                    "camera_features": ""
                },
                "battery": {
                    "battery_capacity": "",
                    "battery_type": "",
                    "fast_charging": ""
                },
                "audio": {
                    "audio_jack": ""
                },
                "box_contents": {
                    "in_the_box": ""
                },
                "manufacturer": {
                    "brand": ""
                }
            }
        }

        spec_section = psoup.find("div", class_="accordionsinglepanel")
        raw_specs = {}

        if spec_section:
            for li in spec_section.find_all("li"):
                key_span = li.find("span", class_="panel-list-key")
                val_span = li.find("span", class_="panel-list-value")
                if key_span and val_span:
                    key = key_span.get_text(strip=True).upper()
                    val = val_span.get_text(strip=True)
                    raw_specs[key] = val

        features["details"]["storage"]["ram"] = raw_specs.get("RAM", "")
        features["details"]["storage"]["rom"] = raw_specs.get("INTERNAL STORAGE", "")
        features["details"]["manufacturer"]["brand"] = raw_specs.get("BRAND", "")
        features["details"]["display"]["resolution"] = raw_specs.get("SCREEN RESOLUTION", "")
        features["details"]["battery"]["battery_capacity"] = raw_specs.get("CAPACITY", "")
        features["details"]["display"]["touchscreen"] = "Yes" if "TOUCHSCREEN" in raw_specs else ""
        features["details"]["design"]["color"] = raw_specs.get("MODEL COLOR", "").capitalize()
        features["details"]["display"]["display_features"] = raw_specs.get("OTHER DISPLAY FEATURES", "")
        features["details"]["design"]["dimensions"] = raw_specs.get("PRODUCT DIMENSIONS(W X D X H)", "")
        features["details"]["design"]["weight"] = raw_specs.get("PRODUCT WEIGHT", "")
        features["details"]["performance"]["processor"] = raw_specs.get("PROCESSOR NAME", "")
        features["details"]["network&connectivity"]["sim"] = raw_specs.get("SIM TYPE", "")
        features["details"]["network&connectivity"]["connectivity"] = raw_specs.get("WI-FI", "")
        features["details"]["performance"]["operating_system"] = raw_specs.get("OS", "")
        features["details"]["performance"]["model_number"] = raw_specs.get("MODEL NAME", "")
        features["details"]["battery"]["fast_charging"] = raw_specs.get("QUICK CHARGING", "")
        features["details"]["camera"]["rear_camera"] = raw_specs.get("REAR CAMERA", "")
        features["details"]["camera"]["front_camera"] = raw_specs.get("FRONT CAMERA", "")
        features["details"]["camera"]["camera_features"] = raw_specs.get("REAR CAMERA FEATURES", "")
        features["details"]["audio"]["audio_jack"] = raw_specs.get("AUDIO JACK", "")
        features["details"]["design"]["form_factor"] = raw_specs.get("FORM FACTOR", "")
        features["details"]["box_contents"]["in_the_box"] = raw_specs.get("IN THE BOX", "")

        return features

    def extract_rating(self):
        try:
            rating_elem = self.driver.find_element(By.XPATH, '//*[@id="reviewBtn"]/p')
            rating_text = rating_elem.text.strip()
            if rating_text:
                rating = re.search(r"\d+(\.\d+)?", rating_text)
                return rating.group(0) if rating else ""
        except Exception:
            pass
        return ""

    def extract_image_url(self, psoup):
        image_block = psoup.find("div", class_="thumbnailList__root")
        urls = []

        if image_block:
            buttons = image_block.find_all("button")
            for btn in buttons:
                img_tag = btn.find("img", class_="thumbnail__image")
                if img_tag and img_tag.get("src"):
                    urls.append(img_tag["src"].strip())

        return {
            "thumbnail": urls[0] if urls else "",
            "urls": urls
        }

    def extract_product_details(self, product_url, category):
        result = {
            "product_id": str(uuid.uuid4()),
            "title": "N/A",
            "discounted_price": "N/A",
            "price": "N/A",
            # "image": {"thumbnail": "", "urls": []},
            "rating": "",
            "brand": "",
            "offers": [],
            # "features": {},
            "affilatelink": product_url,
            "category": category
        }

        try:
            self.driver.get(product_url)
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".productFullDetail__root")))
            time.sleep(2)

            psoup = BeautifulSoup(self.driver.page_source, "html.parser")

            title_el = psoup.find("h1", class_="productFullDetail__productName")
            price_el = psoup.find("p", class_="product__price--price offer")
            price_wrapper = psoup.find("p", class_="product__price--mrp offer")
            price_span = price_wrapper.find("span") if price_wrapper else None
            price = price_span.get_text(strip=True) if price_span else "N/A"

            result["title"] = title_el.get_text(strip=True) if title_el else "N/A"
            result["title"] = " ".join(result["title"].split()[:3]) if title_el else "N/A"
            result["price"] = price
            result["discounted_price"] = price_el.get_text(strip=True) if price_el else "N/A"
            result["brand"] = result["title"].split()[0] if title_el else "N/A"
            result["image"] = self.extract_image_url(psoup)
            result["rating"] = self.extract_rating()
            result["features"] = self.extract_mobile_features(psoup)

            offers_section = psoup.find_all("div", class_="product__price--deals-card")
            unique_offers = []
            seen_texts = set()

            for section in offers_section:
                for p in section.find_all(["p", "span", "div"]):
                    text = p.get_text(strip=True)
                    if text and "view details" not in text.lower() and text not in seen_texts:
                        seen_texts.add(text)
                        unique_offers.append(text)

            result["offers"] = unique_offers if unique_offers else ["No offers found"]

        except Exception as e:
            print(f"Error scraping product: {product_url} | {e}")

        return result

    def scrape_all_products_on_first_page(self, query, category):
        print(f"Searching for: {query}")
        product_links = self.get_product_links(query, max_pages=5)
        print(f"Found {len(product_links)} products")

        all_results = []
        for i, link in enumerate(product_links, 1):
            print(f"[{i}/{len(product_links)}] Scraping: {link}")
            details = self.extract_product_details(link, category)
            all_results.append(details)

        return all_results

    def save_to_json(self, data, filename):
        with open("vijaysales_mobile.json", 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("Saved data to vijaysales_mobile.json")

    def close(self):
        self.driver.quit()


if __name__ == "_main_":
    scraper = VijaySalesScraper()
    try:
        category = "smartphone"
        results = scraper.scrape_all_products_on_first_page("smartphone", category)
        scraper.save_to_json(results, 'vijaysales_mobile.json')
    finally:
        scraper.close()