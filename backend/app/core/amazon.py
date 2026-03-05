from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import pandas as pd
import time
import random
import re
import json
import uuid


class AmazonMobileScraper:
    def __init__(self, delay=3):
        self.delay = delay
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.6422.112 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.6478.57 Safari/537.36"
        ]

        options = Options()
        options.add_argument(f"user-agent={random.choice(self.user_agents)}")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)

        self.driver = webdriver.Chrome(options=options)
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        self.wait = WebDriverWait(self.driver, 10)

    def close(self):
        self.driver.quit()

    # ------------------------------
    # STEP 1: Collect Product URLs
    # ------------------------------
    def collect_product_urls(self, search_term, max_pages=1):
        product_urls = []

        for page in range(1, max_pages + 1):
            query = quote_plus(search_term)
            url = f"https://www.amazon.in/s?k={query}&page={page}"
            self.driver.get(url)

            self.wait.until(
                EC.presence_of_all_elements_located(
                    (By.XPATH, "//div[@data-component-type='s-search-result']")
                )
            )

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            cards = soup.find_all("div", {"data-component-type": "s-search-result"})

            for card in cards:
                link_tag = card.find("a", href=True)
                if not link_tag:
                    continue

                raw_href = link_tag["href"]
                match = re.search(r"/dp/[A-Z0-9]{10}", raw_href)
                if not match:
                    continue

                product_url = f"https://www.amazon.in{match.group()}"
                product_urls.append(product_url)

        return list(set(product_urls))  # remove duplicates

    # ------------------------------
    # STEP 2: Scrape Product Page
    # ------------------------------
    def scrape_product_page(self, product_url):
        try:
            self.driver.get(product_url)
            self.wait.until(EC.presence_of_element_located((By.ID, "productTitle")))
            soup = BeautifulSoup(self.driver.page_source, "html.parser")

            product_id = str(uuid.uuid4())

            # Title
            title_tag = soup.find("span", id="productTitle")
            raw_title = title_tag.get_text(strip=True) if title_tag else "N/A"
            product_name = " ".join(raw_title.split()[:3])
            brand = product_name.split()[0] if product_name else "N/A"

            # Price
            whole = soup.find("span", class_="a-price-whole")
            fraction = soup.find("span", class_="a-price-fraction")

            if whole:
                whole_price = whole.get_text(strip=True).replace(",", "")
                fraction_price = fraction.get_text(strip=True) if fraction else "00"
                discounted_price = f"₹{whole_price}.{fraction_price}"
            else:
                discounted_price = "N/A"

            actual_price_tag = soup.select_one("span.a-price.a-text-price span.a-offscreen")
            actual_price = actual_price_tag.get_text(strip=True) if actual_price_tag else "N/A"

            # Rating
            rating_tag = soup.select_one("span.a-icon-alt")
            rating = rating_tag.get_text(strip=True) if rating_tag else "N/A"

            # Images
            image_urls = set()
            dynamic_img = soup.select_one("[data-a-dynamic-image]")
            if dynamic_img:
                try:
                    images_dict = json.loads(dynamic_img["data-a-dynamic-image"])
                    sorted_imgs = sorted(images_dict.items(), key=lambda x: x[1][0], reverse=True)
                    for img_url, _ in sorted_imgs:
                        image_urls.add(img_url)
                except:
                    pass

            image_data = {
                "thumbnail": list(image_urls)[0] if image_urls else "N/A",
                "urls": list(image_urls)
            }

            return {
                "product_id": product_id,
                "title": raw_title,
                "product_name": product_name,
                "brand": brand,
                "actual_price": actual_price,
                "discounted_price": discounted_price,
                "rating": rating,
                "image_url": image_data,
                "affiliatelink": product_url,
                "category": "smartphone",
                "store": "Amazon"
            }

        except Exception as e:
            print(f"⚠ Error scraping {product_url}: {e}")
            return None

    # ------------------------------
    # MAIN SCRAPER FUNCTION
    # ------------------------------
    def scrape_mobiles(self, search_term="samsung mobile", max_pages=1):
        all_data = []

        print("Collecting product URLs...")
        product_urls = self.collect_product_urls(search_term, max_pages)
        print(f"Collected {len(product_urls)} URLs")

        for url in product_urls:
            data = self.scrape_product_page(url)
            if data:
                all_data.append(data)

            time.sleep(random.uniform(2, 5))  # human-like delay

        return all_data


# ------------------------------
# RUN SCRIPT
# ------------------------------
if __name__ == "__main__":
    scraper = AmazonMobileScraper()

    try:
        results = scraper.scrape_mobiles("samsung mobile", max_pages=1)
        df = pd.DataFrame(results)
        df.to_json(
            "amazon_mobilesamsung.json",
            orient="records",
            indent=2,
            force_ascii=False
        )
        print(df.head())

    finally:
        scraper.close()
