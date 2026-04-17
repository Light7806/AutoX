import json
import os
import re
import threading
import time

import customtkinter as ctk
import google.generativeai as genai
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


# ==========================================
# USER / APP CONFIGURATION
# ==========================================
USER_PROFILE = {
    "name": "Alex Developer",
    "first_name": "Alex",
    "last_name": "Developer",
    "email": "alex.dev@example.com",
    "phone": "+91 9876543210",
    "location": "Bengaluru, India",
    "linkedin": "https://www.linkedin.com/in/alexdeveloper",
    "github": "https://github.com/alexdev",
    "portfolio": "https://alexdev.dev",
    "college": "Example Institute of Technology",
    "current_company": "Example Labs",
    "resume_summary": "Full-stack engineer focused on AI workflows, automation, and product prototyping.",
    "profile_sources": {
        "local_profile": True,
        "google_connected": False,
        "linkedin_connected": False,
    },
}

DOMINO_CONTEXT = {
    "team_slack_url": "https://slack.com/workspace",
    "calendar_url": "https://calendar.google.com",
    "boss_name": "Abhimanyu",
}

DELIVERY_SITES = {
    "amazon": {
        "label": "Amazon",
        "home": "https://www.amazon.in",
        "search_input": "#twotabsearchtextbox",
        "search_submit": "#nav-search-submit-button",
        "result_links": "div[data-component-type='s-search-result'] h2 a",
        "add_to_cart": "#add-to-cart-button",
    },
    "flipkart": {
        "label": "Flipkart",
        "home": "https://www.flipkart.com",
        "search_input": "input[title='Search for Products, Brands and More']",
        "search_submit": "input[title='Search for Products, Brands and More']",
        "result_links": "a[href*='/p/']",
        "add_to_cart": "button:has-text('Add to cart')",
    },
}

GEMINI_API_KEY = os.getenv("AIzaSyB9tEzShtCDp2csBozSUiQGldmPjcYqHtQ", "").strip()
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    GEMINI_MODEL = genai.GenerativeModel("gemini-2.5-flash")
else:
    GEMINI_MODEL = None


# ==========================================
# INTENT ROUTING
# ==========================================
def extract_json_object(text):
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return json.loads(match.group(0))


def infer_sites_from_text(user_input):
    lowered = user_input.lower()
    sites = [site for site in DELIVERY_SITES if site in lowered]
    return sites or ["amazon", "flipkart"]


def infer_delivery_task(user_input):
    lowered = user_input.lower()
    if any(phrase in lowered for phrase in ["add to cart", "add it to cart", "put in cart"]):
        return "add_to_cart"
    if any(phrase in lowered for phrase in ["open", "go to", "visit"]):
        return "visit"
    return "search"


def active_profile_sources():
    sources = []
    if USER_PROFILE["profile_sources"].get("google_connected"):
        sources.append("google")
    if USER_PROFILE["profile_sources"].get("linkedin_connected"):
        sources.append("linkedin")
    if USER_PROFILE["profile_sources"].get("local_profile") or not sources:
        sources.append("local_profile")
    return sources


def heuristic_route(user_input):
    lowered = user_input.lower()

    if any(token in lowered for token in ["traffic", "running late", "commuting", "stuck"]):
        return {"action": "domino_traffic"}

    if any(token in lowered for token in ["sick", "fever", "unwell", "medical day", "not feeling well"]):
        return {"action": "domino_sick"}

    if any(token in lowered for token in ["apply", "application", "form", "register", "hackathon", "job"]):
        url_match = re.search(r"https?://\S+", user_input)
        return {
            "action": "form_fill",
            "url": url_match.group(0) if url_match else "",
            "profile_sources": active_profile_sources(),
        }

    if any(token in lowered for token in ["amazon", "flipkart", "buy", "price", "cheapest", "cart", "delivery"]):
        query = re.sub(
            r"\b(buy|find|get|search|compare|price|cheapest|on|amazon|flipkart|delivery|add to cart|add it to cart|put in cart)\b",
            "",
            lowered,
            flags=re.IGNORECASE,
        )
        clean_query = " ".join(query.split()) or "item"
        return {
            "action": "delivery",
            "query": clean_query,
            "sites": infer_sites_from_text(user_input),
            "task": infer_delivery_task(user_input),
        }

    return {"action": "unknown"}


def get_ai_decision(user_input):
    system_prompt = """
You are the central intelligence router for an AI Chief of Staff.
Analyze the user's command and categorize it into exactly ONE action.

Supported actions:
1. "delivery": The user wants e-commerce help on Amazon and/or Flipkart.
   Required fields when relevant:
   - "query": product or item being searched
   - "sites": array containing one or more of ["amazon", "flipkart"]
   - "task": one of ["visit", "search", "add_to_cart"]
2. "form_fill": The user wants to apply for a job, hackathon, or complete a form.
   Required fields when relevant:
   - "url": string, empty if absent
   - "profile_sources": array containing one or more of ["google", "linkedin", "local_profile"]
3. "domino_sick": The user explicitly says they are sick, unwell, or taking a medical day.
4. "domino_traffic": The user says they are stuck in traffic, commuting, or running late.
5. "unknown": The request does not fit the supported actions.

Rules:
- Respond in strict raw JSON only.
- Do not include markdown or explanation.
- If a website is not explicitly named for delivery, default to both Amazon and Flipkart.
- If profile source is not explicitly named for form fill, prefer connected sources and include local_profile as fallback.

Examples:
{"action":"delivery","query":"mechanical keyboard","sites":["amazon","flipkart"],"task":"search"}
{"action":"delivery","query":"iphone 16","sites":["amazon"],"task":"add_to_cart"}
{"action":"form_fill","url":"https://example.com/apply","profile_sources":["linkedin","local_profile"]}
{"action":"domino_traffic"}
{"action":"domino_sick"}
{"action":"unknown"}
""".strip()

    if not GEMINI_MODEL:
        return heuristic_route(user_input)

    try:
        response = GEMINI_MODEL.generate_content(f"{system_prompt}\n\nCommand: {user_input}")
        decision = extract_json_object(response.text)
        action = decision.get("action", "unknown")

        if action == "delivery":
            decision["sites"] = [site for site in decision.get("sites", []) if site in DELIVERY_SITES] or infer_sites_from_text(user_input)
            decision["task"] = decision.get("task") or infer_delivery_task(user_input)
            decision["query"] = decision.get("query") or "item"
        elif action == "form_fill":
            decision["url"] = decision.get("url", "")
            decision["profile_sources"] = decision.get("profile_sources") or active_profile_sources()

        return decision
    except Exception as exc:
        fallback = heuristic_route(user_input)
        fallback["router_fallback_reason"] = str(exc)
        return fallback


# ==========================================
# PROFILE / FORM HELPERS
# ==========================================
def profile_payload_for_form():
    return {
        "name": USER_PROFILE["name"],
        "first_name": USER_PROFILE["first_name"],
        "last_name": USER_PROFILE["last_name"],
        "email": USER_PROFILE["email"],
        "phone": USER_PROFILE["phone"],
        "location": USER_PROFILE["location"],
        "linkedin": USER_PROFILE["linkedin"],
        "github": USER_PROFILE["github"],
        "portfolio": USER_PROFILE["portfolio"],
        "college": USER_PROFILE["college"],
        "company": USER_PROFILE["current_company"],
        "summary": USER_PROFILE["resume_summary"],
    }


def try_fill_first(page, selectors, value):
    for selector in selectors:
        locator = page.locator(selector).first
        if locator.count():
            try:
                locator.fill(value)
                return True
            except Exception:
                continue
    return False


def fill_common_form_fields(page, profile, log_callback):
    field_map = {
        "name": [profile["name"], ["input[name*='name']", "input[id*='name']", "input[placeholder*='Name']"]],
        "first_name": [profile["first_name"], ["input[name*='first']", "input[id*='first']", "input[placeholder*='First']"]],
        "last_name": [profile["last_name"], ["input[name*='last']", "input[id*='last']", "input[placeholder*='Last']"]],
        "email": [profile["email"], ["input[type='email']", "input[name*='mail']", "input[id*='mail']", "input[placeholder*='Email']"]],
        "phone": [profile["phone"], ["input[type='tel']", "input[name*='phone']", "input[id*='phone']", "input[placeholder*='Phone']"]],
        "location": [profile["location"], ["input[name*='location']", "input[id*='location']", "input[placeholder*='Location']"]],
        "linkedin": [profile["linkedin"], ["input[name*='linkedin']", "input[id*='linkedin']", "input[placeholder*='LinkedIn']"]],
        "github": [profile["github"], ["input[name*='github']", "input[id*='github']", "input[placeholder*='GitHub']"]],
        "portfolio": [profile["portfolio"], ["input[name*='portfolio']", "input[id*='portfolio']", "input[placeholder*='Portfolio']", "input[placeholder*='Website']"]],
        "college": [profile["college"], ["input[name*='college']", "input[id*='college']", "input[placeholder*='College']", "input[placeholder*='University']"]],
        "company": [profile["company"], ["input[name*='company']", "input[id*='company']", "input[placeholder*='Company']"]],
        "summary": [profile["summary"], ["textarea[name*='summary']", "textarea[id*='summary']", "textarea[name*='cover']", "textarea[placeholder*='summary']", "textarea"]],
    }

    filled = 0
    for field_name, (value, selectors) in field_map.items():
        if value and try_fill_first(page, selectors, value):
            filled += 1
            log_callback(f"Filled form field: {field_name}")

    if filled == 0:
        log_callback("No common fields were matched automatically on this page.")
    else:
        log_callback(f"Auto-filled {filled} common field(s).")


# ==========================================
# PLAYWRIGHT EXECUTION
# ==========================================
def safe_click(locator):
    try:
        locator.click(timeout=4000)
        return True
    except Exception:
        return False


def open_delivery_site(page, site_key, query, task, log_callback):
    config = DELIVERY_SITES[site_key]
    label = config["label"]

    log_callback(f"Opening {label} for task '{task}'...")
    page.goto(config["home"], wait_until="domcontentloaded")

    if site_key == "flipkart":
        safe_click(page.locator("button[aria-label='Close']").first)
        safe_click(page.locator("button:has-text('Close')").first)

    if task == "visit":
        log_callback(f"{label} opened.")
        return

    search_input = page.locator(config["search_input"]).first
    search_input.wait_for(timeout=8000)
    search_input.fill(query)

    if config["search_submit"] == config["search_input"]:
        search_input.press("Enter")
    else:
        page.locator(config["search_submit"]).first.click()

    log_callback(f"{label} search results loaded for '{query}'.")

    if task != "add_to_cart":
        return

    result_link = page.locator(config["result_links"]).first
    result_link.wait_for(timeout=8000)
    result_link.click()
    page.wait_for_load_state("domcontentloaded")

    pages = page.context.pages
    product_page = pages[-1]
    product_page.wait_for_load_state("domcontentloaded")

    if safe_click(product_page.locator(config["add_to_cart"]).first):
        log_callback(f"{label}: attempted add-to-cart on the first result.")
    else:
        log_callback(f"{label}: could not confirm add-to-cart automatically. Login or captcha may be blocking it.")


def execute_delivery(query, sites, task, log_callback):
    log_callback(f"Starting delivery workflow for '{query}' on {', '.join(sites)}.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=350)
        try:
            for site in sites:
                if site not in DELIVERY_SITES:
                    log_callback(f"Skipping unsupported site: {site}")
                    continue

                context = browser.new_context()
                page = context.new_page()
                try:
                    open_delivery_site(page, site, query, task, log_callback)
                except PlaywrightTimeoutError:
                    log_callback(f"{DELIVERY_SITES[site]['label']}: timed out while loading selectors.")
                except Exception as exc:
                    log_callback(f"{DELIVERY_SITES[site]['label']}: workflow failed with {exc}")
        finally:
            time.sleep(3)
            browser.close()
            log_callback("Delivery workflow complete.")


def execute_form_fill(url, profile_sources, log_callback):
    log_callback(f"Starting form-fill workflow using profile sources: {', '.join(profile_sources)}.")
    target_url = url.strip()
    if not target_url:
        log_callback("No form URL provided. Open a specific job or hackathon form URL to continue.")
        return

    profile = profile_payload_for_form()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=350)
        try:
            page = browser.new_page()
            page.goto(target_url, wait_until="domcontentloaded")
            fill_common_form_fields(page, profile, log_callback)
            log_callback("Form-fill pass complete. Review before submitting.")
            time.sleep(5)
        except Exception as exc:
            log_callback(f"Form-fill workflow failed with {exc}")
        finally:
            browser.close()


def execute_traffic_domino(context_data, log_callback):
    log_callback("Traffic delay detected. Triggering commute protocol.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=600)
        try:
            page = browser.new_page()

            log_callback("Opening communication channel placeholder.")
            page.goto("https://www.google.com", wait_until="domcontentloaded")
            search_box = page.locator("textarea[name='q']").first
            if search_box.count():
                search_box.fill(
                    f"Message to {context_data['boss_name']}: Stuck in traffic, running 20 minutes late."
                )
            time.sleep(2)

            log_callback("Opening calendar.")
            page.goto(context_data["calendar_url"], wait_until="domcontentloaded")
            time.sleep(2)
            log_callback("Traffic protocol complete. Team and schedule surfaces opened.")
        finally:
            browser.close()


def execute_sick_domino(context_data, log_callback):
    log_callback("Sick day detected. Triggering health absence protocol.")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=600)
        try:
            page = browser.new_page()

            log_callback("Opening communication channel placeholder.")
            page.goto("https://www.google.com", wait_until="domcontentloaded")
            search_box = page.locator("textarea[name='q']").first
            if search_box.count():
                search_box.fill(
                    f"Message to {context_data['boss_name']}: I am unwell today and need to take a sick day."
                )
            time.sleep(2)

            log_callback("Opening calendar.")
            page.goto(context_data["calendar_url"], wait_until="domcontentloaded")
            time.sleep(2)
            log_callback("Sick day protocol complete. Communication and calendar surfaces opened.")
        finally:
            browser.close()


# ==========================================
# UI
# ==========================================
class AgentUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AI Chief of Staff")
        self.geometry("540x620")
        self.attributes("-topmost", True)

        self.title_label = ctk.CTkLabel(self, text="AI Chief of Staff", font=("Arial", 24, "bold"))
        self.title_label.pack(pady=20)

        self.status_label = ctk.CTkLabel(
            self,
            text="Delivery | Form Fill | Gemini Routing",
            font=("Arial", 14),
        )
        self.status_label.pack(pady=(0, 10))

        self.input_box = ctk.CTkEntry(self, width=480, placeholder_text="Describe the task...")
        self.input_box.pack(pady=10)
        self.input_box.bind("<Return>", self.process_command)

        self.log_box = ctk.CTkTextbox(self, width=480, height=410, state="disabled", font=("Courier New", 12))
        self.log_box.pack(pady=10)

        router_mode = "Gemini" if GEMINI_MODEL else "Heuristic fallback"
        self.log_message(f"System initialized. Router mode: {router_mode}.")
        self.log_message("Supported flows: delivery, form fill, domino_sick, domino_traffic.")

    def log_message(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def process_command(self, event=None):
        user_text = self.input_box.get()
        if not user_text.strip():
            return

        self.input_box.delete(0, "end")
        self.log_message("")
        self.log_message(f"> You: {user_text}")
        threading.Thread(target=self.run_automation, args=(user_text,), daemon=True).start()

    def run_automation(self, user_text):
        self.log_message("Thinking...")
        decision = get_ai_decision(user_text)
        action = decision.get("action", "unknown")
        self.log_message(f"Router output: {json.dumps(decision)}")

        if action == "delivery":
            execute_delivery(
                query=decision.get("query", "item"),
                sites=decision.get("sites", ["amazon", "flipkart"]),
                task=decision.get("task", "search"),
                log_callback=self.log_message,
            )
        elif action == "form_fill":
            execute_form_fill(
                url=decision.get("url", ""),
                profile_sources=decision.get("profile_sources", active_profile_sources()),
                log_callback=self.log_message,
            )
        elif action == "domino_traffic":
            execute_traffic_domino(DOMINO_CONTEXT, self.log_message)
        elif action == "domino_sick":
            execute_sick_domino(DOMINO_CONTEXT, self.log_message)
        elif action == "unknown":
            self.log_message("Unsupported request for this build. Try delivery, form filling, or domino status workflows.")
        else:
            self.log_message("Router error. Falling back was unsuccessful.")


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    app = AgentUI()
    app.mainloop()
