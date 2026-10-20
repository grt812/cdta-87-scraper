import csv
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def handle_response(response, writer, file_handle):
    if "ajax-arrivals" in response.url and response.request.method == "POST":
        try:
            post_data = response.request.post_data or ""
            stop_id_match = re.search(r"stop_id=([^&]+)", post_data)
            stop_id = stop_id_match.group(1) if stop_id_match else "unknown"
            print(f"Processing stop_id: {stop_id}")
            
            html_content = response.text()
            soup = BeautifulSoup(html_content, "html.parser")
            
            scrape_time_dt = datetime.now()
            scrape_time = scrape_time_dt.strftime("%Y-%m-%dT%H:%M:%S")
            
            for li in soup.find_all("li"):
                time_match = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)', li.text, re.IGNORECASE)
                if not time_match:
                    continue
                
                img_tag = li.find("img")
                occupancy = "unknown"
                if img_tag and "src" in img_tag.attrs:
                    src = img_tag["src"]
                    if "occupancy3.png" in src:
                        occupancy = "crowded"
                    elif "occupancy2.png" in src:
                        occupancy = "some crowding"
                    elif "occupancy1.png" in src:
                        occupancy = "not crowded"
                
                parsed_time = datetime.strptime(time_match.group(1).strip(), "%I:%M %p")
                arrival_dt = scrape_time_dt.replace(hour=parsed_time.hour, minute=parsed_time.minute, second=0, microsecond=0)
                
                # Handle edge case where scrape happens right at midnight
                if arrival_dt < scrape_time_dt and (scrape_time_dt.hour - arrival_dt.hour) > 12:
                    arrival_dt += timedelta(days=1)
                
                arrival_time_str = arrival_dt.strftime("%Y-%m-%dT%H:%M:%S")

                due_span = li.find("span", class_="duetime")
                due_text = due_span.text.strip("()") if due_span else ""
                
                hrs, mins = 0, 0
                hr_match = re.search(r'(\d+)\s*hr', due_text, re.IGNORECASE)
                min_match = re.search(r'(\d+)\s*min', due_text, re.IGNORECASE)
                
                if hr_match:
                    hrs = int(hr_match.group(1))
                if min_match:
                    mins = int(min_match.group(1))
                
                eta_dt = scrape_time_dt + timedelta(hours=hrs, minutes=mins)
                due_in_str = eta_dt.strftime("%Y-%m-%dT%H:%M:%S")
                
                if due_span:
                    due_span.extract()
                occ_span = li.find("span", class_="i-occupancy")
                if occ_span:
                    occ_span.extract()
                
                writer.writerow([scrape_time, stop_id, arrival_time_str, due_in_str, occupancy])
                
            file_handle.flush()
        except Exception as e:
            print(e)
            pass
    else:
        print("Ignoring response:", response)

def main():
    csv_file = "route_87.csv"
    with open(csv_file, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if f.tell() == 0:
            writer.writerow(["Scrape_Time", "Stop_ID", "Arrival_Time", "Due_In", "Occupancy"])
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            page.on("response", lambda resp: handle_response(resp, writer, f))
            page.goto("https://www.cdta.org/schedules-route-detail?route_id=87")

            page.wait_for_selector(".b-show-hide-arrivals")
            
            buttons = page.locator(".b-show-hide-arrivals").all()
            
            for button in buttons:
                if button.is_visible() and "Show Arrivals" in button.inner_text():
                    button.click()
                    page.wait_for_timeout(100)
            try:
                while True:
                    page.wait_for_timeout(1000)
            except KeyboardInterrupt:
                pass
            finally:
                browser.close()

if __name__ == "__main__":
    main()
