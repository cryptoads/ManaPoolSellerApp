# 🧙‍♂️ ManaPool Seller Dashboard

A desktop tool for managing and selling **Magic: The Gathering** inventory using:

- 📦 **ManaBox** as the card scanning and collection source
- 📊 **Google Sheets** as the inventory database
- 💰 **ManaPool API** for pricing, listing, syncing, and selling workflows

The app is designed around a simple idea:

> **Google Sheets is the source of truth.**  
> The desktop app is the control layer.  
> ManaPool is the execution layer.

---

## ✨ Features

### 📦 Inventory Management

- Import ManaBox CSV exports
- Merge new CSV imports into existing inventory
- Detect duplicate cards
- Preserve existing listed prices and listing status
- Track:
  - Quantity owned
  - Quantity listed
  - Quantity selected to list
  - Current list price
  - Current ManaPool listed price

### 📊 Google Sheets Integration

Google Sheets acts as the app database.

The app can:

- Load inventory from Google Sheets on startup
- Write inventory updates back to Google Sheets
- Keep active inventory in the main sheet
- Track sold cards in a separate `Sold Inventory` tab
- Preserve inventory data between computers

### 💰 ManaPool Integration

The app can:

- Look up ManaPool products using Scryfall IDs
- Match variants by language, condition, and finish
- Refresh best prices
- Apply smart pricing
- Push selected listings to ManaPool
- Sync currently listed inventory from ManaPool
- Mark sold cards and move them into sold history

### 🧠 Smart Pricing

Supported pricing modes:

- Match best price
- Undercut best price by `$0.01`
- Undercut best price by percentage
- Apply a minimum floor price

### 📈 Sales Tracking

When marking a card sold, the app can:

- Ask for quantity sold
- Ask for sold price
- Append the sale to the `Sold Inventory` tab
- Reduce quantity owned
- Reduce quantity listed
- Remove the card from active inventory if quantity reaches zero

---

## 🧭 Recommended Workflow

1. Scan cards in ManaBox.
2. Export a CSV from ManaBox.
3. Open the ManaPool Seller Dashboard.
4. Merge the ManaBox CSV into the app.
5. Select cards to sell.
6. Refresh prices from ManaPool.
7. Apply smart pricing.
8. Push selected listings to ManaPool.
9. Mark cards sold when sales happen.
10. Keep Google Sheets synced as the source of truth.

---

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd ManaPool
```

### 2. Install Python

Install **Python 3.12 or newer**.

Download Python from:

https://www.python.org/downloads/

During installation, make sure this option is checked:

```text
Add Python to PATH
```

### 3. Install Dependencies

From the project folder, run:

```bash
pip install pandas requests gspread google-auth
```

Tkinter is usually included with Python on Windows.

If you are on Linux and Tkinter is missing, install it with:

```bash
sudo apt install python3-tk
```

---

## 📁 Project Structure

Recommended folder layout:

```text
ManaPool/
├── ManaPoolInventory.py
├── README.md
├── .gitignore
├── .env
├── credentials.json
└── seller_state.json
```

### Important Files

| File | Purpose |
|---|---|
| `ManaPoolInventory.py` | Main application |
| `.env` | ManaPool API credentials |
| `credentials.json` | Google service account credentials |
| `README.md` | Project documentation |
| `seller_state.json` | Local app state, if used |

---

## 📊 Google Sheets Setup

Google Sheets is the app’s database. The app loads from Google Sheets when it starts and writes changes back to Google Sheets when inventory changes.

### Step 1 — Create the Google Sheet

1. Open Google Sheets.
2. Create a new blank spreadsheet.
3. Name it exactly:

```text
ManaPool
```

4. The first tab is used for active inventory.

You may rename the first tab to:

```text
Inventory
```

The app also creates or uses a second tab:

```text
Sold Inventory
```

That tab is used for sold cards.

---

### Step 2 — Create a Google Cloud Project

1. Go to Google Cloud Console:

https://console.cloud.google.com/

2. Create a new project.
3. Give it a name such as:

```text
ManaPool Inventory App
```

---

### Step 3 — Enable Google APIs

Inside your Google Cloud project, enable these APIs:

- Google Sheets API
- Google Drive API

You can find them under:

```text
APIs & Services → Library
```

Search each API name and click **Enable**.

---

### Step 4 — Create a Service Account

1. Go to:

```text
APIs & Services → Credentials
```

2. Click:

```text
Create Credentials → Service Account
```

3. Give the service account a name, such as:

```text
manapool-sheets-service
```

4. Finish creating the service account.

---

### Step 5 — Create a JSON Key

1. Open the service account you created.
2. Go to the **Keys** tab.
3. Click:

```text
Add Key → Create new key
```

4. Choose:

```text
JSON
```

5. Download the file.
6. Rename it to:

```text
credentials.json
```

7. Place it in the same folder as:

```text
ManaPoolInventory.py
```

---

### Step 6 — Share the Google Sheet

1. Open `credentials.json`.
2. Find the service account email.

It will look something like:

```text
your-service-account@your-project.iam.gserviceaccount.com
```

3. Open your Google Sheet.
4. Click **Share**.
5. Add the service account email.
6. Give it **Editor** access.

If you skip this step, the app will not be able to read or write your sheet.

---

## 📦 Using ManaBox

ManaBox is used as your card scanning and collection entry tool.

### Step 1 — Scan Cards in ManaBox

1. Open ManaBox.
2. Scan cards into your collection.
3. Review each card and make sure the following fields are correct:
   - Name
   - Set
   - Collector number
   - Foil or nonfoil
   - Condition
   - Language
   - Quantity

These fields are important because the app uses them to match the correct ManaPool product and variant.

For example, these are different listings:

```text
English Near Mint Nonfoil
English Near Mint Foil
Japanese Near Mint Nonfoil
English Lightly Played Foil
```

If the condition, language, or finish is wrong in ManaBox, the app may match the wrong ManaPool variant.

---

### Step 2 — Export a CSV from ManaBox

In ManaBox:

1. Open your collection.
2. Choose the export option.
3. Export as CSV.
4. Save the file locally.

The app expects ManaBox columns such as:

```text
Name
Set code
Set name
Collector number
Foil
Rarity
Quantity
ManaBox ID
Scryfall ID
Purchase price
Misprint
Altered
Condition
Language
Purchase price currency
```

The most important field is:

```text
Scryfall ID
```

The app uses this to look up the card in ManaPool.

---

### Step 3 — Merge the CSV into the App

In the app, use:

```text
Data → Merge CSV
```

The app will:

- Add new cards to Google Sheets
- Detect duplicate cards
- Ask whether to increase quantities
- Preserve existing list prices
- Preserve existing listed status
- Preserve sales tracking data

Recommended habit:

```text
Scan in ManaBox → Export CSV → Merge CSV into app → Sync Sheets
```

---

## 🔑 ManaPool API Setup

### Step 1 — Get ManaPool API Credentials

From ManaPool, generate or copy your API credentials from the integrations/API area.

You need:

- ManaPool API token
- ManaPool account email

---

### Step 2 — Create the `.env` File

Create a file named:

```text
.env
```

Place it in the same folder as:

```text
ManaPoolInventory.py
```

The file should contain:

```env
MANAPOOL_API_TOKEN=your_token_here
MANAPOOL_API_EMAIL=your_email_here
```

Example:

```env
MANAPOOL_API_TOKEN=mpat_xxxxxxxxxxxxxxxxx
MANAPOOL_API_EMAIL=you@example.com
```

Do not use quotes.

Correct:

```env
MANAPOOL_API_TOKEN=mpat_xxxxxxxxxxxxxxxxx
```

Incorrect:

```env
MANAPOOL_API_TOKEN="mpat_xxxxxxxxxxxxxxxxx"
```

---

## ▶️ Running the Application

From the project folder, run:

```bash
python ManaPoolInventory.py
```

On startup, the app will try to load inventory from Google Sheets.

---

## 🖥️ UI Overview

The app is organized into tabs so each workflow shows the buttons that belong to it.

| Tab | Purpose |
|---|---|
| Collection | Load, merge, sync, prepare owned cards, and push newly selected listings |
| Listed | Sync ManaPool, refresh pricing, push listings, and unlist cards |
| Sold | Mark cards sold and prepare ManaPool sold-import review |
| Tools | API tests and dry-run payload generation |

Switching tabs also changes the table view. `Collection` shows the owned collection, `Listed` focuses on rows with `Quantity Listed` greater than zero, and `Sold` focuses on rows that are listed or selected for sale while the sold-import workflow is built out.

---

### Data

Data actions control Google Sheets and ManaBox imports.

| Button | Purpose |
|---|---|
| Reload Sheets | Reload inventory from Google Sheets |
| Merge CSV | Merge a ManaBox CSV export |
| Sync Sheets | Write local app data back to Google Sheets |
| Sync MP | Pull current listings from ManaPool |

---

### Pricing

Pricing actions help determine and apply list prices.

| Button | Purpose |
|---|---|
| Refresh Prices | Pull best price data for selected rows |
| Apply Smart Pricing | Apply selected pricing strategy to selected rows |

---

### Listing

Listing actions affect ManaPool inventory and sales state.

| Button | Purpose |
|---|---|
| Mark Max | Mark all available unlisted copies for sale |
| Mark Sold | Record a completed sale |
| Push API | Push selected listings to ManaPool |

`Mark Max` works on the focused row. It sets `Sell Quantity` to:

```text
Quantity Owned - Quantity Listed
```

and marks that row as `Selling`. Use it when you want to list every unlisted copy you own for that row.

---

### Table Editing and Right-Click Actions

The inventory table supports quick row edits:

| Action | Purpose |
|---|---|
| Double-click `Sell Quantity` | Edit how many copies are selected for the next listing push |
| Double-click `List Price` | Edit the price to push |
| Double-click `Condition` | Choose the ManaPool condition for that row |
| Right-click -> Change grading for one copy | Move one owned copy into a new condition row |
| Right-click -> Change card/set details | Change the card printing or set identity for a row |

Supported ManaPool conditions are:

```text
near_mint
lightly_played
moderately_played
heavily_played
damaged
```

Changing grading for one copy is available only when `Quantity Owned` is greater than 1. The app reduces the original row by one owned copy and creates a new row at the selected condition. If that exact card, finish, language, and condition already exists, the app adds the copy to that existing row instead.

Changing card/set details lets you correct the card identity fields that determine which ManaPool variant is pushed. If the row is already listed, the app clears the local listed state and stale ManaPool mapping so you can push the corrected printing cleanly.

---

### More

Debug and developer tools.

| Item | Purpose |
|---|---|
| API Test | Test ManaPool authentication |
| Dry Run | Generate JSON payload without pushing |

---

## 🧾 Inventory Fields

| Field | Description |
|---|---|
| Quantity Owned | Total copies you own |
| Quantity Listed | Copies currently listed on ManaPool |
| Sell Quantity | Copies selected to push in the next listing action |
| Best Price | Current best price from ManaPool |
| List Price | Price you intend to push |
| Listed Price | Price currently live on ManaPool |
| Condition | ManaPool condition used for matching and pushing the listing |
| Selling | Selected for the current action |
| Is Listed | Currently listed on ManaPool |
| ManaPool Product ID | ManaPool product identifier |
| TCGPlayer Product ID | TCGPlayer product ID |
| TCGPlayer SKU | TCGPlayer SKU used by ManaPool |
| Last Listed | Timestamp of last successful listing push |
| Best Price Updated | Timestamp of last price refresh |
| Listed Price Updated | Timestamp of last listed price update |

---

## 💰 Smart Pricing Logic

### Match Best Price

```text
List Price = Best Price
```

### Undercut by $0.01

```text
List Price = Best Price - 0.01
```

### Undercut by Percentage

```text
List Price = Best Price * (1 - percent / 100)
```

### Floor Price

The app prevents smart pricing from going below your configured floor price.

```text
Final Price = max(calculated price, floor price)
```

---

## 📤 Listing Flow

To list cards:

1. Select one or more rows.
2. Set `Sell Quantity`.
3. Set `List Price`.
4. Click `Push API`.

The app will:

- Look up the ManaPool product
- Match the correct variant by language, condition, and finish
- Build the inventory payload
- Push the listing to ManaPool
- Update Google Sheets with:
  - Is Listed
  - Quantity Listed
  - Listed Price
  - Last Listed

---

## Listed Inventory Value

The `List Value` metric shows the value of everything currently listed on ManaPool.

```text
List Value = Quantity Listed * Listed Price
```

Rows count toward this value whenever `Quantity Listed` is greater than zero.

---

## Correcting Listed Inventory

### Change the Grade of One Copy

Use this when a row has multiple owned copies and one copy is a different condition.

1. Right-click the row.
2. Choose `Change grading for one copy`.
3. Select the new condition.

The app will:

- Reduce the original row's `Quantity Owned` by 1
- Create or update a row for the selected condition
- Clear stale pricing and ManaPool mapping fields on the new condition row
- Save the inventory update back to Google Sheets

The new condition row starts unlisted. Set its `Sell Quantity` and `List Price`, then push it when ready.

### Change the Card or Set

Use this when the listed row is the wrong printing, set, collector number, or Scryfall ID.

1. Right-click the row.
2. Choose `Change card/set details`.
3. Update the card identity fields.

The editable fields include:

```text
Name
Set code
Set name
Collector number
Scryfall ID
Rarity
ManaBox ID
Foil
Language
Condition
```

If the row is currently listed, the app warns you before continuing. Continuing clears the local listed state and stale ManaPool product/SKU fields, keeps the previous listed quantity selected as `Sell Quantity`, and preserves the old listed price as `List Price` when available.

If the old printing is already live on ManaPool, unlist the old listing before pushing the corrected row.

---

## ManaPool Sold Import Review

The `Sold` tab includes an `Import as-of` date and a `Review Sold` workflow.

`Review Sold` pulls recent ManaPool seller orders and builds an approval queue. The app skips any ManaPool sale that already has an imported `Import ID` in the `Sold Inventory` tab.

Use the as-of date as the clean starting line for automated inventory adjustments. For example, using `2026-07-06` means:

- Sales before that date default to `tracking` mode.
- Sales on or after that date default to `adjust` mode.
- You approve the rows to import from the review window before inventory changes.
- You can toggle selected rows between `tracking` and `adjust` before importing.

Import modes:

| Mode | Behavior |
|---|---|
| tracking | Adds the sale to `Sold Inventory` without changing owned or listed quantities |
| adjust | Adds the sale to `Sold Inventory` and reduces `Quantity Owned`, `Quantity Listed`, and `Sell Quantity` on the matched row |

The importer matches sold cards to local rows using the same identity fields as the rest of the app:

```text
Scryfall ID
Set code
Collector number
Foil
Condition
Language
```

Imported ManaPool sales add these audit fields to `Sold Inventory`:

```text
Import Source
Import ID
Import Mode
Imported At
```

This lets you rerun the import safely without double-counting sales that were already imported.

---

## ✅ Marking Cards Sold

To record a sale:

1. Select the row.
2. Click `Mark Sold`.
3. Enter quantity sold.
4. Enter sold price.

The app will:

- Append the sale to the `Sold Inventory` tab
- Reduce `Quantity Owned`
- Reduce `Quantity Listed`
- Remove the row from active inventory if no copies remain

---

## 🔄 ManaPool Sync

`Sync MP` pulls inventory currently listed on ManaPool.

It updates matching rows with:

- Is Listed
- Quantity Listed
- Listed Price
- ManaPool Product ID
- TCGPlayer Product ID
- TCGPlayer SKU

If a ManaPool item is not in your sheet, the app can add it as a new row.

Sealed products may be skipped unless sealed product support is added.

---

## ⚠️ Troubleshooting

### 401 Unauthorized

Check:

- `.env` exists
- Token is correct
- Email is correct
- Values are not wrapped in quotes

Correct:

```env
MANAPOOL_API_TOKEN=mpat_xxxxx
MANAPOOL_API_EMAIL=you@example.com
```

---

### Google Sheets Permission Error

Check:

- `credentials.json` exists
- Google Sheets API is enabled
- Google Drive API is enabled
- Sheet is shared with the service account email
- Service account has Editor access

---

### Google Sheet Does Not Load

Check that the sheet is named:

```text
ManaPool
```

If you changed the name, update the `SHEET_NAME` constant in the code.

---

### Duplicate Rows

Duplicates are usually caused by mismatched card identity fields:

- Scryfall ID
- Set code
- Collector number
- Foil status
- Condition
- Language

Make sure ManaBox data is accurate before exporting.

---

### Missing Prices

Common causes:

- Missing Scryfall ID
- Unsupported language
- Token or sealed product
- ManaPool does not have pricing for that exact variant

---

### Wrong Variant Matched

Check:

- Language
- Condition
- Foil status
- Collector number

The app matches ManaPool variants using those fields.

---

## 🔐 Security

Never commit these files:

```text
.env
credentials.json
```

They contain private credentials.

Recommended `.gitignore` entries:

```gitignore
.env
credentials.json
__pycache__/
*.pyc
seller_state.json
*.csv
*.xlsx
manapool_payload_*.json
```

---

## 🧪 Developer Notes

### Main Concepts

```text
Google Sheets = source of truth
Desktop app = control layer
ManaPool = execution/listing layer
ManaBox = scanning/import source
```

### Important Matching Fields

The app uses this combination to identify card rows:

```text
Scryfall ID
Set code
Collector number
Foil
Condition
Language
```

### Recommended Future Improvements

- Profit tracking
- Sales analytics
- Sealed product support
- Bulk repricing
- Better duplicate cleanup tools
- Pricing alerts
- Exportable reports
- Installer packaging

---

## 🏁 TL;DR

```text
Scan in ManaBox
→ Export CSV
→ Merge into app
→ Refresh prices
→ Apply pricing
→ Push to ManaPool
→ Mark sold
→ Track everything in Google Sheets
```
