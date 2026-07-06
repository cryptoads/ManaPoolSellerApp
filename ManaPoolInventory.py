import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog

import gspread
from google.oauth2.service_account import Credentials

# ============================================================
# ManaPool Seller Dashboard
# Google Sheets = source of truth
# ManaBox CSV = merge/update input
# ManaPool API = product lookup + inventory push
# ============================================================

APP_TITLE = "ManaPool Seller Dashboard"
SHEET_NAME = "ManaPool"
SOLD_SHEET_NAME = "Sold Inventory"
CREDS_FILE = "credentials.json"
ENV_FILE = ".env"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

MANAPOOL_API_BASE_DEFAULT = "https://manapool.com/api/v1"

MANABOX_COLUMNS = [
    "Name",
    "Set code",
    "Set name",
    "Collector number",
    "Foil",
    "Rarity",
    "Quantity",
    "ManaBox ID",
    "Scryfall ID",
    "Purchase price",
    "Misprint",
    "Altered",
    "Condition",
    "Language",
    "Purchase price currency",
]

LEDGER_COLUMNS = [
    "Key",
    "Selling",
    "Is Listed",
    "Name",
    "Set code",
    "Set name",
    "Collector number",
    "Foil",
    "Rarity",
    "Condition",
    "Language",
    "Scryfall ID",
    "ManaBox ID",
    "Quantity Owned",
    "Quantity Listed",
    "Sell Quantity",
    "Purchase price",
    "Best Price",
    "List Price",
    "Listed Price",
    "ManaPool Product ID",
    "TCGPlayer Product ID",
    "TCGPlayer SKU",
    "Last Imported",
    "Last Updated",
    "Best Price Updated",
    "Listed Price Updated",
    "Last Listed",
]

TABLE_COLUMNS = [
    "Selling",
    "Is Listed",
    "Name",
    "Set code",
    "Collector number",
    "Foil",
    "Rarity",
    "Condition",
    "Language",
    "Quantity Owned",
    "Sell Quantity",
    "Quantity Listed",
    "Best Price",
    "List Price",
    "Listed Price",
]

BOOL_TRUE_VALUES = {"true", "1", "yes", "y", "✔", "x"}


MANAPOOL_CONDITIONS = [
    ("near_mint", "NM"),
    ("lightly_played", "LP"),
    ("moderately_played", "MP"),
    ("heavily_played", "HP"),
    ("damaged", "DMG"),
]
MANAPOOL_CONDITION_VALUES = [value for value, _ in MANAPOOL_CONDITIONS]
MANAPOOL_CONDITION_BY_ID = {condition_id: value for value, condition_id in MANAPOOL_CONDITIONS}


# ============================================================
# Environment
# ============================================================

def load_env_file():
    env_path = Path(__file__).parent / ENV_FILE
    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ[key.strip()] = value.strip().strip('"').strip("'")


load_env_file()


# ============================================================
# Helpers
# ============================================================

def safe(value):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    return str(value).strip()


def safe_int(value, default=0):
    try:
        text = safe(value)
        if text == "":
            return default
        return int(float(text))
    except Exception:
        return default


def safe_float(value, default=0.0):
    try:
        text = safe(value).replace("$", "").replace(",", "")
        if text == "":
            return default
        return float(text)
    except Exception:
        return default


def bool_from_value(value):
    return safe(value).lower() in BOOL_TRUE_VALUES


def bool_text(value):
    return "TRUE" if bool_from_value(value) or value is True else "FALSE"


def price_text(value):
    number = safe_float(value)
    if number <= 0:
        return ""
    return f"{number:.2f}"


def money(value):
    number = safe_float(value)
    if number <= 0:
        return ""
    return f"${number:,.2f}"


def safe_collector_number(value):
    text = safe(value)
    if text == "":
        return ""
    try:
        number = float(text)
        if number.is_integer():
            return str(int(number))
    except Exception:
        pass
    return text


def map_condition(value):
    text = safe(value).lower()
    mapping = {
        "near_mint": "NM",
        "near mint": "NM",
        "nm": "NM",
        "lightly_played": "LP",
        "lightly played": "LP",
        "lp": "LP",
        "moderately_played": "MP",
        "moderately played": "MP",
        "mp": "MP",
        "heavily_played": "HP",
        "heavily played": "HP",
        "hp": "HP",
        "damaged": "DMG",
        "dmg": "DMG",
    }
    return mapping.get(text, "NM")


def normalize_condition(value):
    condition_id = map_condition(value)
    return MANAPOOL_CONDITION_BY_ID.get(condition_id, "near_mint")


def map_language(value):
    text = safe(value).lower()
    mapping = {
        "en": "EN",
        "english": "EN",
        "ja": "JA",
        "japanese": "JA",
        "de": "DE",
        "german": "DE",
        "fr": "FR",
        "french": "FR",
        "es": "ES",
        "spanish": "ES",
        "it": "IT",
        "italian": "IT",
        "pt": "PT",
        "portuguese": "PT",
        "ko": "KO",
        "korean": "KO",
        "ru": "RU",
        "russian": "RU",
        "zhs": "CS",
        "zh-cn": "CS",
        "zht": "CT",
        "zh-tw": "CT",
    }
    return mapping.get(text, text.upper() if text else "EN")


def map_finish(value):
    text = safe(value).lower()
    if text in ["foil", "fo", "f"]:
        return "FO"
    if text in ["etched", "e"]:
        return "ET"
    return "NF"


def inventory_key(name, set_code, collector, foil, condition, language, scryfall_id):
    return "|".join([
        safe(name),
        safe(set_code),
        safe_collector_number(collector),
        safe(foil).lower(),
        safe(condition).lower(),
        safe(language).lower(),
        safe(scryfall_id),
    ])


def row_key(row):
    return inventory_key(
        row.get("Name"),
        row.get("Set code"),
        row.get("Collector number"),
        row.get("Foil"),
        row.get("Condition"),
        row.get("Language"),
        row.get("Scryfall ID"),
    )


def make_empty_ledger():
    return pd.DataFrame(columns=LEDGER_COLUMNS).astype("object")


def ensure_ledger_columns(df):
    df = df.copy().astype("object")
    for col in LEDGER_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[LEDGER_COLUMNS]


def normalize_ledger_df(df):
    if df is None or df.empty:
        return make_empty_ledger()

    df = ensure_ledger_columns(df)

    for idx, row in df.iterrows():
        df.at[idx, "Selling"] = bool_text(row.get("Selling"))
        df.at[idx, "Is Listed"] = bool_text(row.get("Is Listed"))
        df.at[idx, "Collector number"] = safe_collector_number(row.get("Collector number"))
        df.at[idx, "Condition"] = normalize_condition(row.get("Condition"))
        if safe(row.get("Key")) == "":
            df.at[idx, "Key"] = row_key(df.loc[idx])
        df.at[idx, "Quantity Owned"] = str(safe_int(row.get("Quantity Owned")))
        df.at[idx, "Quantity Listed"] = str(safe_int(row.get("Quantity Listed")))
        df.at[idx, "Sell Quantity"] = str(safe_int(row.get("Sell Quantity")))
        df.at[idx, "Purchase price"] = price_text(row.get("Purchase price"))
        df.at[idx, "Best Price"] = price_text(row.get("Best Price"))
        df.at[idx, "List Price"] = price_text(row.get("List Price"))
        df.at[idx, "Listed Price"] = price_text(row.get("Listed Price"))

    return df.astype("object")


def normalize_manabox_csv(df):
    df = df.copy().astype("object")
    for col in MANABOX_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    rows = []
    now = datetime.now().isoformat()

    for _, row in df.iterrows():
        qty = safe_int(row.get("Quantity"))
        purchase_price = price_text(row.get("Purchase price"))
        key = row_key(row)

        rows.append({
            "Key": key,
            "Selling": "FALSE",
            "Is Listed": "FALSE",
            "Name": safe(row.get("Name")),
            "Set code": safe(row.get("Set code")),
            "Set name": safe(row.get("Set name")),
            "Collector number": safe_collector_number(row.get("Collector number")),
            "Foil": safe(row.get("Foil")),
            "Rarity": safe(row.get("Rarity")),
            "Condition": normalize_condition(row.get("Condition")),
            "Language": safe(row.get("Language")),
            "Scryfall ID": safe(row.get("Scryfall ID")),
            "ManaBox ID": safe(row.get("ManaBox ID")),
            "Quantity Owned": str(qty),
            "Quantity Listed": "0",
            "Sell Quantity": "0",
            "Purchase price": purchase_price,
            "Best Price": "",
            "List Price": purchase_price,
            "Listed Price": "",
            "ManaPool Product ID": "",
            "TCGPlayer Product ID": "",
            "TCGPlayer SKU": "",
            "Last Imported": now,
            "Last Updated": now,
            "Best Price Updated": "",
            "Listed Price Updated": "",
            "Last Listed": "",
        })

    return normalize_ledger_df(pd.DataFrame(rows))


# ============================================================
# Google Sheets
# ============================================================

class SheetsClient:
    def __init__(self):
        self.enabled = False
        self.error = None
        self.sheet = None
        self.connect()

    def connect(self):
        try:
            creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
            client = gspread.authorize(creds)
            spreadsheet = client.open(SHEET_NAME)
            self.sheet = spreadsheet.sheet1
            self.enabled = True
            self.error = None
        except Exception as exc:
            self.enabled = False
            self.error = str(exc)

    def read_inventory(self):
        if not self.enabled:
            raise RuntimeError(self.error or "Google Sheets is not connected.")
        records = self.sheet.get_all_records()
        if not records:
            return make_empty_ledger()
        return normalize_ledger_df(pd.DataFrame(records))

    def write_inventory(self, df):
        if not self.enabled:
            raise RuntimeError(self.error or "Google Sheets is not connected.")
        df = normalize_ledger_df(df)
        df = df.fillna("").astype(str)
        self.sheet.clear()
        self.sheet.append_row(LEDGER_COLUMNS)
        if not df.empty:
            self.sheet.append_rows(df[LEDGER_COLUMNS].values.tolist())

    def get_or_create_worksheet(self, title, rows=1000, cols=30):
        spreadsheet = self.sheet.spreadsheet

        try:
            return spreadsheet.worksheet(title)
        except gspread.WorksheetNotFound:
            return spreadsheet.add_worksheet(title=title, rows=rows, cols=cols)


    def append_sold_inventory(self, sold_row):
        sold_sheet = self.get_or_create_worksheet(SOLD_SHEET_NAME)

        headers = [
            "Sold At",
            "Name",
            "Set code",
            "Set name",
            "Collector number",
            "Foil",
            "Rarity",
            "Condition",
            "Language",
            "Scryfall ID",
            "ManaBox ID",
            "Quantity Sold",
            "Sold Price",
            "Total Sold",
            "Purchase price",
            "Listed Price",
            "ManaPool Product ID",
            "TCGPlayer SKU",
            "Key",
        ]

        existing = sold_sheet.get_all_values()

        # If sheet is empty, create the header.
        if not existing:
            sold_sheet.update(range_name="A1", values=[headers])
            next_row = 2
        else:
            # Do NOT clear existing sold inventory.
            # If headers differ, still append using our fixed column order.
            next_row = len(existing) + 1

            # If A1 is blank for some reason, write headers without deleting rows.
            if not existing[0] or not any(existing[0]):
                sold_sheet.update(range_name="A1", values=[headers])
                next_row = max(2, next_row)

        row_values = [safe(sold_row.get(col, "")) for col in headers]

        sold_sheet.update(
            range_name=f"A{next_row}:S{next_row}",
            values=[row_values]
        )

# ============================================================
# ManaPool API
# ============================================================

class ManaPoolAPI:
    def __init__(self):
        self.base_url = os.environ.get("MANAPOOL_API_BASE", MANAPOOL_API_BASE_DEFAULT).strip().rstrip("/")
        self.token = os.environ.get("MANAPOOL_API_TOKEN", "").strip()
        self.email = os.environ.get("MANAPOOL_API_EMAIL", "").strip()

    def headers(self):
        return {
            "X-ManaPool-Email": self.email,
            "X-ManaPool-Access-Token": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def request(self, method, path, **kwargs):
        if not self.token:
            raise RuntimeError("Missing MANAPOOL_API_TOKEN in .env")
        if not self.email:
            raise RuntimeError("Missing MANAPOOL_API_EMAIL in .env")

        url = f"{self.base_url}{path}"
        response = requests.request(method, url, headers=self.headers(), timeout=30, **kwargs)

        if response.status_code >= 400:
            raise RuntimeError(f"ManaPool API error {response.status_code}:\n{response.text}")

        try:
            return response.json()
        except Exception:
            return {"status_code": response.status_code, "text": response.text}

    def test_connection(self):
        return self.request("GET", "/seller/orders", params={"limit": 1})
    
    def build_unlist_payload(self, df):
        payload = self.build_inventory_payload(df)

        for item in payload.get("items", []):
            inventory = item.get("inventory", {})
            inventory["quantity"] = 0

        return payload

    def lookup_single_product(self, row):
        scryfall_id = safe(row.get("Scryfall ID"))
        if not scryfall_id:
            return {}

        params = {
            "scryfall_ids": scryfall_id,
            "languages": map_language(row.get("Language")),
        }

        result = self.request("GET", "/products/singles", params=params)
        if isinstance(result, dict):
            data = result.get("data")
            if isinstance(data, list) and data:
                return data[0]
        return {}

    def select_variant(self, product, row):
        variants = product.get("variants", []) if isinstance(product, dict) else []
        language = map_language(row.get("Language"))
        condition = map_condition(row.get("Condition"))
        finish = map_finish(row.get("Foil"))

        for variant in variants:
            if (
                variant.get("language_id") == language
                and variant.get("condition_id") == condition
                and variant.get("finish_id") == finish
            ):
                return variant
        return {}

    def get_best_price_for_row(self, row):
        # Tokens and ambiguous product cards may fail lookup. Caller should handle None.
        product = self.lookup_single_product(row)
        if not product:
            return None

        variant = self.select_variant(product, row)
        if not variant:
            return None

        low_price = variant.get("low_price")
        if not low_price:
            if map_finish(row.get("Foil")) == "FO":
                low_price = product.get("price_market_foil") or product.get("price_cents_nm_foil")
            else:
                low_price = product.get("price_market") or product.get("price_cents_nm")

        if not low_price:
            return None

        return {
            "best_price": round(safe_int(low_price) / 100, 2),
            "best_price_cents": safe_int(low_price),
            "product_id": safe(variant.get("product_id")),
            "tcgplayer_sku": safe(variant.get("tcgplayer_sku_id")),
            "tcgplayer_product_id": safe(product.get("tcgplayer_product_id")),
        }

    def build_inventory_payload(self, df):
        items = []
        warnings = []

        for _, row in df.iterrows():
            product = self.lookup_single_product(row)
            variant = self.select_variant(product, row) if product else {}

            product_id = safe(variant.get("product_id"))
            tcgplayer_sku = safe_int(variant.get("tcgplayer_sku_id"))
            tcgplayer_product_id = safe_int(product.get("tcgplayer_product_id")) if product else 0

            if not product_id or not tcgplayer_sku:
                warnings.append(f"{safe(row.get('Name'))} could not be matched to a ManaPool variant.")

            inventory = {
                "product_type": "mtg_single",
                "product_id": product_id,
                "product": {
                    "type": "mtg_single",
                    "id": product_id,
                    "tcgplayer_sku": tcgplayer_sku,
                    "single": {
                        "scryfall_id": safe(row.get("Scryfall ID")),
                        "tcgplayer_id": tcgplayer_product_id,
                        "name": safe(row.get("Name")),
                        "set": safe(row.get("Set code")),
                        "number": safe_collector_number(row.get("Collector number")),
                        "language_id": map_language(row.get("Language")),
                        "condition_id": map_condition(row.get("Condition")),
                        "finish_id": map_finish(row.get("Foil")),
                    },
                },
                "price_cents": int(round(safe_float(row.get("List Price")) * 100)),
                "quantity": safe_int(row.get("Sell Quantity")),
                "custom_external_id": safe(row.get("Key")) or row_key(row),
            }
            items.append({"inventory": inventory})

        return {"items": items, "warnings": warnings}

    def push_inventory(self, payload):
        results = []
        for item in payload.get("items", []):
            inventory = item.get("inventory", {})
            sku = inventory.get("product", {}).get("tcgplayer_sku", 0)
            product_id = inventory.get("product_id", "")

            if sku:
                path = f"/seller/inventory/tcgsku/{sku}"
            elif product_id:
                path = f"/seller/inventory/product/mtg_single/{product_id}"
            else:
                raise RuntimeError(f"Cannot push unmatched item: {inventory.get('product', {}).get('single', {}).get('name', '')}")

            results.append(self.request("PUT", path, json=inventory))

        return {"updated": len(results), "results": results}
    def get_seller_inventory(self):
        return self.request("GET", "/seller/inventory")


# ============================================================
# GUI App
# ============================================================

class ManaPoolSellerDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1280x760")
        self.root.minsize(1180, 680)
        self.root.configure(bg="#111827")

        self.df = make_empty_ledger()
        self.filtered_df = make_empty_ledger()
        self.sheets = SheetsClient()
        self.manapool_api = ManaPoolAPI()

        self.search_var = tk.StringVar()
        self.rarity_var = tk.StringVar(value="All")
        self.min_price_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Ready")
        self.total_cards_var = tk.StringVar(value="0")
        self.listed_cards_var = tk.StringVar(value="0")
        self.selling_cards_var = tk.StringVar(value="0")
        self.value_var = tk.StringVar(value="$0.00")
        self.sold_import_as_of_var = tk.StringVar(value=datetime.now().date().isoformat())

        self.pricing_mode_var = tk.StringVar(value="Undercut $0.01")
        self.undercut_percent_var = tk.StringVar(value="3")
        self.floor_price_var = tk.StringVar(value="0.10")

        self.active_view = "collection"
        self.sort_column = None
        self.sort_reverse = False
        self.context_row_id = None

        self.build_styles()
        self.build_ui()
        self.root.after(150, self.load_from_google_sheets)
        

    # ---------- UI ----------
    def build_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#0f172a", foreground="#e5e7eb", fieldbackground="#0f172a", rowheight=28)
        style.map("Treeview", background=[("selected", "#2563eb")])
        style.configure("Treeview.Heading", background="#1f2937", foreground="#f9fafb", font=("Segoe UI", 9, "bold"))

    def button(self, parent, text, command, primary=False):
        return tk.Button(
            parent,
            text=text,
            command=command,
            bg="#2563eb" if primary else "#374151",
            fg="#ffffff",
            activebackground="#1d4ed8" if primary else "#4b5563",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=10,
            pady=5,
            font=("Segoe UI", 9, "bold"),
        )

    def build_ui(self):
        header = tk.Frame(self.root, bg="#111827")
        header.pack(fill=tk.X, padx=12, pady=(10, 4))

        left = tk.Frame(header, bg="#111827")
        left.pack(side=tk.LEFT)
        tk.Label(left, text="ManaPool Seller Dashboard", bg="#111827", fg="#f9fafb", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tk.Label(left, text="Sheets-first MTG listing manager", bg="#111827", fg="#9ca3af", font=("Segoe UI", 9)).pack(anchor="w")

        actions = tk.Frame(header, bg="#111827")
        # Legacy all-in-one toolbar is kept constructed but hidden; tabbed action bars below expose scoped controls.

        # ---- DATA GROUP ----
        data_frame = tk.LabelFrame(actions, text="Data", bg="#111827", fg="#e5e7eb")
        data_frame.pack(side=tk.LEFT, padx=4)

        self.button(data_frame, "Reload", self.load_from_google_sheets).pack(side=tk.LEFT, padx=2)
        self.button(data_frame, "Merge CSV", self.import_csv).pack(side=tk.LEFT, padx=2)
        self.button(data_frame, "Sync Sheets", self.sync_sheets).pack(side=tk.LEFT, padx=2)
        self.button(data_frame, "Sync MP", self.sync_from_manapool).pack(side=tk.LEFT, padx=2)

        # ---- PRICING GROUP ----
        pricing_frame = tk.LabelFrame(actions, text="Pricing", bg="#111827", fg="#e5e7eb")
        pricing_frame.pack(side=tk.LEFT, padx=4)

        self.button(pricing_frame, "Refresh Prices", self.refresh_best_prices).pack(side=tk.LEFT, padx=2)
        self.button(pricing_frame, "Smart Price", self.update_listed_prices_to_best).pack(side=tk.LEFT, padx=2)

        # ---- LISTING GROUP ----
        listing_frame = tk.LabelFrame(actions, text="Listing", bg="#111827", fg="#e5e7eb")
        listing_frame.pack(side=tk.LEFT, padx=4)
        self.button(listing_frame, "Select Listed", self.select_all_listed).pack(side=tk.LEFT, padx=2)
        self.button(listing_frame, "Mark Max", self.mark_selected_max_for_sale).pack(side=tk.LEFT, padx=2)
        self.button(listing_frame, "Mark Sold", self.mark_selected_sold).pack(side=tk.LEFT, padx=2)
        self.button(listing_frame, "Unlist Selected", self.unlist_selected_from_manapool).pack(side=tk.LEFT, padx=2)
        self.button(listing_frame, "Push API", self.api_push_selected, primary=True).pack(side=tk.LEFT, padx=2)

        menu_button = tk.Menubutton(actions, text="⚙️ More", bg="#374151", fg="#fff", relief=tk.FLAT)
        menu_button.pack(side=tk.LEFT, padx=6)

        menu = tk.Menu(menu_button, tearoff=0)
        menu_button.config(menu=menu)

        menu.add_command(label="API Test", command=self.api_test_connection)
        menu.add_command(label="Dry Run", command=self.api_dry_run)


        metrics = tk.Frame(self.root, bg="#111827")
        metrics.pack(fill=tk.X, padx=12, pady=4)
        self.metric(metrics, "Owned", self.total_cards_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.metric(metrics, "Listed", self.listed_cards_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.metric(metrics, "Selected to Push", self.selling_cards_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)
        self.metric(metrics, "List Value", self.value_var).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=4)

        self.view_tabs = ttk.Notebook(self.root)
        self.view_tabs.pack(fill=tk.X, padx=12, pady=(4, 0))
        self.view_tabs.bind("<<NotebookTabChanged>>", self.handle_view_changed)

        collection_tab = tk.Frame(self.view_tabs, bg="#111827")
        listed_tab = tk.Frame(self.view_tabs, bg="#111827")
        sold_tab = tk.Frame(self.view_tabs, bg="#111827")
        tools_tab = tk.Frame(self.view_tabs, bg="#111827")

        self.view_tabs.add(collection_tab, text="Collection")
        self.view_tabs.add(listed_tab, text="Listed")
        self.view_tabs.add(sold_tab, text="Sold")
        self.view_tabs.add(tools_tab, text="Tools")

        collection_actions = tk.Frame(collection_tab, bg="#111827")
        collection_actions.pack(fill=tk.X, padx=8, pady=8)
        self.button(collection_actions, "Reload", self.load_from_google_sheets).pack(side=tk.LEFT, padx=2)
        self.button(collection_actions, "Merge CSV", self.import_csv).pack(side=tk.LEFT, padx=2)
        self.button(collection_actions, "Sync Sheets", self.sync_sheets).pack(side=tk.LEFT, padx=2)
        self.button(collection_actions, "Mark Max", self.mark_selected_max_for_sale).pack(side=tk.LEFT, padx=2)

        listed_actions = tk.Frame(listed_tab, bg="#111827")
        listed_actions.pack(fill=tk.X, padx=8, pady=8)
        self.button(listed_actions, "Sync MP", self.sync_from_manapool).pack(side=tk.LEFT, padx=2)
        self.button(listed_actions, "Select Listed", self.select_all_listed).pack(side=tk.LEFT, padx=2)
        self.button(listed_actions, "Refresh Prices", self.refresh_best_prices).pack(side=tk.LEFT, padx=2)
        self.button(listed_actions, "Smart Price", self.update_listed_prices_to_best).pack(side=tk.LEFT, padx=2)
        self.button(listed_actions, "Unlist Selected", self.unlist_selected_from_manapool).pack(side=tk.LEFT, padx=2)
        self.button(listed_actions, "Push API", self.api_push_selected, primary=True).pack(side=tk.LEFT, padx=2)

        sold_actions = tk.Frame(sold_tab, bg="#111827")
        sold_actions.pack(fill=tk.X, padx=8, pady=8)
        self.button(sold_actions, "Mark Sold", self.mark_selected_sold).pack(side=tk.LEFT, padx=2)
        tk.Label(sold_actions, text="Import as-of", bg="#111827", fg="#d1d5db").pack(side=tk.LEFT, padx=(12, 4))
        tk.Entry(sold_actions, textvariable=self.sold_import_as_of_var, width=12).pack(side=tk.LEFT, padx=2)
        self.button(sold_actions, "Review Sold", self.review_sold_import).pack(side=tk.LEFT, padx=2)

        tools_actions = tk.Frame(tools_tab, bg="#111827")
        tools_actions.pack(fill=tk.X, padx=8, pady=8)
        self.button(tools_actions, "API Test", self.api_test_connection).pack(side=tk.LEFT, padx=2)
        self.button(tools_actions, "Dry Run", self.api_dry_run).pack(side=tk.LEFT, padx=2)

        controls = tk.Frame(self.root, bg="#111827")
        controls.pack(fill=tk.X, padx=12, pady=4)
        tk.Label(controls, text="Search", bg="#111827", fg="#d1d5db").pack(side=tk.LEFT)
        tk.Entry(controls, textvariable=self.search_var, width=32).pack(side=tk.LEFT, padx=6)

        tk.Label(controls, text="Pricing", bg="#111827", fg="#d1d5db").pack(side=tk.LEFT, padx=(12, 4))

        pricing = ttk.Combobox(
            controls,
            textvariable=self.pricing_mode_var,
            width=16,
            values=["Match Best Price", "Undercut $0.01", "Undercut %"],
            state="readonly"
        )
        pricing.pack(side=tk.LEFT, padx=4)

        tk.Label(controls, text="Undercut %", bg="#111827", fg="#d1d5db").pack(side=tk.LEFT, padx=(8, 4))
        tk.Entry(controls, textvariable=self.undercut_percent_var, width=5).pack(side=tk.LEFT)

        tk.Label(controls, text="Floor $", bg="#111827", fg="#d1d5db").pack(side=tk.LEFT, padx=(8, 4))
        tk.Entry(controls, textvariable=self.floor_price_var, width=6).pack(side=tk.LEFT)
        self.search_var.trace_add("write", lambda *_: self.apply_filters())
        tk.Label(controls, text="Rarity", bg="#111827", fg="#d1d5db").pack(side=tk.LEFT, padx=(12, 4))
        rarity = ttk.Combobox(controls, textvariable=self.rarity_var, width=11, values=["All", "common", "uncommon", "rare", "mythic"], state="readonly")
        rarity.pack(side=tk.LEFT)
        rarity.bind("<<ComboboxSelected>>", lambda *_: self.apply_filters())
        self.button(controls, "Select Filtered", self.select_filtered).pack(side=tk.LEFT, padx=6)
        self.button(controls, "Clear Filtered", self.clear_filtered).pack(side=tk.LEFT, padx=2)

        table_wrap = tk.Frame(self.root, bg="#111827")
        table_wrap.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)

        # Tree
        self.tree = ttk.Treeview(table_wrap, show="headings", selectmode="browse")

        # Scrollbars
        yscroll = ttk.Scrollbar(table_wrap, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_wrap, orient="horizontal", command=self.tree.xview)

        # Configure scrolling
        self.tree.configure(
            yscrollcommand=yscroll.set,
            xscrollcommand=xscroll.set
        )

        # Layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        # Make table expand properly
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self.handle_double_click)
        self.tree.bind("<Button-3>", self.show_table_context_menu)
        self.configure_table()

        self.table_menu = tk.Menu(self.root, tearoff=0)
        self.table_menu.add_command(label="Change card/set details", command=self.change_card_set_details)
        self.table_menu.add_command(label="Change grading for one copy", command=self.split_one_copy_to_condition)

        self.output_box = scrolledtext.ScrolledText(self.root, height=6, bg="#030712", fg="#e5e7eb", insertbackground="#e5e7eb")
        self.output_box.pack(fill=tk.X, padx=12, pady=(4, 0))

        footer = tk.Frame(self.root, bg="#030712")
        footer.pack(fill=tk.X)
        tk.Label(footer, textvariable=self.status_var, bg="#030712", fg="#d1d5db", anchor="w").pack(fill=tk.X, padx=10, pady=4)

    def metric(self, parent, label, variable):
        frame = tk.Frame(parent, bg="#1f2937", highlightthickness=1, highlightbackground="#374151")
        tk.Label(frame, text=label, bg="#1f2937", fg="#9ca3af", font=("Segoe UI", 8)).pack(anchor="w", padx=10, pady=(6, 0))
        tk.Label(frame, textvariable=variable, bg="#1f2937", fg="#f9fafb", font=("Segoe UI", 15, "bold")).pack(anchor="w", padx=10, pady=(0, 6))
        return frame

    def configure_table(self):
        widths = {
            "Selling": 65,
            "Is Listed": 70,
            "Name": 230,
            "Set code": 70,
            "Collector number": 90,
            "Foil": 70,
            "Rarity": 80,
            "Condition": 90,
            "Language": 75,
            "Quantity Owned": 95,
            "Sell Quantity": 95,
            "Quantity Listed": 95,
            "Best Price": 85,
            "List Price": 85,
            "Listed Price": 90,
        }
        self.tree["columns"] = TABLE_COLUMNS
        for col in TABLE_COLUMNS:
            self.tree.heading(col, text=col, command=lambda c=col: self.sort_by(c))
            self.tree.column(col, width=widths.get(col, 100), anchor="center")
        self.tree.tag_configure("selling", background="#064e3b", foreground="#ecfdf5")
        self.tree.tag_configure("listed", background="#1e3a8a", foreground="#eff6ff")
        self.tree.tag_configure("rare", background="#422006", foreground="#fffbeb")
        self.tree.tag_configure("mythic", background="#3b0764", foreground="#f5f3ff")
        self.tree.tag_configure("normal", background="#0f172a", foreground="#e5e7eb")

    def handle_view_changed(self, event=None):
        selected_tab = self.view_tabs.tab(self.view_tabs.select(), "text").lower()
        if selected_tab == "listed":
            self.active_view = "listed"
        elif selected_tab == "sold":
            self.active_view = "sold"
        elif selected_tab == "tools":
            self.active_view = "tools"
        else:
            self.active_view = "collection"
        self.apply_filters(keep_status=True)
        self.set_status(f"Viewing {selected_tab}.")

    def handle_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return

        row_id = self.tree.identify_row(event.y)
        column_id = self.tree.identify_column(event.x)

        if not row_id or not column_id:
            return

        col_index = int(column_id.replace("#", "")) - 1
        column_name = TABLE_COLUMNS[col_index]

        if column_name in ["Sell Quantity", "List Price", "Condition"]:
            self.edit_cell(row_id, column_name)
        else:
            self.toggle_selected_row()

    def show_table_context_menu(self, event):
        row_id = self.tree.identify_row(event.y)
        if not row_id:
            return

        self.tree.selection_set(row_id)
        self.tree.focus(row_id)
        self.context_row_id = row_id

        idx = int(row_id)
        can_split = safe_int(self.df.at[idx, "Quantity Owned"]) > 1
        self.table_menu.entryconfig("Change card/set details", state=tk.NORMAL)
        self.table_menu.entryconfig(
            "Change grading for one copy",
            state=tk.NORMAL if can_split else tk.DISABLED,
        )
        self.table_menu.tk_popup(event.x_root, event.y_root)
        self.table_menu.grab_release()

    def select_all_listed(self):
        if self.df.empty:
            return

        count = 0

        for idx, row in self.df.iterrows():
            if bool_from_value(row.get("Is Listed")) and safe_int(row.get("Quantity Listed")) > 0:
                self.df.at[idx, "Selling"] = "TRUE"
                count += 1

        self.apply_filters(keep_status=True)
        self.set_status(f"Selected {count} currently listed rows.")

    def unlist_selected_from_manapool(self):
        if self.df.empty:
            return

        selected = self.df[
            self.df["Selling"].apply(bool_from_value)
            & self.df["Is Listed"].apply(bool_from_value)
            & (self.df["Quantity Listed"].apply(safe_int) > 0)
        ].copy()

        if selected.empty:
            messagebox.showwarning(
                "No Listed Rows Selected",
                "Select listed rows first. Use Select Listed, then remove any cards you do not want to unlist."
            )
            return

        if not messagebox.askyesno(
            "Confirm Unlist",
            f"This will set quantity to 0 for {len(selected)} selected ManaPool listings.\n\nContinue?"
        ):
            return

        try:
            payload = self.manapool_api.build_unlist_payload(selected)

            if payload.get("warnings"):
                proceed = messagebox.askyesno(
                    "Unlist Warnings",
                    f"{len(payload['warnings'])} selected rows had product mapping warnings.\n\n"
                    "Only mapped rows can be unlisted reliably.\n\nContinue anyway?"
                )
                if not proceed:
                    return

            result = self.manapool_api.push_inventory(payload)

            now = datetime.now().isoformat()

            for idx in selected.index:
                self.df.at[idx, "Is Listed"] = "FALSE"
                self.df.at[idx, "Quantity Listed"] = "0"
                self.df.at[idx, "Listed Price"] = ""
                self.df.at[idx, "Listed Price Updated"] = now
                self.df.at[idx, "Selling"] = "FALSE"
                self.df.at[idx, "Sell Quantity"] = "0"
                self.df.at[idx, "Last Updated"] = now

            self.df = normalize_ledger_df(self.df)
            self.sheets.write_inventory(self.df)
            self.apply_filters(keep_status=True)

            messagebox.showinfo(
                "Unlist Complete",
                f"Unlisted {len(selected)} rows from ManaPool."
            )

        except Exception as exc:
            self.log_output(f"Unlist Failed: {exc}")
            messagebox.showerror("Unlist Failed", str(exc))

    def edit_cell(self, row_id, column_name):
        idx = int(row_id)

        bbox = self.tree.bbox(row_id, f"#{TABLE_COLUMNS.index(column_name) + 1}")
        if not bbox:
            return

        x, y, width, height = bbox

        current_value = self.df.at[idx, column_name]

        if column_name == "Condition":
            editor_var = tk.StringVar(value=normalize_condition(current_value))
            editor = ttk.Combobox(
                self.tree,
                textvariable=editor_var,
                values=MANAPOOL_CONDITION_VALUES,
                state="readonly",
            )
            editor.place(x=x, y=y, width=width, height=height)
            editor.focus()
        else:
            editor = tk.Entry(self.tree)
            editor.place(x=x, y=y, width=width, height=height)
            editor.insert(0, safe(current_value))
            editor.focus()
            editor.select_range(0, tk.END)

        edit_finished = {"value": False}

        def save_edit(event=None):
            if edit_finished["value"]:
                return
            edit_finished["value"] = True
            new_value = editor.get().strip()
            editor.destroy()

            if column_name == "Sell Quantity":
                qty = safe_int(new_value)
                owned = safe_int(self.df.at[idx, "Quantity Owned"])

                if qty < 0:
                    messagebox.showerror("Invalid Quantity", "Sell Quantity cannot be negative.")
                    return

                if qty > owned:
                    messagebox.showerror("Invalid Quantity", "Sell Quantity cannot exceed Quantity Owned.")
                    return

                self.df.at[idx, "Sell Quantity"] = str(qty)

                if qty > 0:
                    self.df.at[idx, "Selling"] = "TRUE"

            elif column_name == "List Price":
                price = safe_float(new_value)

                if price < 0:
                    messagebox.showerror("Invalid Price", "List Price cannot be negative.")
                    return

                self.df.at[idx, "List Price"] = price_text(price)

            elif column_name == "Condition":
                self.df.at[idx, "Condition"] = normalize_condition(new_value)
                self.df.at[idx, "Key"] = row_key(self.df.loc[idx])

            self.df = normalize_ledger_df(self.df)
            self.apply_filters(keep_status=True)
            self.set_status(f"Updated {column_name}.")

        def cancel_edit(event=None):
            if edit_finished["value"]:
                return
            edit_finished["value"] = True
            editor.destroy()

        editor.bind("<Return>", save_edit)
        editor.bind("<FocusOut>", save_edit)
        editor.bind("<Escape>", cancel_edit)
        if column_name == "Condition":
            editor.bind("<<ComboboxSelected>>", save_edit)
            editor.event_generate("<Button-1>")

    # ---------- Logging / status ----------
    def log_output(self, text):
        print(text)
        if hasattr(self, "output_box"):
            self.output_box.insert(tk.END, str(text) + "\n")
            self.output_box.see(tk.END)

    def set_status(self, text):
        self.status_var.set(text)

    # ---------- Data loading ----------
    def load_from_google_sheets(self):
        try:
            self.df = self.sheets.read_inventory()
            self.apply_filters()
            self.set_status(f"Loaded {len(self.df)} rows from Google Sheets.")
        except Exception as exc:
            self.log_output(f"Google Sheets Load Error: {exc}")
            self.set_status("Could not load Google Sheets inventory.")

    def sync_sheets(self):
        try:
            self.sheets.write_inventory(self.df)
            self.set_status("Synced inventory to Google Sheets.")
        except Exception as exc:
            self.log_output(f"Google Sheets Sync Error: {exc}")
            messagebox.showerror("Google Sheets Error", str(exc))

    def review_sold_import(self):
        as_of_text = self.sold_import_as_of_var.get().strip()
        try:
            datetime.strptime(as_of_text, "%Y-%m-%d")
        except ValueError:
            messagebox.showerror("Invalid Date", "Use YYYY-MM-DD for the sold import as-of date.")
            return

        messagebox.showinfo(
            "Sold Import Review",
            "Sold import review is ready for the ManaPool order matching step.\n\n"
            f"As-of date: {as_of_text}\n\n"
            "Planned behavior:\n"
            "- Sales before this date default to tracking-only import.\n"
            "- Sales on or after this date default to inventory-adjusting import.\n"
            "- Each matched sale will require approval before inventory changes."
        )
        self.set_status(f"Sold import review as-of date set to {as_of_text}.")

    def import_csv(self):
        file_path = filedialog.askopenfilename(title="Select ManaBox CSV", filetypes=[("CSV files", "*.csv")])
        if not file_path:
            return

        try:
            incoming = normalize_manabox_csv(pd.read_csv(file_path))
            existing = self.sheets.read_inventory()
            now = datetime.now().isoformat()

            existing_keys = set(existing["Key"].astype(str)) if not existing.empty else set()
            incoming_keys = set(incoming["Key"].astype(str))
            duplicates = incoming_keys.intersection(existing_keys)

            increase_qty = False
            if duplicates:
                answer = messagebox.askyesnocancel(
                    "Duplicates Found",
                    f"Found {len(duplicates)} duplicate card rows.\n\n"
                    "Yes = increase Quantity Owned\n"
                    "No = keep existing rows unchanged\n"
                    "Cancel = stop import"
                )
                if answer is None:
                    return
                increase_qty = answer

            rows = []
            existing_by_key = {safe(row.get("Key")): row.to_dict() for _, row in existing.iterrows()}

            # Preserve and optionally update existing rows
            for _, old in existing.iterrows():
                row = old.to_dict()
                key = safe(row.get("Key"))
                if key in incoming_keys and increase_qty:
                    incoming_row = incoming[incoming["Key"] == key].iloc[0]
                    row["Quantity Owned"] = str(safe_int(row.get("Quantity Owned")) + safe_int(incoming_row.get("Quantity Owned")))
                    row["Last Imported"] = now
                    row["Last Updated"] = now
                rows.append(row)

            # Add new rows
            for _, inc in incoming.iterrows():
                key = safe(inc.get("Key"))
                if key not in existing_keys:
                    row = inc.to_dict()
                    row["Last Imported"] = now
                    row["Last Updated"] = now
                    rows.append(row)

            self.df = normalize_ledger_df(pd.DataFrame(rows))
            self.sheets.write_inventory(self.df)
            self.apply_filters()
            self.set_status(f"Merged {len(incoming)} CSV rows into Google Sheets.")
        except Exception as exc:
            self.log_output(f"CSV Import Error: {exc}")
            messagebox.showerror("Import Error", str(exc))

    def manapool_inventory_to_row(self, item):
        if not isinstance(item, dict):
            return None

        inv = item.get("inventory", item)
        if not isinstance(inv, dict):
            return None

        product = inv.get("product") or {}
        product_type = safe(inv.get("product_type") or product.get("type"))

        if product_type != "mtg_single":
            return None
        if not isinstance(product, dict):
            product = {}

        single = product.get("single") or {}
        if not isinstance(single, dict):
            single = {}

        quantity = safe_int(inv.get("quantity"))
        if quantity <= 0:
             return None
        price = round(safe_int(inv.get("price_cents")) / 100, 2)

        finish_id = safe(single.get("finish_id")).upper()
        condition_id = safe(single.get("condition_id")).upper()
        language_id = safe(single.get("language_id")).upper()

        foil_text = {
            "FO": "foil",
            "NF": "normal",
            "ET": "etched",
        }.get(finish_id, "normal")

        condition_text = {
            "NM": "near_mint",
            "LP": "lightly_played",
            "MP": "moderately_played",
            "HP": "heavily_played",
            "DMG": "damaged",
        }.get(condition_id, condition_id.lower())

        language_text = language_id.lower() if language_id else "en"

        key = inventory_key(
            single.get("name"),
            single.get("set"),
            single.get("number"),
            foil_text,
            condition_text,
            language_text,
            single.get("scryfall_id"),
        )

        row = {
            "Key": key,
            "Selling": "FALSE",
            "Is Listed": "TRUE" if quantity > 0 else "FALSE",
            "Name": safe(single.get("name")),
            "Set code": safe(single.get("set")),
            "Set name": "",
            "Collector number": safe_collector_number(single.get("number")),
            "Foil": foil_text,
            "Rarity": "",
            "Condition": condition_text,
            "Language": language_text,
            "Scryfall ID": safe(single.get("scryfall_id")),
            "ManaBox ID": "",
            "Quantity Owned": str(quantity),
            "Quantity Listed": str(quantity),
            "Sell Quantity": "0",
            "Purchase price": "",
            "Best Price": "",
            "List Price": price_text(price),
            "Listed Price": price_text(price),
            "ManaPool Product ID": safe(inv.get("product_id") or product.get("id")),
            "TCGPlayer Product ID": safe(single.get("tcgplayer_id")),
            "TCGPlayer SKU": safe(product.get("tcgplayer_sku")),
            "Last Imported": "",
            "Last Updated": datetime.now().isoformat(),
            "Best Price Updated": "",
            "Listed Price Updated": datetime.now().isoformat(),
            "Last Listed": "",
        }

        return row
    
    def sync_from_manapool(self):
        try:
            result = self.manapool_api.get_seller_inventory()

            raw_items = (
                result.get("data")
                or result.get("items")
                or result.get("inventory")
                or []
            )

            if isinstance(raw_items, dict):
                raw_items = list(raw_items.values())

            now = datetime.now().isoformat()
            self.df = normalize_ledger_df(self.df)

            existing_by_key = {
                safe(row.get("Key")): idx
                for idx, row in self.df.iterrows()
            }

            added = 0
            updated = 0
            skipped = 0

            for item in raw_items:
                try:
                    mp_row = self.manapool_inventory_to_row(item)
                    if not mp_row:
                        skipped += 1
                        continue
                    key = safe(mp_row.get("Key"))

                    if not key:
                        skipped += 1
                        continue

                    matched_idx = self.find_matching_inventory_index(mp_row)

                    if matched_idx is not None:
                        idx = matched_idx

                        self.df.at[idx, "Is Listed"] = mp_row["Is Listed"]
                        self.df.at[idx, "Quantity Listed"] = mp_row["Quantity Listed"]
                        self.df.at[idx, "Listed Price"] = mp_row["Listed Price"]
                        self.df.at[idx, "List Price"] = mp_row["Listed Price"]
                        self.df.at[idx, "ManaPool Product ID"] = mp_row["ManaPool Product ID"]
                        self.df.at[idx, "TCGPlayer Product ID"] = mp_row["TCGPlayer Product ID"]
                        self.df.at[idx, "TCGPlayer SKU"] = mp_row["TCGPlayer SKU"]
                        self.df.at[idx, "Listed Price Updated"] = now
                        self.df.at[idx, "Last Updated"] = now

                        updated += 1

                    else:
                        mp_row["Last Imported"] = now
                        mp_row["Last Updated"] = now
                        self.df = pd.concat([self.df, pd.DataFrame([mp_row])], ignore_index=True)
                        added += 1

                except Exception as row_exc:
                    skipped += 1
                    self.log_output(f"ManaPool sync skipped row: {row_exc}")

            self.df = normalize_ledger_df(self.df)
            self.sheets.write_inventory(self.df)
            self.apply_filters(keep_status=True)

            messagebox.showinfo(
                "ManaPool Sync Complete",
                f"Updated existing rows: {updated}\n"
                f"Added ManaPool-only rows: {added}\n"
                f"Skipped rows: {skipped}"
            )

        except Exception as exc:
            self.log_output(f"ManaPool Sync Error: {exc}")
            messagebox.showerror("ManaPool Sync Error", str(exc))

    # ---------- Table rendering ----------
    def apply_filters(self, keep_status=False):
        df = normalize_ledger_df(self.df)
        if self.active_view == "listed":
            df = df[df["Quantity Listed"].apply(safe_int) > 0]
        elif self.active_view == "sold":
            df = df[
                df["Selling"].apply(bool_from_value)
                | (df["Quantity Listed"].apply(safe_int) > 0)
            ]
        query = self.search_var.get().strip().lower()
        if query:
            df = df[df.apply(lambda row: query in " ".join([safe(v).lower() for v in row.values]), axis=1)]
        rarity = self.rarity_var.get()
        if rarity != "All":
            df = df[df["Rarity"].astype(str).str.lower() == rarity.lower()]
        if self.sort_column and self.sort_column in df.columns:
            df = self.sort_dataframe(df, self.sort_column, self.sort_reverse)
        self.filtered_df = df
        self.render_table()
        if not keep_status:
            self.set_status(f"Showing {len(self.filtered_df)} of {len(self.df)} rows.")

    def render_table(self):
        self.tree.delete(*self.tree.get_children())
        for idx, row in self.filtered_df.iterrows():
            selling = bool_from_value(row.get("Selling"))
            listed = bool_from_value(row.get("Is Listed"))
            rarity = safe(row.get("Rarity")).lower()
            if selling:
                tag = "selling"
            elif listed:
                tag = "listed"
            elif rarity == "mythic":
                tag = "mythic"
            elif rarity == "rare":
                tag = "rare"
            else:
                tag = "normal"

            self.tree.insert("", "end", iid=str(idx), tags=(tag,), values=(
                "✔" if selling else "",
                "✔" if listed else "",
                safe(row.get("Name")),
                safe(row.get("Set code")),
                safe(row.get("Collector number")),
                safe(row.get("Foil")),
                safe(row.get("Rarity")),
                safe(row.get("Condition")),
                safe(row.get("Language")),
                safe_int(row.get("Quantity Owned")),
                safe_int(row.get("Sell Quantity")),
                safe_int(row.get("Quantity Listed")),
                money(row.get("Best Price")),
                money(row.get("List Price")),
                money(row.get("Listed Price")),
            ))
        self.update_metrics()

    def sort_by(self, column):
        if self.sort_column == column:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = column
            self.sort_reverse = False
        self.apply_filters(keep_status=True)

    def sort_dataframe(self, df, column, reverse):
        numeric = {"Quantity Owned", "Sell Quantity", "Quantity Listed", "Best Price", "List Price", "Listed Price", "Purchase price"}
        if column in numeric:
            return df.assign(_sort=df[column].apply(safe_float)).sort_values("_sort", ascending=not reverse).drop(columns=["_sort"])
        return df.sort_values(column, ascending=not reverse, key=lambda s: s.astype(str).str.lower())

    def update_metrics(self):
        owned = self.df["Quantity Owned"].apply(safe_int).sum() if not self.df.empty else 0
        listed = self.df["Quantity Listed"].apply(safe_int).sum() if not self.df.empty else 0
        selling = self.df[self.df["Selling"].apply(bool_from_value)]["Sell Quantity"].apply(safe_int).sum() if not self.df.empty else 0
        value = 0.0
        if not self.df.empty:
            listed_rows = self.df[self.df["Quantity Listed"].apply(safe_int) > 0]
            value = sum(listed_rows["Quantity Listed"].apply(safe_int) * listed_rows["Listed Price"].apply(safe_float))
        self.total_cards_var.set(f"{owned:,}")
        self.listed_cards_var.set(f"{listed:,}")
        self.selling_cards_var.set(f"{selling:,}")
        self.value_var.set(f"${value:,.2f}")

    def ask_condition(self, title, current_condition):
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.configure(bg="#111827")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        current = normalize_condition(current_condition)
        default_condition = next((condition for condition in MANAPOOL_CONDITION_VALUES if condition != current), current)
        selected = tk.StringVar(value=default_condition)
        result = {"condition": None}

        tk.Label(
            dialog,
            text="New condition",
            bg="#111827",
            fg="#e5e7eb",
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w", padx=12, pady=(12, 4))

        combo = ttk.Combobox(
            dialog,
            textvariable=selected,
            values=MANAPOOL_CONDITION_VALUES,
            state="readonly",
            width=24,
        )
        combo.pack(fill=tk.X, padx=12)
        combo.focus()

        buttons = tk.Frame(dialog, bg="#111827")
        buttons.pack(fill=tk.X, padx=12, pady=12)

        def choose():
            result["condition"] = normalize_condition(selected.get())
            dialog.destroy()

        def cancel():
            dialog.destroy()

        self.button(buttons, "Cancel", cancel).pack(side=tk.RIGHT, padx=(6, 0))
        self.button(buttons, "OK", choose, primary=True).pack(side=tk.RIGHT)
        dialog.bind("<Return>", lambda *_: choose())
        dialog.bind("<Escape>", lambda *_: cancel())

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.root.wait_window(dialog)

        return result["condition"]

    def ask_card_set_details(self, row):
        dialog = tk.Toplevel(self.root)
        dialog.title("Change Card / Set")
        dialog.configure(bg="#111827")
        dialog.resizable(False, False)
        dialog.transient(self.root)
        dialog.grab_set()

        fields = [
            ("Name", "Name"),
            ("Set code", "Set code"),
            ("Set name", "Set name"),
            ("Collector number", "Collector number"),
            ("Scryfall ID", "Scryfall ID"),
            ("Rarity", "Rarity"),
            ("ManaBox ID", "ManaBox ID"),
            ("Foil", "Foil"),
            ("Language", "Language"),
        ]
        variables = {}

        form = tk.Frame(dialog, bg="#111827")
        form.pack(fill=tk.BOTH, expand=True, padx=12, pady=(12, 6))

        for row_number, (label, column) in enumerate(fields):
            tk.Label(form, text=label, bg="#111827", fg="#e5e7eb").grid(row=row_number, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=safe(row.get(column)))
            variables[column] = var
            tk.Entry(form, textvariable=var, width=42).grid(row=row_number, column=1, sticky="ew", padx=(10, 0), pady=3)

        condition_row = len(fields)
        tk.Label(form, text="Condition", bg="#111827", fg="#e5e7eb").grid(row=condition_row, column=0, sticky="w", pady=3)
        condition_var = tk.StringVar(value=normalize_condition(row.get("Condition")))
        condition = ttk.Combobox(
            form,
            textvariable=condition_var,
            values=MANAPOOL_CONDITION_VALUES,
            state="readonly",
            width=39,
        )
        condition.grid(row=condition_row, column=1, sticky="ew", padx=(10, 0), pady=3)
        form.grid_columnconfigure(1, weight=1)

        result = {"values": None}
        buttons = tk.Frame(dialog, bg="#111827")
        buttons.pack(fill=tk.X, padx=12, pady=(4, 12))

        def choose():
            values = {column: var.get().strip() for column, var in variables.items()}
            values["Condition"] = normalize_condition(condition_var.get())
            result["values"] = values
            dialog.destroy()

        def cancel():
            dialog.destroy()

        self.button(buttons, "Cancel", cancel).pack(side=tk.RIGHT, padx=(6, 0))
        self.button(buttons, "OK", choose, primary=True).pack(side=tk.RIGHT)
        dialog.bind("<Return>", lambda *_: choose())
        dialog.bind("<Escape>", lambda *_: cancel())

        dialog.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_rooty() + (self.root.winfo_height() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        self.root.wait_window(dialog)

        return result["values"]

    def change_card_set_details(self):
        row_id = self.context_row_id or self.tree.focus()
        if not row_id:
            return

        idx = int(row_id)
        if idx not in self.df.index:
            return

        was_listed = safe_int(self.df.at[idx, "Quantity Listed"]) > 0
        if was_listed:
            proceed = messagebox.askyesno(
                "Change Listed Card",
                "This row is currently marked as listed.\n\n"
                "Changing the card/set will clear the local listed status and ManaPool mapping for this row. "
                "If the old printing is already live on ManaPool, unlist it there or with the Unlist action first.\n\n"
                "Continue?"
            )
            if not proceed:
                return

        values = self.ask_card_set_details(self.df.loc[idx])
        if not values:
            return

        now = datetime.now().isoformat()
        previous_listed_qty = safe_int(self.df.at[idx, "Quantity Listed"])
        previous_listed_price = safe_float(self.df.at[idx, "Listed Price"])

        for column, value in values.items():
            self.df.at[idx, column] = value

        self.df.at[idx, "Collector number"] = safe_collector_number(self.df.at[idx, "Collector number"])
        self.df.at[idx, "Condition"] = normalize_condition(self.df.at[idx, "Condition"])
        self.df.at[idx, "Key"] = row_key(self.df.loc[idx])
        self.df.at[idx, "ManaPool Product ID"] = ""
        self.df.at[idx, "TCGPlayer Product ID"] = ""
        self.df.at[idx, "TCGPlayer SKU"] = ""
        self.df.at[idx, "Best Price"] = ""
        self.df.at[idx, "Best Price Updated"] = ""
        self.df.at[idx, "Listed Price"] = ""
        self.df.at[idx, "Listed Price Updated"] = ""
        self.df.at[idx, "Last Listed"] = ""

        if was_listed:
            sell_qty = min(previous_listed_qty, safe_int(self.df.at[idx, "Quantity Owned"]))
            self.df.at[idx, "Is Listed"] = "FALSE"
            self.df.at[idx, "Quantity Listed"] = "0"
            self.df.at[idx, "Selling"] = bool_text(sell_qty > 0)
            self.df.at[idx, "Sell Quantity"] = str(sell_qty)
            if previous_listed_price > 0:
                self.df.at[idx, "List Price"] = price_text(previous_listed_price)

        self.df.at[idx, "Last Updated"] = now

        self.df = normalize_ledger_df(self.df)
        self.apply_filters(keep_status=True)
        self.set_status("Updated card/set details. Refresh price before pushing if needed.")
        try:
            self.sheets.write_inventory(self.df)
        except Exception as exc:
            self.log_output(f"Google Sheets Sync Error after card/set change: {exc}")
            messagebox.showwarning(
                "Sheets Sync Failed",
                "The card/set change was applied locally, but Google Sheets could not be updated.\n\n"
                f"{exc}"
            )

    def split_one_copy_to_condition(self):
        row_id = self.context_row_id or self.tree.focus()
        if not row_id:
            return

        idx = int(row_id)
        if idx not in self.df.index:
            return

        owned = safe_int(self.df.at[idx, "Quantity Owned"])
        if owned <= 1:
            messagebox.showwarning("Cannot Split", "This row needs at least 2 owned copies before one can be moved to another condition.")
            return

        current_condition = normalize_condition(self.df.at[idx, "Condition"])
        new_condition = self.ask_condition("Change Grading", current_condition)
        if not new_condition:
            return

        if new_condition == current_condition:
            messagebox.showwarning("Same Condition", "Choose a different condition for the split copy.")
            return

        now = datetime.now().isoformat()
        self.df = normalize_ledger_df(self.df)

        new_row = self.df.loc[idx].to_dict()
        new_row["Condition"] = new_condition
        new_row["Quantity Owned"] = "1"
        new_row["Quantity Listed"] = "0"
        new_row["Sell Quantity"] = "0"
        new_row["Selling"] = "FALSE"
        new_row["Is Listed"] = "FALSE"
        new_row["Best Price"] = ""
        new_row["List Price"] = ""
        new_row["Listed Price"] = ""
        new_row["ManaPool Product ID"] = ""
        new_row["TCGPlayer SKU"] = ""
        new_row["Best Price Updated"] = ""
        new_row["Listed Price Updated"] = ""
        new_row["Last Listed"] = ""
        new_row["Last Updated"] = now
        new_row["Key"] = row_key(new_row)

        new_owned = owned - 1
        self.df.at[idx, "Quantity Owned"] = str(new_owned)
        self.df.at[idx, "Quantity Listed"] = str(min(safe_int(self.df.at[idx, "Quantity Listed"]), new_owned))
        self.df.at[idx, "Sell Quantity"] = str(min(safe_int(self.df.at[idx, "Sell Quantity"]), new_owned))
        self.df.at[idx, "Is Listed"] = bool_text(safe_int(self.df.at[idx, "Quantity Listed"]) > 0)
        self.df.at[idx, "Selling"] = bool_text(safe_int(self.df.at[idx, "Sell Quantity"]) > 0)
        self.df.at[idx, "Last Updated"] = now

        target_key = safe(new_row.get("Key"))
        target_idx = None
        for candidate_idx, row in self.df.iterrows():
            if candidate_idx != idx and safe(row.get("Key")) == target_key:
                target_idx = candidate_idx
                break

        if target_idx is None:
            self.df = pd.concat([self.df, pd.DataFrame([new_row])], ignore_index=True)
            action_text = f"Created a new {new_condition} row."
        else:
            self.df.at[target_idx, "Quantity Owned"] = str(safe_int(self.df.at[target_idx, "Quantity Owned"]) + 1)
            self.df.at[target_idx, "Last Updated"] = now
            action_text = f"Added 1 copy to the existing {new_condition} row."

        self.df = normalize_ledger_df(self.df)
        self.apply_filters(keep_status=True)
        self.set_status(action_text)
        try:
            self.sheets.write_inventory(self.df)
        except Exception as exc:
            self.log_output(f"Google Sheets Sync Error after grading split: {exc}")
            messagebox.showwarning(
                "Sheets Sync Failed",
                "The grading split was applied locally, but Google Sheets could not be updated.\n\n"
                f"{exc}"
            )

    # ---------- Selection ----------
    def toggle_selected_row(self, event=None):
        item = self.tree.focus()
        if not item:
            return
        idx = int(item)
        current = bool_from_value(self.df.at[idx, "Selling"])
        self.df.at[idx, "Selling"] = "FALSE" if current else "TRUE"
        # Intentionally do not change Sell Quantity or List Price.
        self.apply_filters(keep_status=True)
        self.set_status("Toggled Selling. Quantity and price were not changed.")

    def select_filtered(self):
        for idx in self.filtered_df.index:
            self.df.at[idx, "Selling"] = "TRUE"
        self.apply_filters(keep_status=True)
        self.set_status(f"Selected {len(self.filtered_df)} visible rows. Set quantities/prices before pushing.")

    def clear_filtered(self):
        for idx in self.filtered_df.index:
            self.df.at[idx, "Selling"] = "FALSE"
        self.apply_filters(keep_status=True)
        self.set_status(f"Cleared {len(self.filtered_df)} visible rows.")


    def selected_for_sale_df(self):
        if self.df.empty:
            return make_empty_ledger()
        selected = self.df[self.df["Selling"].apply(bool_from_value)].copy()
        selected = selected[selected["Sell Quantity"].apply(safe_int) > 0]
        selected = selected[selected["List Price"].apply(safe_float) > 0]

        invalid = selected[selected["Sell Quantity"].apply(safe_int) > selected["Quantity Owned"].apply(safe_int)]
        if not invalid.empty:
            names = "\n".join(invalid["Name"].astype(str).head(10).tolist())
            messagebox.showwarning("Invalid Quantity", f"Sell Quantity cannot exceed Quantity Owned.\n\n{names}")
            return make_empty_ledger()
        return selected
    
    def mark_selected_max_for_sale(self):
        item = self.tree.focus()
        if not item:
            messagebox.showwarning("No Row Selected", "Click a row first.")
            return

        idx = int(item)

        owned = safe_int(self.df.at[idx, "Quantity Owned"])
        listed = safe_int(self.df.at[idx, "Quantity Listed"])
        available = owned - listed

        if available <= 0:
            messagebox.showinfo(
                "Nothing Available",
                "All owned copies are already listed."
            )
            return

        best_price = safe_float(self.df.at[idx, "Best Price"])
        listed_price = safe_float(self.df.at[idx, "Listed Price"])
        purchase_price = safe_float(self.df.at[idx, "Purchase price"])

        self.df.at[idx, "Selling"] = "TRUE"
        self.df.at[idx, "Sell Quantity"] = str(available)

        if safe_float(self.df.at[idx, "List Price"]) <= 0:
            self.df.at[idx, "List Price"] = price_text(best_price or listed_price or purchase_price)

        self.apply_filters(keep_status=True)
        self.set_status(f"Marked {available} available copies for sale.")

    def find_matching_inventory_index(self, mp_row):
        target_scryfall = safe(mp_row.get("Scryfall ID")).lower()
        target_finish = safe(mp_row.get("Foil")).lower()
        target_condition = safe(mp_row.get("Condition")).lower()
        target_language = safe(mp_row.get("Language")).lower()
        target_set = safe(mp_row.get("Set code")).lower()
        target_number = safe_collector_number(mp_row.get("Collector number")).lower()

        for idx, row in self.df.iterrows():
            if (
                safe(row.get("Scryfall ID")).lower() == target_scryfall
                and safe(row.get("Foil")).lower() == target_finish
                and safe(row.get("Condition")).lower() == target_condition
                and safe(row.get("Language")).lower() == target_language
                and safe(row.get("Set code")).lower() == target_set
                and safe_collector_number(row.get("Collector number")).lower() == target_number
            ):
                return idx

        return None

    # ---------- Pricing ----------
    def refresh_best_prices(self):
        if self.df.empty:
            return
        now = datetime.now().isoformat()
        updated = 0
        failed = 0
        self.df = normalize_ledger_df(self.df)
        for idx, row in self.df.iterrows():
            # Refresh selected or already-listed rows only.
            if not bool_from_value(row.get("Selling")):
                continue
            try:
                result = self.manapool_api.get_best_price_for_row(row)
                if not result:
                    failed += 1
                    continue
                self.df.at[idx, "Best Price"] = price_text(result["best_price"])
                self.df.at[idx, "Best Price Updated"] = now
                self.df.at[idx, "ManaPool Product ID"] = safe(result["product_id"])
                self.df.at[idx, "TCGPlayer SKU"] = safe(result["tcgplayer_sku"])
                self.df.at[idx, "TCGPlayer Product ID"] = safe(result["tcgplayer_product_id"])
                updated += 1
            except Exception as exc:
                failed += 1
                self.log_output(f"Price refresh failed for {safe(row.get('Name'))}: {exc}")
        self.df = normalize_ledger_df(self.df)
        self.sheets.write_inventory(self.df)
        self.apply_filters(keep_status=True)
        messagebox.showinfo("Best Prices", f"Updated {updated} rows. Failed/skipped {failed} rows.")

    def calculate_smart_price(self, best_price):
        best = safe_float(best_price)
        floor = safe_float(self.floor_price_var.get(), 0.10)

        if best <= 0:
            return 0

        mode = self.pricing_mode_var.get()

        if mode == "Match Best Price":
            price = best

        elif mode == "Undercut $0.01":
            price = best - 0.01

        elif mode == "Undercut %":
            pct = safe_float(self.undercut_percent_var.get(), 3.0)
            price = best * (1 - pct / 100)

        else:
            price = best

        price = max(price, floor)
        return round(price, 2)

    def update_listed_prices_to_best(self):
        if self.df.empty:
            return

        mode = self.pricing_mode_var.get()

        if not messagebox.askyesno(
            "Confirm Smart Reprice",
            f"This will update List Price for selected Selling rows using:\n\n{mode}\n\nContinue?"
        ):
            return

        now = datetime.now().isoformat()
        updated = 0
        skipped = 0

        self.df = normalize_ledger_df(self.df)

        for idx, row in self.df.iterrows():
            if not bool_from_value(row.get("Selling")):
                continue

            best = safe_float(row.get("Best Price"))
            if best <= 0:
                skipped += 1
                continue

            new_price = self.calculate_smart_price(best)

            if new_price <= 0:
                skipped += 1
                continue

            self.df.at[idx, "List Price"] = price_text(new_price)
            self.df.at[idx, "Last Updated"] = now
            updated += 1

        self.sheets.write_inventory(self.df)
        self.apply_filters(keep_status=True)

        messagebox.showinfo(
            "Smart Reprice Complete",
            f"Updated {updated} selected rows.\nSkipped {skipped} rows."
        )

    def mark_selected_sold(self):
        item = self.tree.focus()
        if not item:
            messagebox.showwarning("No Row Selected", "Click a row first.")
            return

        idx = int(item)
        row = self.df.loc[idx]

        owned = safe_int(row.get("Quantity Owned"))
        listed = safe_int(row.get("Quantity Listed"))
        sell_qty = safe_int(row.get("Sell Quantity"))

        max_available = listed if listed > 0 else owned

        if max_available <= 0:
            messagebox.showwarning("Nothing to Sell", "This row has no listed/owned quantity to mark sold.")
            return

        qty_text = simpledialog.askstring(
            "Quantity Sold",
            f"How many copies sold?\n\nAvailable/listed: {max_available}",
            initialvalue=str(min(1, max_available))
        )

        if qty_text is None:
            return

        sold_qty = safe_int(qty_text)
        if sold_qty <= 0 or sold_qty > max_available:
            messagebox.showerror("Invalid Quantity", f"Sold quantity must be between 1 and {max_available}.")
            return

        default_price = (
            safe_float(row.get("Listed Price"))
            or safe_float(row.get("List Price"))
            or safe_float(row.get("Best Price"))
            or safe_float(row.get("Purchase price"))
        )

        price_text_value = simpledialog.askstring(
            "Sold Price",
            "What price did it sell for per copy?",
            initialvalue=f"{default_price:.2f}" if default_price > 0 else ""
        )

        if price_text_value is None:
            return

        sold_price = safe_float(price_text_value)
        if sold_price <= 0:
            messagebox.showerror("Invalid Price", "Sold price must be greater than 0.")
            return

        now = datetime.now().isoformat()

        sold_row = {
            "Sold At": now,
            "Name": safe(row.get("Name")),
            "Set code": safe(row.get("Set code")),
            "Set name": safe(row.get("Set name")),
            "Collector number": safe(row.get("Collector number")),
            "Foil": safe(row.get("Foil")),
            "Rarity": safe(row.get("Rarity")),
            "Condition": safe(row.get("Condition")),
            "Language": safe(row.get("Language")),
            "Scryfall ID": safe(row.get("Scryfall ID")),
            "ManaBox ID": safe(row.get("ManaBox ID")),
            "Quantity Sold": str(sold_qty),
            "Sold Price": price_text(sold_price),
            "Total Sold": price_text(sold_qty * sold_price),
            "Purchase price": price_text(row.get("Purchase price")),
            "Listed Price": price_text(row.get("Listed Price")),
            "ManaPool Product ID": safe(row.get("ManaPool Product ID")),
            "TCGPlayer SKU": safe(row.get("TCGPlayer SKU")),
            "Key": safe(row.get("Key")),
        }

        try:
            self.sheets.append_sold_inventory(sold_row)

            new_owned = max(0, owned - sold_qty)
            new_listed = max(0, listed - sold_qty)
            new_sell_qty = max(0, sell_qty - sold_qty)

            self.df.at[idx, "Quantity Owned"] = str(new_owned)
            self.df.at[idx, "Quantity Listed"] = str(new_listed)
            self.df.at[idx, "Sell Quantity"] = str(new_sell_qty)
            self.df.at[idx, "Last Updated"] = now

            if new_listed <= 0:
                self.df.at[idx, "Is Listed"] = "FALSE"
                self.df.at[idx, "Listed Price"] = ""
                self.df.at[idx, "Listed Price Updated"] = ""

            if new_sell_qty <= 0:
                self.df.at[idx, "Selling"] = "FALSE"

            if new_owned <= 0:
                self.df = self.df.drop(index=idx)

            self.df = normalize_ledger_df(self.df)
            self.sheets.write_inventory(self.df)
            self.apply_filters(keep_status=True)

            messagebox.showinfo(
                "Marked Sold",
                f"Recorded sale of {sold_qty}x {safe(row.get('Name'))} at ${sold_price:.2f} each."
            )

        except Exception as exc:
            self.log_output(f"Mark Sold Error: {exc}")
            messagebox.showerror("Mark Sold Error", str(exc))
    # ---------- API ----------
    def api_test_connection(self):
        try:
            result = self.manapool_api.test_connection()
            messagebox.showinfo("API Test OK", json.dumps(result, indent=2)[:3000])
        except Exception as exc:
            self.log_output(f"API Test Failed: {exc}")
            messagebox.showerror("API Test Failed", str(exc))

    def api_dry_run(self):
        selected = self.selected_for_sale_df()
        if selected.empty:
            messagebox.showwarning("No Cards Ready", "Mark cards as Selling and set Sell Quantity/List Price first.")
            return
        try:
            payload = self.manapool_api.build_inventory_payload(selected)
            path = filedialog.asksaveasfilename(defaultextension=".json", initialfile=f"manapool_payload_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            if path:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
            messagebox.showinfo("Dry Run", f"Prepared {len(payload['items'])} rows. Warnings: {len(payload['warnings'])}")
        except Exception as exc:
            self.log_output(f"Dry Run Error: {exc}")
            messagebox.showerror("Dry Run Error", str(exc))

    def api_push_selected(self):
        selected = self.selected_for_sale_df()
        if selected.empty:
            messagebox.showwarning("No Cards Ready", "Mark cards as Selling and set Sell Quantity/List Price first.")
            return
        try:
            payload = self.manapool_api.build_inventory_payload(selected)
            if payload.get("warnings"):
                if not messagebox.askyesno("Warnings", "Some rows could not be matched. Continue anyway?"):
                    return
            if not messagebox.askyesno("Confirm Push", f"Push {len(payload['items'])} listings to ManaPool?"):
                return
            result = self.manapool_api.push_inventory(payload)
            now = datetime.now().isoformat()
            self.df = normalize_ledger_df(self.df)
            for idx in selected.index:
                self.df.at[idx, "Is Listed"] = "TRUE"
                self.df.at[idx, "Quantity Listed"] = str(safe_int(self.df.at[idx, "Sell Quantity"]))
                self.df.at[idx, "Listed Price"] = price_text(self.df.at[idx, "List Price"])
                self.df.at[idx, "Listed Price Updated"] = now
                self.df.at[idx, "Last Listed"] = now
                self.df.at[idx, "Last Updated"] = now
            self.sheets.write_inventory(self.df)
            self.apply_filters(keep_status=True)
            messagebox.showinfo("Push Complete", json.dumps(result, indent=2)[:3000])
        except Exception as exc:
            self.log_output(f"API Push Failed: {exc}")
            messagebox.showerror("API Push Failed", str(exc))


if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "ManaPool.SellerDashboard.GoblinIcon.1"
        )
    except Exception:
        pass

    root = tk.Tk()

    try:
        icon_path = os.path.join(os.path.dirname(__file__), "app.ico")
        root.iconbitmap(default=icon_path)
    except Exception as exc:
        print("Icon load failed:", exc)

    app = ManaPoolSellerDashboard(root)
    root.mainloop()
