# ChallengeHire (Flask + MySQL)

Skill-based recruitment platform. The browser UI (`static/index.html`) talks to a Flask JSON API (`app.py`), which stores everything in MySQL. There is no browser-side data storage: accounts, jobs, applications, challenge submissions and evaluation results all live in the database.

The red banner at the top of the page appears **only** when the backend or database cannot be reached (and shows the reason). When the app is connected to Flask + MySQL, no banner is shown.

## Requirements
- Python 3.10+
- MySQL 8+ (or MariaDB 10.5+)

## Setup
```bash
cd challengehire
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # Windows: copy .env.example .env
```
Create a MySQL user for the app (run as a MySQL admin), then put the same values in `.env`:
```sql
CREATE USER 'challengehire'@'localhost' IDENTIFIED BY 'your-password';
GRANT ALL PRIVILEGES ON challengehire.* TO 'challengehire'@'localhost';
```
Set `SECRET_KEY` in `.env` to a long random string (for example `python -c "import secrets;print(secrets.token_hex(32))"`) and keep `DB_NAME=challengehire`.

Create the tables and load the labelled demo data:
```bash
python init_db.py            # safe to re-run: seeds only when the users table is empty
python init_db.py --reset    # DROPS the database and recreates it (deletes all data)
```
You can also run `schema.sql` yourself with `mysql -u <user> -p < schema.sql` (tables only, no sample data).

## Run
```bash
python app.py
```
Open **http://127.0.0.1:5000** (change the port with `PORT=` in `.env`). Flask serves the frontend and the API from the same origin, so open the site through Flask, not by double-clicking the HTML file.

## Demo accounts (development only)
Created by `init_db.py`. Password for all: `Password123!`

| Role | Email |
|---|---|
| Student | student@demo.dev, diya@demo.dev |
| Recruiter (NovaTech) | recruiter@demo.dev |
| Recruiter (DataLeaf) | karthik@demo.dev |

Demo records (companies marked "(demo)", the `@demo.dev` users, 5 jobs, 5 challenges, 2 applications, 1 evaluated submission) are fictional sample data. New accounts you register are normal records. Delete the demo data with `python init_db.py --reset` before any real use.

## Tests
`pytest -q` runs integration tests against a real MySQL server using a separate database, `challengehire_test`, which it drops and recreates. The `DB_USER` needs permission to create databases.

## API summary
`POST /api/register`, `/api/login`, `/api/logout`, `/api/profile` · `GET /api/bootstrap`, `/api/health` · `POST /api/jobs`, `/api/jobs/<id>/toggle`, `/api/jobs/<id>/apply` · `POST /api/challenges`, `/api/challenges/<id>/submit` · `POST /api/applications/<id>/status`, `/api/submissions/<id>/grade`

Passwords are hashed (Werkzeug), all SQL is parameterized, routes check the user's role and ownership, and a duplicate application is rejected by a unique database constraint. Errors return JSON with a message; an unreachable database returns HTTP 503 with a message that the UI shows in the banner.

## Troubleshooting
- **"Cannot reach the backend server"**: Flask is not running, or the page was not opened through Flask.
- **"Database unavailable"**: MySQL is stopped, or `DB_*` in `.env` is wrong. Check with `mysql -u <DB_USER> -p`.
- **`Access denied` / `Unknown database` when running `init_db.py`**: fix the MySQL user/password in `.env` and the grants above.

## Not included yet
GitHub Pages cannot run this version (it needs a Python server and MySQL), so deploy it to a host that can. AI features are limited to the rule-based skill match, skill-gap and challenge recommendations in the UI; there is no LLM feedback, quiz module or file upload (links only).
