import time
import json
import uuid
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from pprint import pprint


class CromaScraper:
    def __init__(self, delay=2, headless=False):
        self.delay = delay
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--log-level=3")

        try:
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, 10)
        except Exception as e:
            print(f"Failed to launch browser: {e}")
            exit()

    def click_all_view_more_buttons(self):
        while True:
            try:
                view_more = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'View More')]"))
                )
                if view_more.is_displayed():
                    print(" Clicking 'View More'...")
                    self.driver.execute_script("arguments[0].click();", view_more)
                    time.sleep(self.delay)
                else:
                    break
            except Exception:
                print("No more 'View More' button or it's not clickable.")
                break

    def map_raw_to_features(self, raw):
        return {
            "type": "mobile",
            "details": {
                "design": {
                    "dimensions": raw.get("Dimensions In CM (WxDxH)", ""),
                    "weight": raw.get("Main Unit Weight", ""),
                    "form_factor": raw.get("Mobile Design", ""),
                    "stylus_support": raw.get("Stylus Support", ""),
                    "color": raw.get("Color", raw.get("Brand Color", ""))
                },
                "display": {
                    "resolution": raw.get("Screen Resolution", ""),
                    "touchscreen": raw.get("Screen Type", ""),
                    "display_features": f"Refresh Rate: {raw.get('Refresh Rate', '')} | Brightness: {raw.get('Brightness', '')}"
                },
                "network&connectivity": {
                    "wireless_tech": raw.get("Cellular Technology", ""),
                    "connectivity": f"Wi-Fi: {raw.get('Wi-Fi Supported', '')}, Bluetooth: {raw.get('Bluetooth Specifications', '')}",
                    "gps": raw.get("Smart Sensors", ""),
                    "sim": raw.get("SIM Type", ""),
                    "mobilehotspot": raw.get("Wi-Fi Features", "")
                },
                "performance": {
                    "Operating System": f"{raw.get('OS Name & Version', '')} ({raw.get('OS Type', '')})",
                    "Model Number": raw.get("Model Number", ""),
                    "processor": f"{raw.get('Processor Name', '')} ({raw.get('Processor Brand', '')})"
                },
                "storage": {
                    "ram": raw.get("RAM", ""),
                    "rom": raw.get("Internal Storage", "")
                },
                "camera": {
                    "rear_camera": raw.get("Rear Camera", ""),
                    "front_camera": raw.get("Front Camera", ""),
                    "camera_features": raw.get("Camera Features", "")
                },
                "battery": {
                    "battery_capacity": raw.get("Battery Capacity", ""),
                    "battery_type": raw.get("Battery Type", ""),
                    "fast_charging": raw.get("Fast Charging Capability", "")
                },
                "audio": {
                    "audio_jack": raw.get("Audio Jack Port", "")
                },
                "box_contents": {
                    "in_the_box": raw.get("Package Includes", raw.get("Main product", ""))
                },
                "manufacturer": {
                    "brand": raw.get("Brand", "")
                }
            }
        }

    def get_specifications(self, url):
        self.driver.get(url)
        time.sleep(3)

        try:
            view_more_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[@id='specification']//button[contains(text(), 'View More')]")))
            self.driver.execute_script("arguments[0].click();", view_more_btn)
            time.sleep(2)
        except:
            print("No 'View More' button found or already expanded.")

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        spec_block = soup.find("div", id="specification_container")
        raw_specs = {}

        if spec_block:
            categories = spec_block.find_all("ul", class_="cp-specification-info")
            for spec in categories:
                labels = spec.find_all("li", class_="cp-specification-spec-title")
                values = spec.find_all("li", class_="cp-specification-spec-details")

                for lbl, val in zip(labels, values):
                    key = lbl.get_text(strip=True)
                    value = val.get_text(strip=True)
                    if key:
                        raw_specs[key] = value

        return self.map_raw_to_features(raw_specs)

    def scrape_all_products(self, search_query: str) -> list:
        all_products = []

        try:
            self.driver.get("https://www.croma.com/")
            search_box = self.wait.until(EC.presence_of_element_located((By.ID, "searchV2")))
            search_box.clear()
            search_box.send_keys(search_query)
            search_box.send_keys(Keys.RETURN)
        except Exception as e:
            print(f" Error during search: {e}")
            self.driver.quit()
            return []

        time.sleep(self.delay)
        self.click_all_view_more_buttons()

        soup = BeautifulSoup(self.driver.page_source, "html.parser")
        product_cards = soup.find_all("li", class_="product-item")

        if not product_cards:
            print("⚠ No products found.")
            self.driver.quit()
            return []

        print(f" Found {len(product_cards)} products.")

        for idx, card in enumerate(product_cards, start=1):
            a_tag = card.find("a", href=True)
            title_tag = card.find("h3", class_="product-title")

            if not a_tag or not title_tag:
                continue

            product_url = "https://www.croma.com" + a_tag['href']
            product_title = title_tag.text.strip()
            print(f"[{idx}] Scraping: {product_title}")
            print(f"     URL: {product_url}")

            try:
                self.driver.get(product_url)
                time.sleep(self.delay)

                psoup = BeautifulSoup(self.driver.page_source, "html.parser")
                product_id = str(uuid.uuid4())

                title_tag = psoup.find("h1", class_="pd-title pd-title-normal")
                price_tag = psoup.find("span", class_="amount")
                actual_price_tag = psoup.find("span", class_="old-price")
                try:
                    rating_elem = self.driver.find_element(
                        By.CSS_SELECTOR,
                        "#pdpdatael > div.cp-section.banner-spacing.show-pdp-icon > div.container > div > div > div > div.col-md-6.right-alignElement > div > ul > li > div.cp-rating > span:nth-child(1) > span"
    
                    )
                    
                    rating = rating_elem.text.strip()
                    print(rating)
                except Exception:
                    try:
                        rating_elem = psoup.find("div",class_="cp-rating")
                        rating = rating_elem.text.strip()
                        print(rating)
                    except Exception:
                        rating = "N/A"
                title = title_tag.text.strip() if title_tag else product_title
                brand = title.split()[0] if title else "N/A"
                print(f"Brand.................: {brand}")
                short_title = " ".join(title.split()[:3])
                price = price_tag.text.strip() if price_tag else "Price not found"
                actual_price = actual_price_tag.get_text(strip=True) if actual_price_tag else "Not found"

                image_urls = []
                seen_urls = set()
                max_slides = 10

                for _ in range(max_slides):
                    try:
                        active_img = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "swiper-slide-active")))
                        img_tag = active_img.find_element(By.TAG_NAME, "img")
                        img_url = img_tag.get_attribute("data-src") or img_tag.get_attribute("src")
                        if img_url and img_url not in seen_urls:
                            image_urls.append(img_url)
                            seen_urls.add(img_url)
                        else:
                            break

                        next_btn = self.driver.find_element(By.CLASS_NAME, "swiper-button-next")
                        if next_btn.is_displayed() and next_btn.is_enabled():
                            self.driver.execute_script("arguments[0].click();", next_btn)
                            time.sleep(1)
                        else:
                            break

                    except Exception as e:
                        print("⚠️ Carousel ended or error:", e)
                        break

                for i, url in enumerate(image_urls):
                    print(f"Image {i+1}: {url}")

                offers = set()
                offer_section = psoup.find("div", class_="offer-section-pdp")
                if offer_section:
                    offer_blocks = offer_section.find_all("div", recursive=True)
                    for block in offer_blocks:
                        title_elem = block.find("span", class_="bank-name-text")
                        value_elem = block.find("span", class_="bank-offers-text-pdp-carousel")
                        if title_elem and value_elem:
                            offer_text = f"{title_elem.get_text(strip=True)} - {value_elem.get_text(strip=True)}"
                            offers.add(offer_text)
                offers=list(offers)            

                specifications = self.get_specifications(product_url)
                print(specifications)

                product_data = {
                    "vendor": "croma",
                    "product": {
                        "product_id": product_id,
                        "product_name": short_title,
                        "brand": brand,
                        "price": actual_price,
                        "discounted_Price": price,
                        "rating": rating,
                        "offers": offers,
                        "specifications": specifications,
                        "affiliatelink": product_url,
                        "image_url": image_urls,
                        "category": "smartphone"
                    }
                }

                all_products.append(product_data)

            except Exception as detail_err:
                print(f"⚠ Error scraping {product_title}: {detail_err}")

        self.driver.quit()
        return all_products

    def save_to_json(self, croma_data, filename="cromamobiles.json"):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(croma_data, f, indent=4, ensure_ascii=False)
            print(f" Data saved to {filename}")
        except Exception as e:
            print(f" Failed to save JSON: {e}")

    def close(self):
        self.driver.quit()


if __name__ == "__main__":
    scraper = CromaScraper(headless=False)
    results = scraper.scrape_all_products("iphone 16")
    scraper.save_to_json(results)
