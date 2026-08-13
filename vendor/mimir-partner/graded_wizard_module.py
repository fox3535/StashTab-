import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
import urllib.parse
import urllib.request
import json
import re
import statistics
from bs4 import BeautifulSoup
from PIL import Image
import os
import undetected_chromedriver as uc

def get_chrome_major_version():
    try:
        import subprocess
        exe = uc.find_chrome_executable()
        path = exe.replace('\\', '\\\\')
        output = subprocess.check_output(f'wmic datafile where name="{path}" get Version', shell=True).decode()
        match = re.search(r'(\d+)\.', output)
        if match:
            return int(match.group(1))
    except Exception:
        pass
    return None


from database import db_session, InventoryItem, SystemSettings

class GradedCardWizard(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Graded Card Price Wizard")
        self.geometry("400x300")
        self.attributes("-topmost", True)
        self.grab_set()

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text="Graded Card Price Wizard", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0, pady=(20, 10))

        self.auto_btn = ctk.CTkButton(self, text="Auto Price Wizard", command=self.run_auto_wizard, fg_color="#3b8ed0", hover_color="#2c6a9b", font=ctk.CTkFont(weight="bold"))
        self.auto_btn.grid(row=1, column=0, pady=10, padx=20, sticky="ew")

        self.manual_btn = ctk.CTkButton(self, text="Manual Price Wizard", command=self.run_manual_wizard, fg_color="#2fa572", hover_color="#268a5f", font=ctk.CTkFont(weight="bold"))
        self.manual_btn.grid(row=2, column=0, pady=10, padx=20, sticky="ew")

        self.settings_btn = ctk.CTkButton(self, text="Wizard Settings", command=self.open_settings, fg_color="gray", hover_color="darkgray")
        self.settings_btn.grid(row=3, column=0, pady=10, padx=20, sticky="ew")

    def open_settings(self):
        SettingsModal(self)

    def run_auto_wizard(self):
        messagebox.showinfo("Auto Wizard", "Auto wizard is starting in the background. You can continue using the app.")
        threading.Thread(target=self.auto_wizard_thread, daemon=True).start()
        self.destroy()

    def auto_wizard_thread(self):
        settings = db_session.query(SystemSettings).first()
        sales_count = settings.graded_wizard_sales_count if settings else 5
        
        graded_cards = db_session.query(InventoryItem).filter(InventoryItem.card_type == 'Graded').all()
        updated_count = 0
        failed_cards = []
        
        from logic import calculate_shop_price
        
        for card in graded_cards:
            sales = ScraperHelper.get_sales(card.name, card.set_name, card.sequence_number, card.condition)
            if not sales:
                failed_cards.append(f"{card.name} ({card.set_name} {card.sequence_number}) - No sales found")
                continue
                
            sales = sales[:sales_count]
            prices = [s['price'] for s in sales]
            if not prices:
                failed_cards.append(f"{card.name} - No valid prices")
                continue
                
            avg_price = sum(prices) / len(prices)
            
            card.old_price = card.price
            card.price = avg_price
            card.shop_listing_price = calculate_shop_price(avg_price)
            card.needs_update = True
            updated_count += 1
            
        db_session.commit()
        
        msg = f"Auto Wizard completed!\nUpdated {updated_count} graded cards."
        if failed_cards:
            msg += f"\n\nFailed to find pricing for {len(failed_cards)} cards. Defaulting to latest recon price (if any)."
            
        # Try to show toast in main thread
        try:
            self.master.after(0, lambda: messagebox.showinfo("Auto Wizard Complete", msg))
        except Exception:
            print(msg)
    def run_manual_wizard(self):
        self.grab_release()
        self.destroy()
        self.master.after(50, lambda: ManualWizardSession(self.master))

class SettingsModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Wizard Settings")
        self.geometry("300x250")
        self.attributes("-topmost", True)
        self.grab_set()

        settings = db_session.query(SystemSettings).first()
        self.sales_count_var = ctk.StringVar(value=str(settings.graded_wizard_sales_count if settings else 5))
        self.omit_diff_var = ctk.StringVar(value=str(settings.graded_wizard_omit_diff if settings else 20.0))

        ctk.CTkLabel(self, text="Sales Count to Average:").pack(pady=(15, 0))
        ctk.CTkEntry(self, textvariable=self.sales_count_var).pack(pady=5)

        ctk.CTkLabel(self, text="% Difference to Omit (Outliers):").pack(pady=(10, 0))
        ctk.CTkEntry(self, textvariable=self.omit_diff_var).pack(pady=5)

        ctk.CTkButton(self, text="Save Settings", command=self.save).pack(pady=20)

    def save(self):
        try:
            sales_count = int(self.sales_count_var.get())
            omit_diff = float(self.omit_diff_var.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers.")
            return

        settings = db_session.query(SystemSettings).first()
        if settings:
            settings.graded_wizard_sales_count = sales_count
            settings.graded_wizard_omit_diff = omit_diff
            db_session.commit()
            messagebox.showinfo("Success", "Settings saved!")
            self.destroy()


class ScraperHelper:
    @staticmethod
    def get_cad_rate():
        try:
            req = urllib.request.Request("https://api.exchangerate-api.com/v4/latest/USD")
            response = urllib.request.urlopen(req).read()
            data = json.loads(response)
            return data['rates']['CAD']
        except Exception:
            return 1.35

    @staticmethod
    def scrape_ebay(query, is_graded=False, required_company="", sold=True):
        try:
            encoded_query = urllib.parse.quote_plus(query)
            url = f"https://www.ebay.com/sch/i.html?_nkw={encoded_query}&LH_PrefLoc=2"
            if sold:
                url += "&LH_Sold=1&LH_Complete=1"
                
            options = uc.ChromeOptions()
            options.add_argument('--window-position=-32000,-32000')
            chrome_version = get_chrome_major_version()
            
            if chrome_version:
                driver = uc.Chrome(options=options, version_main=chrome_version)
            else:
                driver = uc.Chrome(options=options)
                
            try:
                driver.set_page_load_timeout(30)
                driver.get(url)
                import time
                time.sleep(3)
                html_source = driver.page_source
            finally:
                driver.quit()

            soup = BeautifulSoup(html_source, 'html.parser')
            
            items = soup.find_all('div', class_='s-item__info')
            is_s_card = False
            if not items:
                items = soup.find_all('li', class_='s-card')
                is_s_card = True
                
            results = []
            for item in items:
                if not is_s_card:
                    title_div = item.find('div', class_='s-item__title')
                    if not title_div: continue
                    title = title_div.text.strip()
                    if title.lower() == 'shop on ebay': continue

                    price_span = item.find('span', class_='s-item__price')
                    date_span = item.find('span', class_='POSITIVE')
                    if not date_span:
                        date_span = item.find('div', class_='s-item__title--tag')
                    a_tag = item.find('a', class_='s-item__link')
                else:
                    title_div = item.find('div', class_='s-card__title')
                    if not title_div: continue
                    title = title_div.text.strip()
                    if title.lower() == 'shop on ebay': continue
                    
                    price_span = item.find('span', class_=lambda c: c and 's-card__price' in c)
                    date_span = item.find('span', class_=lambda c: c and 'positive' in c.lower())
                    a_tag = item.find('a', class_='s-card__link') or item.find('a', class_='s-card__action')

                if not price_span: continue
                price_text = price_span.text.strip()
                
                if 'strikethrough' in str(price_span).lower(): continue
                if 'to' in price_text.lower(): continue
                
                # Removed custom fuzzy matching checks per user request, relying entirely on eBay search.
                
                clean_price = re.sub(r'[^\d.]', '', price_text)
                if not clean_price: continue
                usd_price = float(clean_price)
                cad_rate = ScraperHelper.get_cad_rate()
                price_val = round(usd_price * cad_rate, 2)
                
                # Filter out wrong grading companies from eBay's fuzzy search
                if required_company:
                    t_lower = title.lower()
                    req_lower = required_company.lower()
                    
                    competitors = ["psa", "bgs", "cgc", "sgc", "tag", "pca", "cga", "ksa", "mnt"]
                    if req_lower in competitors:
                        competitors.remove(req_lower)
                        
                    has_competitor = False
                    for comp in competitors:
                        if re.search(rf'\b{comp}\b', t_lower):
                            has_competitor = True
                            break
                    if has_competitor:
                        continue


                date_str = date_span.text.strip() if date_span else "Unknown Date"
                if date_str.lower().startswith('sold '):
                    date_str = date_str[5:].strip()

                item_url = a_tag['href'] if a_tag else url

                results.append({
                    'title': title,
                    'price': price_val,
                    'date': date_str,
                    'url': item_url,
                    'source': 'eBay'
                })
                if len(results) >= 10:
                    break
            return results
        except Exception as e:
            print(f"eBay Scrape error: {e}")
            return []


    @staticmethod
    def scrape_pricecharting(query, condition):
        try:
            encoded_query = urllib.parse.quote_plus(query)
            search_url = f"https://www.pricecharting.com/search-products?type=prices&q={encoded_query}"
            req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            response = urllib.request.urlopen(req).read()
            soup = BeautifulSoup(response, 'html.parser')
            
            if soup.find('table', id='price_data'):
                product_url = search_url
            else:
                td_titles = soup.find_all('td', class_='title')
                if td_titles and td_titles[0].find('a'):
                    href = td_titles[0].find('a')['href']
                    if href.startswith('http'):
                        product_url = href
                    else:
                        product_url = "https://www.pricecharting.com" + href
                    req = urllib.request.Request(product_url, headers={'User-Agent': 'Mozilla/5.0'})
                    response = urllib.request.urlopen(req).read()
                    soup = BeautifulSoup(response, 'html.parser')
                else:
                    return []

            pc_grade_match = "Ungraded"
            if condition:
                cond_lower = condition.lower()
                company = condition.split(' ')[0].upper()
                is_psa_or_raw = company in ["PSA", ""] or company not in ["BGS", "CGC", "SGC", "TAG", "PCA", "CGA", "KSA", "MNT"]
                
                if "10" in cond_lower:
                    if is_psa_or_raw:
                        pc_grade_match = "PSA 10"
                    else:
                        # PriceCharting only tracks PSA 10 explicitly. It does not have BGS 10 or CGC 10.
                        return []
                elif "9.5" in cond_lower: pc_grade_match = "Grade 9.5"
                elif "9" in cond_lower: pc_grade_match = "Grade 9"
                elif "8" in cond_lower: pc_grade_match = "Grade 8"
                elif "7" in cond_lower: pc_grade_match = "Grade 7"

            pc_class_map = {
                "PSA 10": "completed-auctions-manual-only",
                "Grade 9.5": "completed-auctions-box-only",
                "Grade 9": "completed-auctions-graded",
                "Grade 8": "completed-auctions-new",
                "Grade 7": "completed-auctions-cib",
                "Ungraded": "completed-auctions-used"
            }
            target_class = pc_class_map.get(pc_grade_match, "completed-auctions-used")
            
            divs = soup.find_all('div', class_=target_class)
            listings = []
            cad_rate = ScraperHelper.get_cad_rate()
            
            for div in divs:
                table = div.find('table')
                if table:
                    tbody = table.find('tbody')
                    if tbody:
                        for tr in tbody.find_all('tr'):
                            title_td = tr.find('td', class_='title')
                            price_td = tr.find('td', class_='numeric')
                            date_td = tr.find('td', class_='date')
                            
                            if not title_td or not price_td or not date_td:
                                continue
                                
                            title = title_td.text.strip()
                            price_str = price_td.text.strip().split('\n')[0].strip()
                            date_str = date_td.text.strip()
                            
                            clean_price = re.sub(r'[^\d.]', '', price_str)
                            if clean_price:
                                usd_price = float(clean_price)
                                cad_price = round(usd_price * cad_rate, 2)
                                listings.append({
                                    'title': title,
                                    'price': cad_price,
                                    'date': date_str,
                                    'url': product_url,
                                    'source': 'PriceCharting'
                                })
                    break 
            return listings
        except Exception as e:
            print(f"PriceCharting error: {e}")
            return []

    @staticmethod
    def get_sales(card_name, set_name, card_number, condition):
        # Extract company for grading filter
        company = condition.split(' ')[0].upper() if condition else ""
        is_graded = company in ["PSA", "BGS", "CGC", "SGC", "TAG", "PCA", "CGA", "KSA", "MNT"]
        
        # For graded cards, strip out words like 'Pristine' or 'Gem Mint' which restrict the eBay search too much.
        # We just want the company and the number (e.g., 'BGS 10')
        if is_graded:
            grade_match = re.search(r'\d+(\.\d+)?', condition)
            if grade_match:
                try:
                    num = float(grade_match.group())
                    grade_num = str(int(num)) if num.is_integer() else str(num)
                except ValueError:
                    grade_num = grade_match.group()
            else:
                grade_num = ""
            clean_condition = f"{company} {grade_num}".strip()
        else:
            clean_condition = condition
            
        # Match scraper.py logic exactly: just combine the fields
        query_parts = [card_name, set_name, card_number, clean_condition]
        query = " ".join([p for p in query_parts if p])
        
        ebay_sales = ScraperHelper.scrape_ebay(query, is_graded, required_company=company)
        if ebay_sales and len(ebay_sales) > 0:
            return ebay_sales

        # Fallback to PriceCharting
        pc_query = f"{card_name} {set_name} {card_number}".strip()
        pc_sales = ScraperHelper.scrape_pricecharting(pc_query, condition)
        return pc_sales

class ManualWizardSession(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Manual Price Wizard")
        self.geometry("900x600")
        self.attributes("-topmost", True)
        # self.grab_set()  # Allow user to interact with links
        
        self.graded_cards = db_session.query(InventoryItem).filter(InventoryItem.card_type == 'Graded').all()
        self.current_idx = 0
        
        settings = db_session.query(SystemSettings).first()
        self.target_sales_count = settings.graded_wizard_sales_count if settings else 5
        self.omit_diff = settings.graded_wizard_omit_diff if settings else 20.0
        
        self.all_scraped_sales = []
        self.sales_data = []
        self.sale_vars = []
        
        self.setup_ui()
        self.load_current_card()
        
    def setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=1)
        
        # Left Panel (Card Details & Image)
        self.left_panel = ctk.CTkFrame(self)
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.img_lbl = ctk.CTkLabel(self.left_panel, text="No Image", width=200, height=280)
        self.img_lbl.pack(pady=10)
        
        self.name_lbl = ctk.CTkLabel(self.left_panel, text="Name", font=ctk.CTkFont(weight="bold", size=16), wraplength=250)
        self.name_lbl.pack(pady=(10,0))
        
        self.set_lbl = ctk.CTkLabel(self.left_panel, text="Set")
        self.set_lbl.pack()
        
        self.cond_lbl = ctk.CTkLabel(self.left_panel, text="Condition", text_color="#F2A900")
        self.cond_lbl.pack(pady=(5,0))
        
        self.recon_price_lbl = ctk.CTkLabel(self.left_panel, text="Recon Price: $0.00", text_color="gray")
        self.recon_price_lbl.pack(pady=(10,0))

        # Right Panel (Sales & Controls)
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        self.status_lbl = ctk.CTkLabel(self.right_panel, text="")
        self.status_lbl.pack()
        
        self.tabs = ctk.CTkTabview(self.right_panel)
        self.tabs.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.sold_tab = self.tabs.add("Recent Sold")
        self.active_tab = self.tabs.add("Current Listings")
        
        self.sales_frame = ctk.CTkScrollableFrame(self.sold_tab, fg_color="transparent")
        self.sales_frame.pack(fill="both", expand=True)
        
        self.active_frame = ctk.CTkScrollableFrame(self.active_tab, fg_color="transparent")
        self.active_frame.pack(fill="both", expand=True)
        
        self.load_more_btn = ctk.CTkButton(self.sold_tab, text="Load More Sales", command=self.load_more_sales, fg_color="gray", state="disabled")
        self.load_more_btn.pack(pady=(5,0))
        
        self.active_load_more_btn = ctk.CTkButton(self.active_tab, text="Load More Listings", command=self.load_more_active, fg_color="gray", state="disabled")
        self.active_load_more_btn.pack(pady=(5,0))
        
        # Bottom Controls inside right panel
        bottom_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        bottom_frame.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(bottom_frame, text="Calculated Average:", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, padx=5)
        self.avg_var = ctk.StringVar(value="$0.00")
        ctk.CTkLabel(bottom_frame, textvariable=self.avg_var, font=ctk.CTkFont(size=18, weight="bold"), text_color="#2fa572").grid(row=0, column=1, padx=5)
        
        ctk.CTkLabel(bottom_frame, text="Manual Price:").grid(row=1, column=0, padx=5, pady=(10,0))
        self.manual_price_var = ctk.StringVar()
        ctk.CTkEntry(bottom_frame, textvariable=self.manual_price_var).grid(row=1, column=1, padx=5, pady=(10,0))
        
        btn_frame = ctk.CTkFrame(bottom_frame, fg_color="transparent")
        btn_frame.grid(row=2, column=0, columnspan=2, pady=15)
        
        ctk.CTkButton(btn_frame, text="Skip", command=self.next_card, fg_color="gray").pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Apply & Next", command=self.apply_price).pack(side="left", padx=5)

    def load_current_card(self):
        if self.current_idx >= len(self.graded_cards):
            messagebox.showinfo("Done", "All graded cards processed!")
            self.destroy()
            return
            
        card = self.graded_cards[self.current_idx]
        self.name_lbl.configure(text=card.name)
        self.set_lbl.configure(text=f"{card.set_name} #{card.sequence_number}")
        self.cond_lbl.configure(text=card.condition)
        self.recon_price_lbl.configure(text=f"Recon Price: ${card.price:.2f}" if card.price else "Recon Price: $0.00")
        thumb_path = os.path.join('static', 'scraped_thumbnails', f"{card.sku}.png")
        if os.path.exists(thumb_path):
            try:
                img = Image.open(thumb_path)
                img.thumbnail((200, 280))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(img.width, img.height))
                self.img_lbl.configure(image=ctk_img, text="")
            except Exception as e:
                self.img_lbl.configure(image="", text="Image Load Failed")
        else:
            self.img_lbl.configure(image="", text="No Image")
            
        # Clear previous sales
        for w in self.sales_frame.winfo_children():
            w.destroy()
        for w in self.active_frame.winfo_children():
            w.destroy()
            
        self.sale_vars = []
        self.sales_data = []
        self.all_scraped_sales = []
        self.all_active_listings = []
        self.avg_var.set("$0.00")
        
        self.status_lbl.configure(text="Scraping sales and active listings...", text_color="orange")
        self.manual_price_var.set("")
        
        # Run scraping in background
        threading.Thread(target=self.scrape_for_card, args=(card,), daemon=True).start()
        
    def scrape_for_card(self, card):
        sales = ScraperHelper.get_sales(card.name, card.set_name, card.sequence_number, card.condition)
        
        # Extract query for active listings logic
        condition = card.condition
        company = condition.split(' ')[0].upper() if condition else ""
        is_graded = company in ["PSA", "BGS", "CGC", "SGC", "TAG", "PCA", "CGA", "KSA", "MNT"]
        if is_graded:
            grade_match = re.search(r'\d+(\.\d+)?', condition)
            if grade_match:
                try:
                    num = float(grade_match.group())
                    grade_num = str(int(num)) if num.is_integer() else str(num)
                except ValueError:
                    grade_num = grade_match.group()
            else:
                grade_num = ""
            clean_condition = f"{company} {grade_num}".strip()
        else:
            clean_condition = condition
            
        # Match scraper.py logic exactly: just combine the fields
        query_parts = [card.name, card.set_name, card.sequence_number, clean_condition]
        query = " ".join([p for p in query_parts if p])
        
        active_listings = ScraperHelper.scrape_ebay(query, is_graded, required_company=company, sold=False)
        
        self.after(0, self.populate_sales, sales, active_listings)
        
    def populate_sales(self, sales, active_listings):
        self.status_lbl.configure(text=f"Found {len(sales)} sales and {len(active_listings)} active listings", text_color="green")
        
        self.all_scraped_sales = sales
        self.all_active_listings = active_listings
        
        # Load initial target_sales_count
        self.load_more_sales(initial=True)
        self.load_more_active(initial=True)
        
    def load_more_active(self, initial=False):
        count = self.target_sales_count if initial else 5
        to_add = self.all_active_listings[:count]
        self.all_active_listings = self.all_active_listings[count:]
        
        for lst in to_add:
            self.add_active_to_ui(lst)
            
        if self.all_active_listings:
            self.active_load_more_btn.configure(state="normal")
        else:
            self.active_load_more_btn.configure(state="disabled")
            
    def add_active_to_ui(self, lst):
        row = ctk.CTkFrame(self.active_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        
        title_lbl = ctk.CTkLabel(row, text=lst['title'], width=280, anchor="w", wraplength=280)
        title_lbl.pack(side="left", padx=5)
        
        if lst.get('url'):
            import webbrowser
            btn = ctk.CTkButton(row, text="🔗", width=30, command=lambda u=lst['url']: webbrowser.open(u))
            btn.pack(side="right", padx=5)
        
        price_lbl = ctk.CTkLabel(row, text=f"${lst['price']:.2f}", font=ctk.CTkFont(weight="bold"))
        price_lbl.pack(side="right", padx=10)
        
    def load_more_sales(self, initial=False):
        count = self.target_sales_count if initial else 5
        sales_to_add = self.all_scraped_sales[:count]
        self.all_scraped_sales = self.all_scraped_sales[count:]
        
        for sale in sales_to_add:
            self.add_sale_to_ui(sale)
            
        self.recalc_avg()
        
        if self.all_scraped_sales:
            self.load_more_btn.configure(state="normal")
        else:
            self.load_more_btn.configure(state="disabled")
        
    def add_sale_to_ui(self, sale):
        row = ctk.CTkFrame(self.sales_frame, fg_color="transparent")
        row.pack(fill="x", pady=2)
        
        var = ctk.BooleanVar(value=True)
        self.sale_vars.append(var)
        
        chk = ctk.CTkCheckBox(row, text="", variable=var, width=20, command=self.recalc_avg)
        chk.pack(side="left", padx=5)
        
        title_lbl = ctk.CTkLabel(row, text=sale['title'], width=250, anchor="w", wraplength=250)
        title_lbl.pack(side="left", padx=5)
        
        if sale.get('url'):
            import webbrowser
            btn = ctk.CTkButton(row, text="🔗", width=30, command=lambda u=sale['url']: webbrowser.open(u))
            btn.pack(side="right", padx=5)
        
        price_lbl = ctk.CTkLabel(row, text=f"${sale['price']:.2f}", font=ctk.CTkFont(weight="bold"))
        price_lbl.pack(side="right", padx=10)
        
        self.sales_data.append(sale)
        
    def recalc_avg(self):
        active_prices = []
        for i, var in enumerate(self.sale_vars):
            if var.get():
                active_prices.append(self.sales_data[i]['price'])
                
        if not active_prices:
            self.avg_var.set("$0.00")
            self.manual_price_var.set("0.00")
            return
            
        avg = sum(active_prices) / len(active_prices)
        self.avg_var.set(f"${avg:.2f}")
        self.manual_price_var.set(f"{avg:.2f}")
        
    def apply_price(self):
        card = self.graded_cards[self.current_idx]
        try:
            new_price = float(self.manual_price_var.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid price format.")
            return
            
        from logic import calculate_shop_price
        shop_price = calculate_shop_price(new_price)
        
        card.old_price = card.price
        card.price = new_price
        card.shop_listing_price = shop_price
        card.needs_update = True
        
        db_session.commit()
        
        self.next_card()
        
    def next_card(self):
        self.current_idx += 1
        self.load_current_card()
