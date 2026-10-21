# Pamario Klumpė

Current scope only:

- `pamarioklumpe.lt` — logo and „Greitai...“;
- `valdyti.pamarioklumpe.lt` — login-protected management;
- management pages — darbuotojai, darbo laikas, meniu and sąskaitos.

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

## Prekių pirkimas

Vietinis puslapis: `http://127.0.0.1:8020/valdyti/prekiu-pirkimas/`.
Produkcijoje po diegimo: `https://valdyti.pamarioklumpe.lt/prekiu-pirkimas/`.

- Rankinis prekių iš čekių įvedimas, redagavimas ir trynimas.
- Kategorijos: Mėsa, Daržovės, Kita. Parduotuvės: Lidl, Norfa, Maxima, Iki ir kitos prekybos vietos.
- Saugoma data, prekė, kiekis (kg, vnt. arba l), vieneto kaina, galutinė sumokėta suma ir čekio žyma.
- Vienodos prekės su tuo pačiu matavimo vienetu sujungiamos suvestinėje; pirminiai įrašai lieka išskleidžiami.
- Vidutinė vieneto kaina skaičiuojama iš sumokėtos sumos ir kiekio. Visos sumos su PVM, po nuolaidų.
- Ataskaitos: diena, savaitė (pirmadienis–sekmadienis), kalendorinis mėnuo.
- Datos su duomenimis pateikiamos pasirinkime; numatyta naujausia įvesta diena.
- Reikalinga migracija `0007_purchase`. Paprastiems vartotojams reikia suteikti `Purchase` modelio teises; supervartotojas jas turi automatiškai.
- Nuotraukų automatinis nuskaitymas šiame etape neįtrauktas: pirmiausia įvedami iš pateiktų čekių patikrinti duomenys.
- Jei čekyje kiekis ar vieneto kaina nenurodyti, laukai gali likti tušti. Suvestinėje tada rodoma „—“, ne išgalvotas svoris.
- Čekio apvalinimas ar mokėjimas lojalumo pinigais įrašomas kaip mokėjimo korekcija prie vienos čekio eilutės. Prekių savikaina lieka atskirta nuo faktiškai sumokėtos sumos.
- Patikrintus čekių duomenis galima įkelti komanda `python manage.py import_purchase_receipts <failas.json> --dry-run`, o po patikros pakartoti be `--dry-run`. Importas patikrina kiekvieno čekio prekių ir mokėjimo sumas; pakartotinis identiško čekio importas nedubliuoja įrašų. Pirminius JSON ir nuotraukas laikykite ignoruojamame `media/purchase-imports/` kataloge.
- „Dienos PDF“ atsisiunčia pasirinktos datos A4 ataskaitą su kategorijų ir parduotuvių suvestinėmis. Didesnės ataskaitos automatiškai tęsiamos kitame A4 puslapyje su pakartotomis lentelių antraštėmis. PDF naudoja į projektą įtrauktą lietuvišką raides palaikantį DejaVu šriftą ir `reportlab`, todėl papildomų Linux sisteminių PDF bibliotekų nereikia.
- PDF testams įdiekite kūrimo priklausomybes: `python -m pip install -r requirements-dev.txt`.

## Arduino darbo laiko terminalas

Kiekvienam darbuotojui jo redagavimo lange galima priskirti unikalų RFID lusto UID. Terminalas siunčia užklausą į:

`POST https://valdyti.pamarioklumpe.lt/api/clock/scan/`

Antraštė:

`X-Device-Key: <CLOCK_DEVICE_API_KEY>`

JSON turinys:

```json
{"uid": "04A1B2C3"}
```

Pirmas nuskaitymas registruoja atvykimą, kitas — išvykimą. Pakartotinis to paties lusto nuskaitymas per 15 sekundžių nesukuria antro įrašo. Serverio raktas laikomas tik `.env` faile, o Arduino kopija — atskirame į Git neįtraukiamame paslapčių faile.
