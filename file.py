from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time, os, shutil, logging, json, glob
from datetime import datetime

class KHCJudgmentDownloader:
    def __init__(self, download_dir=None, resume=False):
        if download_dir is None:
            download_dir = os.path.join(os.getcwd(), 'KHC_Judgments')
        if not os.path.exists(download_dir): os.makedirs(download_dir)
        self.download_dir = download_dir
        self.state_file = os.path.join(download_dir, 'download_state.json')
        self.resume = resume
        self.current_state = self.load_state() if resume else {}
        self.setup_logging()
        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        prefs = {"download.default_directory": download_dir, "download.prompt_for_download": False, "plugins.always_open_pdf_externally": True,"profile.default_content_setting_values.notifications": 2,"download.directory_upgrade": True}
        chrome_options.add_experimental_option("prefs", prefs)
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 10)
        self.logger.info(f"Download Directory: {self.download_dir}")
        self.logger.info(f"Resume mode: {resume}")
        
    def setup_logging(self):
        log_file = os.path.join(self.download_dir, 'download_log.txt')
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s',handlers=[logging.FileHandler(log_file, encoding='utf-8'), logging.StreamHandler()])
        self.logger = logging.getLogger(__name__)
        
    def load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:return {}
        return {}
    
    def save_state(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.current_state, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving state: {e}")

    def handle_popup(self):
        try:
            time.sleep(1)
            popup_selectors = [
                "//button[contains(text(), 'OK')]","//button[contains(text(), 'Ok')]","//button[contains(text(), 'ok')]","//input[@value='OK']","//input[@value='Ok']","//input[@value='ok']",
                "//button[contains(@onclick, 'close')]","//div[@class='modal']//button[contains(text(), 'OK')]","//div[contains(@class, 'popup')]//button[contains(text(), 'OK')]"]
            for selector in popup_selectors:
                try:
                    ok_buttons = self.driver.find_elements(By.XPATH, selector)
                    for button in ok_buttons:
                        if button.is_displayed():
                            self.logger.info("Found popup, clicking OK button...")
                            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
                            self.driver.execute_script("arguments[0].click();", button)
                            time.sleep(1)  # Wait for popup to close completely
                            self.logger.info("Popup handled successfully")
                            return True
                except:continue
            return False
        except Exception as e:
            self.logger.warning(f"Error handling popup: {e}")
            return False
        
    def safe_click(self, element):
        try:
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            self.driver.execute_script("arguments[0].click();", element)
            time.sleep(0.5)
            self.handle_popup()
            return True
        except Exception as e:
            self.logger.error(f"Error in safe_click: {e}")
            return False
    
    def navigate_to_website(self):
        self.logger.info("Navigating to Karnataka Judiciary website...")
        self.driver.get("https://judiciary.karnataka.gov.in/ds_judgment.php")
        time.sleep(2)
        self.handle_popup() 
        self.logger.info("Page loaded successfully")
    
    def get_all_categories(self):
        self.logger.info("Fetching all available categories...")
        categories = []
        try:
            self.set_display_length("example_length", "100")
            time.sleep(1)
            buttons = self.driver.find_elements(By.XPATH, '//*[@id="example"]/tbody/tr/td/button')
            for btn in buttons:
                category_name = btn.text.strip()
                if category_name:
                    categories.append(category_name)
            self.logger.info(f"Found {len(categories)} categories: {categories}")
        except Exception as e:
            self.logger.error(f"Error fetching categories: {e}")
        return categories
    
    def select_category(self, category_name):
        self.logger.info(f"Selecting category: {category_name}")
        try:
            self.set_display_length("example_length", "100")
            time.sleep(1)
            buttons = self.driver.find_elements(By.XPATH, '//*[@id="example"]/tbody/tr/td/button')
            for btn in buttons:
                btn_text = btn.text.strip()
                if category_name == btn_text:
                    self.logger.info(f"Found and selecting category: {btn_text}")
                    self.safe_click(btn)
                    return True
            self.logger.error(f"Category '{category_name}' not found")
            return False
        except Exception as e:
            self.logger.error(f"Error selecting category: {e}")
            return False
    
    def set_display_length(self, table_name, value="100"):
        try:
            Select(self.driver.find_element(By.NAME, table_name)).select_by_value(value)
            time.sleep(0.3) 
            return True
        except: return False
    
    def click_back_button(self):
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if "back" in btn.text.lower():
                    self.safe_click(btn)
                    return True
        except: pass
        return False
    
    def handle_pagination(self, table_id):
        try:
            pagination_div = self.driver.find_element(By.ID, f"{table_id}_paginate")
            pages = pagination_div.find_elements(By.CSS_SELECTOR, "li.paginate_button.page-item:not(.previous):not(.next):not(.disabled)")
            if len(pages) <= 1:
                return False
            for page_num in range(2, len(pages) + 1):
                try:
                    page_btn = pagination_div.find_element(By.CSS_SELECTOR, f"li.paginate_button.page-item a[data-dt-idx='{page_num}']")
                    self.safe_click(page_btn)
                    return True
                except: continue
        except:return False
        return False
    
    def create_category_folder(self, category_name):
        safe_category_name = "".join(c for c in category_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
        category_folder = os.path.join(self.download_dir, safe_category_name)
        if not os.path.exists(category_folder):  os.makedirs(category_folder)
        return category_folder
    
    def create_year_folder(self, category_folder, year):
        year_folder = os.path.join(category_folder, str(year))
        if not os.path.exists(year_folder): os.makedirs(year_folder)
        return year_folder
    
    def create_month_folder(self, year_folder, month):
        month_folder = os.path.join(year_folder, str(month))
        if not os.path.exists(month_folder):os.makedirs(month_folder)
        return month_folder
    
    def get_current_pdf_count(self):
        pdf_files = glob.glob(os.path.join(self.download_dir, "*.pdf"))
        return len(pdf_files)
    
    def move_files_to_final_location(self, category_name, year, month=None):
        category_folder = self.create_category_folder(category_name)
        year_folder = self.create_year_folder(category_folder, year)
        if month:final_folder = self.create_month_folder(year_folder, month)
        else:final_folder = year_folder
        moved_count = 0
        not_moved_count = 0
        for file in os.listdir(self.download_dir):
            if file.endswith('.pdf'):
                src = os.path.join(self.download_dir, file)
                dst = os.path.join(final_folder, file)
                try:
                    if not os.path.exists(dst): 
                        shutil.move(src, dst)
                        moved_count += 1
                        self.logger.info(f"  Moved file: {file}")
                    else:
                        self.logger.info(f"  Removed duplicate file: {file}")
                except Exception as e:
                    not_moved_count += 1
                    self.logger.warning(f"Failed to move file {file}: {e}")
        return moved_count, not_moved_count
    
    def download_pdf_file(self, link):
        try:
            initial_count = self.get_current_pdf_count()
            file_url = link.get_attribute("href")
            if file_url and file_url.endswith('.pdf'):
                self.logger.info(f"  Downloading PDF: {os.path.basename(file_url)}")
                original_window = self.driver.current_window_handle
                self.driver.execute_script("window.open(arguments[0]);", file_url)
                time.sleep(2)
                new_window = [window for window in self.driver.window_handles if window != original_window][0]
                self.driver.switch_to.window(new_window)
                time.sleep(3) 
                self.driver.close()
                self.driver.switch_to.window(original_window)
                time.sleep(1)
                final_count = self.get_current_pdf_count()
                if final_count > initial_count:
                    self.logger.info(f"  Successfully downloaded PDF")
                    return True
                else:
                    self.logger.warning(f"  PDF download may have failed")
                    return False
        except Exception as e:
            self.logger.error(f"Error downloading PDF: {e}")
            return False
        return False
    
    def download_case_files(self, category_name, year, month=None):
        cases_processed = 0
        files_downloaded = 0
        try:
            self.set_display_length("example4_length", "50")  # Reduced page size for faster loading
            time.sleep(0.3)
            page_num = 1
            while True:
                rows = self.driver.find_elements(By.XPATH, '//*[@id="example4"]/tbody/tr')
                if not rows: break
                self.logger.info(f"    Processing {len(rows)} cases on page {page_num}")
                for idx in range(len(rows)):
                    try:
                        self.set_display_length("example4_length", "50")
                        time.sleep(0.2)
                        rows = self.driver.find_elements(By.XPATH, '//*[@id="example4"]/tbody/tr')
                        if idx >= len(rows):  break
                        row = rows[idx]
                        case_button = row.find_element(By.XPATH, './td[2]/button')
                        case_title = case_button.text.strip()
                        file_key = f"{category_name}_{year}_{month}_{case_title}" if month else f"{category_name}_{year}_{case_title}"
                        if self.resume and self.current_state.get(file_key) == "processed":
                            cases_processed += 1
                            continue
                        self.logger.info(f"    Processing case: {case_title}")
                        self.safe_click(case_button)
                        pdf_links = self.driver.find_elements(By.XPATH, '//table//tr//td[2]/a')
                        for link_idx, link in enumerate(pdf_links):
                            try:
                                if self.download_pdf_file(link):
                                    files_downloaded += 1
                                    self.logger.info(f"    Downloaded PDF {link_idx + 1}/{len(pdf_links)}")
                            except Exception as e:
                                self.logger.error(f"    Error downloading PDF {link_idx + 1}: {e}")
                                continue
                        cases_processed += 1
                        self.current_state[file_key] = "processed"
                        self.save_state()
                        self.click_back_button()
                        time.sleep(0.3)
                    except Exception as e:
                        self.logger.error(f"Error processing case {idx}: {e}")
                        continue
                if month: self.logger.info(f"    Month {month} - Page {page_num}: {cases_processed} cases processed")
                else:self.logger.info(f"    Year {year} - Page {page_num}: {cases_processed} cases processed")
                if not self.handle_pagination("example4"):break
                page_num += 1
        except Exception as e: self.logger.error(f"Error processing cases: {e}")
        return cases_processed, files_downloaded
    
    def process_month_table(self, category_name, year):
        total_cases = 0
        total_files_downloaded = 0
        months_processed = 0
        try:
            self.set_display_length("example3_length", "50")
            time.sleep(0.3)
            page_num = 1
            while True:
                month_buttons = self.driver.find_elements(By.XPATH, '//*[@id="example3"]/tbody/tr/td/button')
                if not month_buttons: return 0, 0, 0
                self.logger.info(f"  Found {len(month_buttons)} months on page {page_num}")
                for month_idx in range(len(month_buttons)):
                    try:
                        self.set_display_length("example3_length", "50")
                        time.sleep(0.2)
                        month_buttons = self.driver.find_elements(By.XPATH, '//*[@id="example3"]/tbody/tr/td/button')
                        if month_idx >= len(month_buttons): break
                        month_btn = month_buttons[month_idx]
                        month_text = month_btn.text.strip()
                        month_key = f"{category_name}_{year}_{month_text}"
                        if self.resume and self.current_state.get(f"{month_key}_completed"):
                            self.logger.info(f"  Skipping already processed month: {month_text}")
                            continue
                        self.logger.info(f"  Processing month: {month_text}")
                        self.safe_click(month_btn)
                        month_cases, month_files = self.download_case_files(category_name, year, month_text)
                        moved_count, not_moved_count = self.move_files_to_final_location(category_name, year, month_text)
                        total_cases += month_cases
                        total_files_downloaded += month_files
                        months_processed += 1
                        self.logger.info(f"  Month {month_text} completed:")
                        self.logger.info(f"    Cases processed: {month_cases}")
                        self.logger.info(f"    Files moved: {moved_count}")
                        self.current_state[f"{month_key}_completed"] = True
                        self.save_state()
                        self.click_back_button()
                        time.sleep(0.3)
                    except Exception as e:
                        self.logger.error(f"  Error processing month {month_idx}: {e}")
                        continue
                if not self.handle_pagination("example3"):break
                page_num += 1
            return months_processed, total_cases, total_files_downloaded
        except Exception as e:
            self.logger.error(f"Error processing month table: {e}")
            return months_processed, total_cases, total_files_downloaded
    
    def process_year(self, year_btn, year_idx, total_years, page_num, category_name):
        year_text = year_btn.text.strip().split('[')[0].strip()
        if not year_text:
            year_text = f"Year_{year_idx + 1}"
        year_key = f"{category_name}_{year_text}"
        if self.resume and self.current_state.get(f"{year_key}_completed"):
            self.logger.info(f"  Skipping already processed year: {year_text}")
            return 0, 0, 0
        start_time = time.time()
        self.logger.info("=" * 70)
        self.logger.info(f"PROCESSING YEAR: {year_text}")
        self.logger.info(f"Category: {category_name}")
        self.logger.info(f"Position: {year_idx + 1}/{total_years} on page {page_num}")
        self.logger.info("=" * 70)
        self.safe_click(year_btn)
        cases_processed = 0
        files_downloaded = 0
        months_processed = 0
        try:
            self.driver.find_element(By.ID, "example3")
            has_month_table = True
            months_processed, cases_processed, files_downloaded = self.process_month_table(category_name, year_text)
            if months_processed == 0:
                self.logger.info("  No months found, processing cases directly...")
                cases_processed, files_downloaded = self.download_case_files(category_name, year_text)
        except:
            self.logger.info("  No month table found, processing cases directly...")
            cases_processed, files_downloaded = self.download_case_files(category_name, year_text)
        moved_count, not_moved_count = self.move_files_to_final_location(category_name, year_text)
        processing_time = time.time() - start_time
        self.logger.info("-" * 60)
        self.logger.info(f"YEAR {year_text} COMPLETED:")
        self.logger.info(f"  Months processed: {months_processed}")
        self.logger.info(f"  Cases processed: {cases_processed}")
        self.logger.info(f"  Files moved: {moved_count}")
        self.logger.info(f"  Time taken: {processing_time:.2f} seconds")
        self.logger.info("-" * 60)
        self.current_state[f"{year_key}_completed"] = True
        self.save_state()
        self.click_back_button()
        time.sleep(0.5)
        return cases_processed, files_downloaded, months_processed
    
    def process_all_years(self, category_name):
        self.logger.info(f"Starting year processing for category: {category_name}")
        total_years_processed = 0
        total_cases_processed = 0
        total_months_processed = 0
        try:
            self.set_display_length("example1_length", "50")
            time.sleep(0.5)
            page_num = 1
            while True:
                year_buttons = self.driver.find_elements(By.XPATH, '//*[@id="example1"]/tbody/tr/td/button')
                total_years_on_page = len(year_buttons)
                if total_years_on_page == 0:  break
                self.logger.info(f"Processing year page {page_num} for category '{category_name}'")
                self.logger.info(f"  Found {total_years_on_page} years on page {page_num}")
                for year_idx in range(total_years_on_page):
                    try:
                        self.set_display_length("example1_length", "50")
                        time.sleep(0.3)
                        year_buttons = self.driver.find_elements(By.XPATH, '//*[@id="example1"]/tbody/tr/td/button')
                        if year_idx >= len(year_buttons): break
                        year_btn = year_buttons[year_idx]
                        cases, files, months = self.process_year(year_btn, year_idx, total_years_on_page, page_num, category_name)
                        total_years_processed += 1
                        total_cases_processed += cases
                        total_files_downloaded += files
                        total_months_processed += months
                    except Exception as e:
                        self.logger.error(f"Failed to process year {year_idx + 1}: {e}")
                        try:
                            self.click_back_button()
                            time.sleep(0.5)
                        except: pass
                        continue
                if not self.handle_pagination("example1"): break
                page_num += 1
            return total_years_processed, total_cases_processed, total_files_downloaded, total_months_processed
        except Exception as e:
            self.logger.error(f"Error processing years for category {category_name}: {e}")
            return total_years_processed, total_cases_processed, total_files_downloaded, total_months_processed
    
    def process_all_categories(self):
        categories = self.get_all_categories()
        if not categories:
            self.logger.error("No categories found!")
            return
        total_stats = {'categories_processed': 0,'total_years': 0,'total_months': 0,'total_cases': 0}
        for category_idx, category_name in enumerate(categories, 1):
            if self.resume and self.current_state.get(f"category_{category_name}_completed"):
                self.logger.info(f"Skipping already processed category: {category_name}")
                continue
            self.logger.info("\n" + "=" * 80)
            self.logger.info(f"PROCESSING CATEGORY {category_idx}/{len(categories)}: {category_name}")
            self.logger.info("=" * 80)
            category_start_time = time.time()
            if not self.select_category(category_name):
                self.logger.error(f"Failed to select category: {category_name}")
                continue
            years, cases, files, months = self.process_all_years(category_name)
            category_time = time.time() - category_start_time
            total_stats['categories_processed'] += 1
            total_stats['total_years'] += years
            total_stats['total_months'] += months
            total_stats['total_cases'] += cases
            self.logger.info("\n" + "*" * 70)
            self.logger.info(f"CATEGORY COMPLETED: {category_name}")
            self.logger.info(f"  Years processed: {years}")
            self.logger.info(f"  Months processed: {months}")
            self.logger.info(f"  Cases processed: {cases}")
            self.logger.info(f"  Files downloaded: {files}")
            self.logger.info(f"  Time taken: {category_time:.2f} seconds")
            self.logger.info("*" * 70)
            self.current_state[f"category_{category_name}_completed"] = True
            self.save_state()
            self.navigate_to_website()
        return total_stats

    def run(self):
        start_time = datetime.now()
        self.logger.info(f"=== KHC Judgment Downloader Started at {start_time} ===")
        self.logger.info(f"Resume mode: {self.resume}")
        try:
            self.navigate_to_website()
            total_stats = self.process_all_categories()
            end_time = datetime.now()
            duration = end_time - start_time
            self.logger.info("\n" + "=" * 80)
            self.logger.info("FINAL DOWNLOAD SUMMARY:")
            self.logger.info("=" * 80)
            if total_stats:
                self.logger.info(f"Categories processed: {total_stats['categories_processed']}")
                self.logger.info(f"Total years processed: {total_stats['total_years']}")
                self.logger.info(f"Total months processed: {total_stats['total_months']}")
                self.logger.info(f"Total cases processed: {total_stats['total_cases']}")
            else: self.logger.info("No statistics available - process may have been interrupted")
            self.logger.info(f"Total time taken: {duration}")
            self.logger.info(f"Files saved at: {self.download_dir}")
            self.logger.info(f"=== Process completed at {end_time} ===")
            if os.path.exists(self.state_file):
                os.remove(self.state_file)
        except Exception as e:
            self.logger.error(f"Fatal error in main process: {e}")
            self.logger.info("Download state saved. You can resume later using resume=True")
        finally: time.sleep(2), self.driver.quit()

def main():
    downloader = KHCJudgmentDownloader(resume=True)
    downloader.run()

if __name__ == "__main__":
    main()