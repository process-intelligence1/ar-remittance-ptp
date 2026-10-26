# Day 2 — Run the backend on your laptop

Goal: the API runs on your laptop, the database has all tables, and your SAP
Excel data is loaded. Time: about 45 minutes.

All commands run in the VS Code terminal (PowerShell). Run them one at a time.

---

## Step 1 — Put the files in place

1. Extract the zip **into** `D:\Finance\AR_Remittance` (choose "Extract all…",
   enter `D:\Finance\AR_Remittance`). If Windows asks to replace `README.md`, choose **Replace**.
2. VS Code: **File → Open Folder → D:\Finance\AR_Remittance**.
3. If VS Code suggests installing recommended extensions (Python, SQLTools), click **Install**.

You should see the folders `backend`, `data`, `docs` on the left.

## Step 2 — Allow PowerShell to run the Python environment script (one time)

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```
Type `Y` if asked. *Windows blocks scripts by default; this allows scripts you
created locally. Needed for step 3.*

## Step 3 — Create a private Python environment for this project

```powershell
cd D:\Finance\AR_Remittance\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
✅ The prompt now starts with **(.venv)**.

*A "virtual environment" is a private set of Python libraries for this project
only, so it never clashes with other Python work on your laptop. You must
activate it (the last line) each time you open a new terminal.*

## Step 4 — Install the libraries

```powershell
pip install -r requirements.txt
```
✅ Ends with "Successfully installed …". *Downloads the exact versions listed in
requirements.txt (API framework, database driver, migration tool, Excel reader).*

## Step 5 — Create your settings file

```powershell
Copy-Item ..\.env.example ..\.env
code ..\.env
```
In the file that opens, change **only** these lines and save (Ctrl+S):

- `DATABASE_URL` → replace `YOUR_AR_APP_PASSWORD` with the **ar_app** password from Day 1
- `GMAIL_CLIENT_SECRET_FILE` → replace `YOUR_CLIENT_SECRET_FILE.json` with your secret's file name

⚠️ If the ar_app password contains any of `@ : / # % ?`, tell me — they need special encoding.

*`.env` holds settings and passwords for your laptop only. It is listed in
`.gitignore`, so Git never uploads it.*

## Step 6 — Create the database tables

```powershell
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```
✅ First command: "Generating …\alembic\versions\…_initial_tables.py … done".
✅ Second command: "Running upgrade -> …, initial tables".

*Alembic compares the table definitions in `app/models` with the database and
writes the difference as a numbered "migration" file (first command), then
applies it (second command). Every future table change works the same way, so
the laptop and Azure databases always have identical structures.*

## Step 7 — Load your SAP data, rules and demo users

```powershell
python -m scripts.load_reference
python -m scripts.seed_app
```
✅ Expected:
```
  t001        6 rows
  tcurx      16 rows
  t052       10 rows
  tcurr   31875 rows
  kna1       71 rows
  knb1       77 rows
  knbk       96 rows
  knvp      308 rows
  adr6      166 rows
  bsid     4840 rows
  bsad        0 rows
Rules in database: 12   Demo users: 4
```
*The first script reads the four Excel files in `data/seed` and loads them into
the `sap` tables. The second stores the Knowledge Base rules (weights,
thresholds, tolerances) and four demo users, one per role.*

## Step 8 — Start the API and try it

```powershell
uvicorn app.main:app --reload
```
✅ "Uvicorn running on http://127.0.0.1:8000".

Open **http://127.0.0.1:8000/docs** in your browser. This page lists every API
endpoint. Try:

1. **GET /api/health** → *Try it out* → *Execute* → `"database": true`
2. **GET /api/reference/summary** → the row counts from step 7
3. **GET /api/customers/{kunnr}** → kunnr `102419` → Pacific Rim Traders with its e-mails, company codes and open items
4. **GET /api/open-items** → ref `JP-26-002271` → the invoice from sample e-mail P03-0193 (SGD 8,300)

Stop the API with **Ctrl+C** in the terminal.

*`uvicorn` is the web server that runs the FastAPI app. `--reload` restarts it
automatically whenever a code file changes.*

## Step 9 — Save to GitHub

Open a **second** terminal (the **+** in the terminal panel), then:
```powershell
cd D:\Finance\AR_Remittance
git status
```
Check the list: it must **not** contain `.env` or anything from `D:\Finance\Secret`.
```powershell
git add .
git commit -m "Day 2: backend skeleton, database tables, SAP reference data loader"
git push
```
✅ github.com/process-intelligence1/ar-remittance-ptp now shows the folders.

---

## If something fails
Copy the red text (or a screenshot) and send it. Common ones:

| Message | Fix |
|---|---|
| `running scripts is disabled on this system` | Step 2 wasn't run |
| `password authentication failed for user "ar_app"` | Wrong password in `.env` `DATABASE_URL` |
| `No module named 'app'` | Run the command from the `backend` folder |
| `alembic: command not found` / not recognized | The prompt doesn't show `(.venv)` — run `.\.venv\Scripts\Activate.ps1` |
