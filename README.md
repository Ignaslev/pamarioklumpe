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

- Kelių čekių nuotraukų įkėlimas ir AI nuskaitymas; rankinis įvedimas lieka atsarginiu būdu per ankstesnį pridėjimo adresą.
- Kategorijos: Mėsa, Daržovės, Kita. Parduotuvės: Lidl, Norfa, Maxima, Iki ir kitos prekybos vietos.
- Saugoma data, prekė, kiekis (kg, vnt. arba l), vieneto kaina, galutinė sumokėta suma ir čekio žyma.
- Vienodos prekės su tuo pačiu matavimo vienetu sujungiamos suvestinėje; pirminiai įrašai lieka išskleidžiami.
- Vidutinė vieneto kaina skaičiuojama iš sumokėtos sumos ir kiekio. Visos sumos su PVM, po nuolaidų.
- Ataskaitos: diena, savaitė (pirmadienis–sekmadienis), kalendorinis mėnuo.
- Datos su duomenimis pateikiamos pasirinkime; numatyta naujausia įvesta diena.
- Reikalingos migracijos iki `0009_purchasereceipt_purchase_receipt`. Paprastiems vartotojams reikia suteikti `Purchase` modelio teises; supervartotojas jas turi automatiškai.
- Jei čekyje kiekis ar vieneto kaina nenurodyti, laukai gali likti tušti. Suvestinėje tada rodoma „—“, ne išgalvotas svoris.
- Čekio apvalinimas ar mokėjimas lojalumo pinigais įrašomas kaip mokėjimo korekcija prie vienos čekio eilutės. Prekių savikaina lieka atskirta nuo faktiškai sumokėtos sumos.
- Patikrintus čekių duomenis galima įkelti komanda `python manage.py import_purchase_receipts <failas.json> --dry-run`, o po patikros pakartoti be `--dry-run`. Importas patikrina kiekvieno čekio prekių ir mokėjimo sumas; pakartotinis identiško čekio importas nedubliuoja įrašų. Pirminius JSON ir nuotraukas laikykite ignoruojamame `media/purchase-imports/` kataloge.
- „Dienos PDF“ atsisiunčia pasirinktos datos A4 ataskaitą su kategorijų ir parduotuvių suvestinėmis. Didesnės ataskaitos automatiškai tęsiamos kitame A4 puslapyje su pakartotomis lentelių antraštėmis. PDF naudoja į projektą įtrauktą lietuvišką raides palaikantį DejaVu šriftą ir `reportlab`, todėl papildomų Linux sisteminių PDF bibliotekų nereikia.
- PDF testams įdiekite kūrimo priklausomybes: `python -m pip install -r requirements-dev.txt`.

### Čekių nuotraukos ir AI

Pirkimų puslapyje spauskite **Įkelti čekius**. Vienu kartu galima pažymėti iki 30 JPG/PNG/WEBP nuotraukų, po vieną visą čekį faile, iki 15 MB kiekviena. Pirmiausia išsaugomi visi originalai, tada naršyklė nuskaito čekius po vieną. Puslapį palikite atidarytą iki pabaigos. Nutrūkus ryšiui originalai lieka sąraše ir nuskaitymą galima pakartoti.

- Naudojamas Responses API, numatytas modelis `gpt-6.1-sol`, mąstymo lygis `medium`. Modelis nekeičiamas į pigesnį tyliai. Nuotraukos perduodamos į OpenAI; užklausos apmokamos API paskyroje. API raktas niekada nesiunčiamas naršyklei.
- AI užpildo datą, parduotuvę, prekes, kategorijas, kiekius ir kainas. Sumos tikrinamos atskirai programoje: prekių eilutės turi sutapti su čekiu, o prekių suma + mokėjimo korekcija — su faktiškai sumokėta suma. Taip pat tikrinama kiekio ir kainos sandauga bei data čekio numeryje, jei ji yra.
- Sutampant sumoms ir nesant perspėjimų prekės įtraukiamos automatiškai. Neaiškus čekis gauna būseną „Reikia patikrinti“ ir į ataskaitas nepatenka, kol peržiūroje nepataisomi duomenys. Matoma originali nuotrauka ir galima redaguoti visas eilutes. AI nėra neklystantis: net ir sėkmingo nuskaitymo turinį verta peržiūrėti.
- Iš bendrinio užrašo „Prekės“ AI negali nustatyti, kas pirkta. Pvz., 6,65 € čekyje svogūnų laiškų pavadinimą reikės patikslinti ranka.
- To paties failo kopija atpažįstama pagal SHA-256. Skirtingos to paties čekio nuotraukos papildomai tikrinamos pagal parduotuvę, datą ir nuskaitytą numerį. Tai sumažina dublikatų riziką, tačiau klaidingai perskaitytą numerį reikia pataisyti peržiūroje.
- Čekio redagavimas atnaujina visas jo prekes vienoje operacijoje, jų nedubliuoja. Susietų prekių negalima keisti ar trinti atskirai apeinant čekio sumų patikrą.
- Nuskaitymo būsena sąraše ir atidaryto čekio peržiūroje tikrinama kas 5 sekundes, nekartojant mokamos AI užklausos. Po 5 minučių užstrigęs bandymas atlaisvinamas ir pažymimas kaip nutrūkęs; jau užstrigę čekiai sutvarkomi atidarius sąrašą arba peržiūrą po atnaujinimo.
- „Atšaukti nuskaitymą“ išsaugo originalą ir leidžia bandyti iš naujo. Čekį galima ištrinti ir vykstant nuskaitymui. Pavėluotas atšaukto ar ištrinto bandymo atsakymas atmetamas ir pirkimų nesukuria; jis taip pat negali perrašyti vėlesnio bandymo rezultato. Jau išsiųstos OpenAI užklausos atšaukimas vietoje negarantuoja, kad API darbas sustos ar nebus apmokestintas.
- Originalai laikomi `private_media/purchase_receipts/`, ne viešame `media/`. Juos galima atsisiųsti tik prisijungus ir turint pirkimų peržiūros teisę. Aplinkos kintamasis `RECEIPT_STORAGE_ROOT` leidžia nurodyti kitą privatų, ilgalaikį katalogą.

### Diegimas į serverį

**Vietiniai duomenys į Git neįtraukiami.** Vietinis SQLite ir serverio PostgreSQL yra skirtingos duomenų bazės. Kodo diegimas neperkelia kompiuteryje suvestų pirkimų. Įdiegę įkelkite čekius tiesiai į serverio puslapį arba atskirai importuokite patikrintą JSON. Serverio duomenys turi likti toje pačioje DB tarp diegimų; jos nekurkite iš naujo.

Prieš diegdami pasidarykite būtent Pamario DB ir failų atsarginę kopiją. Įprastame Pamario diegimo procese turi būti:

```text
python -m pip install -r requirements-production.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py check
```

Šias komandas vykdykite serverio Pamario virtualioje aplinkoje ir su jo esamu `.env`, ne kitos programos kataloge. Serverio `.env`:

```dotenv
OPENAI_API_KEY=<tikras raktas tik serveryje>
OPENAI_RECEIPT_MODEL=gpt-6.1-sol
OPENAI_RECEIPT_REASONING=medium
```

Jei `OPENAI_API_KEY` jau nustatytas sąskaitoms, naudokite tą pačią eilutę, nedėkite antros. Po nustatymų pakeitimo perkraukite tik Pamario servisus. Patikrinkite, kad valdymo Gunicorn turi bent **120 s** timeout: projekte yra `gunicorn.conf.py`, automatiškai skaitomas paleidžiant iš projekto katalogo. Jei systemd naudoja kitą `--config`, `--timeout` ar darbo katalogą, tą pačią reikšmę reikia nustatyti jo naudojamoje Pamario konfigūracijoje. AI vieno čekio užklausos riba yra 90 s; nutrūkimas nepanaikina originalo.

Tik valdymo svetainės Nginx bloke patikrinkite `client_max_body_size 20m;` ir `proxy_read_timeout 150s;`. Visas paketas nesiunčiamas viena milžiniška užklausa: kiekvienas failas įkeliamas atskirai. Kitiems VPS projektams nustatymų nekeiskite. Programos vartotojas turi turėti rašymo teisę į privatų čekių katalogą. Nei jo, nei DB, nei `.env` negalima valyti per diegimą. Atsarginėse kopijose saugokite DB **ir** `RECEIPT_STORAGE_ROOT`; šio katalogo neviešinkite per Nginx.

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
