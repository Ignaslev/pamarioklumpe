# Pamario Klumpė

Current scope only:

- `pamarioklumpe.lt` — logo and „Greitai...“;
- `valdyti.pamarioklumpe.lt` — login-protected management;
- first management page — darbuotojai.

## Structure

```text
pamarioklumpe/   Master Django project and public pamarioklumpe.lt site
ValdytiAPP/      Logged-in management app for valdyti.pamarioklumpe.lt
manage.py        Django command entry point
```

`pamarioklumpe` owns the settings, public routes, public templates, and public static files.

`ValdytiAPP` owns the management routes, login, dashboard, models, management templates/static files, and the first `darbuotojai` feature.

This mirrors the familiar Finance structure:

```text
moneycoach/  -> pamarioklumpe/
finance/     -> ValdytiAPP/
accounts/    -> not needed yet
```

## Local setup

Project folder:

`C:\Users\X\Documents\Pamario klumpe`

```bash
source .venv/Scripts/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

- Public: `http://127.0.0.1:8000/`
- Management: `http://127.0.0.1:8000/valdyti/`
- Django Admin: `http://127.0.0.1:8000/valdyti/admin/`

## Database

The application reads `DATABASE_URL` from `.env`.

- Without `DATABASE_URL`, local development temporarily falls back to `local.sqlite3`.
- Local PostgreSQL will use a separate `pamarioklumpe_dev` database.
- Production will use separate credentials stored only on the VPS.

Never connect local development directly to the production database.

## Domain routing

- Local combined server: `DJANGO_ROOT_URLCONF=pamarioklumpe.local_urls`
- `pamarioklumpe.lt`: `DJANGO_ROOT_URLCONF=pamarioklumpe.urls`
- `valdyti.pamarioklumpe.lt`: `DJANGO_ROOT_URLCONF=ValdytiAPP.urls`

The production domains use the same settings and PostgreSQL database, but separate Gunicorn services and Nginx server blocks.

## Before pushing

```bash
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
```

Do not commit `.env`, `.venv`, SQLite databases, logs, media, or `staticfiles`.

