# ManaPoolSellerApp
# ManaPool Seller Dashboard

A desktop inventory and pricing manager for Magic: The Gathering sellers.

This application connects:

* ManaBox CSV exports
* Google Sheets
* ManaPool Seller API

The goal is to make it easy to:

* Track inventory
* Manage listed cards
* Price and reprice cards
* Push listings to ManaPool
* Track sold inventory
* Keep Google Sheets as the source of truth

---

# Features

## Inventory Management

* Import ManaBox CSV exports
* Merge new scans into existing inventory
* Avoid duplicate rows
* Track quantity owned vs quantity listed
* Track listed prices
* Track sold inventory

## Google Sheets Integration

Google Sheets is the primary database.

The app:

* Loads inventory from Google Sheets on startup
* Writes updates back to Google Sheets
* Maintains a Sold Inventory tab
* Persists pricing and listing data

## ManaPool API Integration

The app can:

* Lookup products from ManaPool
* Refresh best prices
* Apply smart pricing rules
* Push inventory updates
* Sync currently listed inventory from ManaPool

## Smart Pricing

Supports:

* Match Best Price
* Undercut by $0.01
* Undercut by %
* Floor price protection

## Sales Tracking

Mark inventory as sold.

The app:

* Moves sold data into a Sold Inventory tab
* Tracks sold quantity
* Tracks sold price
* Updates remaining inventory automatically

---

# Application Workflow

## Recommended Workflow

### 1. Scan Cards in ManaBox

Use ManaBox to scan and organize your MTG inventory.

### 2. Export CSV from ManaBox

In ManaBox:

* Export Collection
* Save CSV

### 3. Import CSV into App

Use:

```text
Data → Merge CSV
```

The app will:

* Merge new cards into Google Sheets
* Increase quantities for duplicates (optional)
* Preserve listing/pricing data

### 4. Select Cards to Sell

Double-click a row.

This marks:

```text
Selling = TRUE
```

### 5. Set Quantity and Price

Inline edit:

* Sell Quantity
* List Price

OR:

Use:

```text
Pricing → Refresh Prices
Pricing → Apply Smart Pricing
```

### 6. Push to ManaPool

Use:

```text
Listing → Push API
```

The app will:

* Match products to ManaPool
* Push quantity + price
* Update listed status

### 7. Mark Cards Sold

Use:

```text
Listing → Mark Sold
```

The app will:

* Reduce owned quantity
* Reduce listed quantity
* Add row to Sold Inventory tab
* Remove row if quantity becomes zero

---

# Google Sheets Setup

## Step 1 — Create Google Sheet

Create a Google Sheet.

Recommended name:

```text
ManaPool
```

The app uses:

* Sheet1 = active inventory
* Sold Inventory = sold cards

The Sold Inventory tab is created automatically.

---

# Google Cloud / Service Account Setup

The app uses a Google Service Account to access Sheets.

## Step 1 — Create Google Cloud Project

Go to:

[https://console.cloud.google.com/](https://console.cloud.google.com/)

Create a new project.

---

## Step 2 — Enable APIs

Enable:

* Google Sheets API
* Google Drive API

---

## Step 3 — Create Service Account

Go to:

```text
APIs & Services → Credentials
```

Create:

```text
Service Account
```

---

## Step 4 — Create JSON Key

Inside the Service Account:

```text
Keys → Add Key → JSON
```

Download the JSON file.

Rename it:

```text
credentials.json
```

Place it beside:

```text
ManaPoolInventory.py
```

---

## Step 5 — Share Google Sheet

Open your Google Sheet.

Click:

```text
Share
```

Add the service account email from:

```text
credentials.json
```

Give:

```text
Editor access
```

---

# ManaPool API Setup

## Step 1 — Create ManaPool API Token

Go to:

```text
ManaPool → Integrations / API
```

Create API credentials.

You will receive:

* Email
* Access Token

---

## Step 2 — Create .env File

Create a file named:

```text
.env
```

Place it beside:

```text
ManaPoolInventory.py
```

Contents:

```env
MANAPOOL_API_TOKEN=YOUR_TOKEN_HERE
MANAPOOL_API_EMAIL=YOUR_EMAIL_HERE
```

Example:

```env
MANAPOOL_API_TOKEN=mpat_xxxxxxxxxxxxx
MANAPOOL_API_EMAIL=youremail@gmail.com
```

Do NOT use quotes.

---

# Python Installation

## Step 1 — Install Python

Download Python:

[https://www.python.org/downloads/](https://www.python.org/downloads/)

Recommended:

```text
Python 3.12+
```

IMPORTANT:

During install:

```text
✔ Add Python to PATH
```

---

# Project Folder Structure

Recommended:

```text
ManaPool/
│
├── ManaPoolInventory.py
├── credentials.json
├── .env
├── requirements.txt
└── seller_state.json
```

---

# Install Dependencies

Open terminal in the project folder.

Run:

```bash
pip install pandas requests gspread google-auth tkinter
```

If tkinter is missing:

## Windows

Usually included automatically.

## Linux

```bash
sudo apt install python3-tk
```

---

# Running the Application

Open terminal inside the project folder.

Run:

```bash
python ManaPoolInventory.py
```

---

# First Startup Checklist

On first launch:

## Verify:

### Google Sheets

* Inventory loads successfully
* No authentication errors

### ManaPool API

Use:

```text
⚙️ More → API Test
```

Verify successful response.

### CSV Import

Use:

```text
Data → Merge CSV
```

Verify cards appear.

---

# UI Overview

## Data

### Reload

Reload inventory from Google Sheets.

### Merge CSV

Import ManaBox export.

### Sync Sheets

Push local changes to Google Sheets.

### Sync MP

Pull current listed inventory from ManaPool.

---

## Pricing

### Refresh Prices

Refresh best prices for selected rows.

### Apply Smart Pricing

Apply pricing strategy.

Supports:

* Match Best Price
* Undercut by $0.01
* Undercut by %

---

## Listing

### Mark Max

Set:

```text
Sell Quantity = Quantity Owned - Quantity Listed
```

### Mark Sold

Record sold cards.

### Push API

Push selected listings to ManaPool.

---

## ⚙️ More

### API Test

Test ManaPool API connection.

### Dry Run

Generate JSON payload without pushing.

---

# Inventory Fields Explained

| Field           | Meaning                             |
| --------------- | ----------------------------------- |
| Quantity Owned  | Total copies owned                  |
| Quantity Listed | Copies currently listed on ManaPool |
| Sell Quantity   | Copies to push in next API action   |
| Best Price      | Current best market price           |
| List Price      | Price you intend to list at         |
| Listed Price    | Actual live ManaPool listing price  |
| Selling         | Selected for current actions        |
| Is Listed       | Currently listed on ManaPool        |

---

# Smart Pricing Explained

## Match Best Price

```text
List Price = Best Price
```

## Undercut by $0.01

```text
List Price = Best Price - 0.01
```

## Undercut by %

```text
List Price = Best Price * (1 - percent)
```

## Floor Price

Prevents pricing below minimum threshold.

---

# Common Problems

## 401 Unauthorized

Verify:

* .env exists
* token is correct
* email is correct
* no quotes around values

Example:

```env
MANAPOOL_API_TOKEN=mpat_xxxxx
MANAPOOL_API_EMAIL=me@gmail.com
```

---

## Google Sheets Permission Error

Verify:

* credentials.json exists
* Google Sheet shared with service account
* APIs enabled

---

## Duplicate Inventory Rows

Usually caused by:

* mismatched condition/language/foil data
* importing same inventory multiple times

Use:

```text
Sync MP
```

to normalize listing state.

---

## No Prices Returned

Usually caused by:

* missing Scryfall ID
* unsupported language variant
* sealed product

---

# Recommended Backup Strategy

Back up:

* Google Sheet
* credentials.json
* .env
* seller_state.json

Do NOT commit:

* .env
* credentials.json

into public Git repositories.

---

# Future Improvements

Planned ideas:

* Inline quantity editing
* Profit tracking
* Auto repricing
* ManaPool inventory reconciliation
* Sealed product support
* Analytics dashboard
* Profit/loss tracking
* Sales charts
* Bulk repricing
* Right-click context menus
* Auto update checks

---

# Recommended Daily Workflow

```text
1. Scan cards in ManaBox
2. Export CSV
3. Merge CSV into app
4. Select cards to sell
5. Refresh Prices
6. Apply Smart Pricing
7. Push API
8. Mark Sold when sales happen
```

---

# License / Notes

This project is intended for personal inventory and seller workflow management.

Always verify pricing and quantities before pushing live inventory updates.
