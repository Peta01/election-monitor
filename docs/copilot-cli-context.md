# Kontext projektu pro Copilot CLI

Repozitář: `Peta01/election-monitor`

## Cíl projektu
Vytvořit aplikaci v Pythonu, která stahuje otevřená data o volbách do zastupitelstev obcí, ukládá jejich snímky do SQLite a zobrazuje časový vývoj výsledků ve webovém rozhraní.

## Přijatá rozhodnutí
- Technologie: Python, SQLite a webové rozhraní.
- Vývoj probíhá lokálně ve VS Code.
- Jedna instance aplikace sleduje jednu obec.
- Stahování se spouští na vyžádání.
- Databázi SQLite lze sdílet.
- Aplikace načítá seznam zastupitelstev z číselníku ČSÚ a používá XML endpoint pro zvolené zastupitelstvo, určený kódem `KODZASTUP`.
- Rozdělení mandátů mezi volební strany se počítá z aktuálních výsledků podle § 45 odst. 1 a 2 zákona č. 491/2001 Sb.

## Stav repozitáře
Uživatelský návod k instalaci a použití je v `docs/uzivatelsky-manual.md`.

Základ aplikace tvoří:
- `src/election_monitor/app.py`
- `src/election_monitor/config.py`
- `src/election_monitor/downloader.py`
- `src/election_monitor/parser.py`
- `src/election_monitor/db.py`
- `src/election_monitor/models.py`
- `src/election_monitor/web.py`
- `src/election_monitor/allocation.py`

Po spuštění příkazem `python -m election_monitor` se spustí místní webová aplikace na `http://127.0.0.1:8000` a otevře se kaskádový výběr kraje, okresu a obce v prohlížeči. Výběr obce ji trvale zaregistruje ke sledování v tabulce `tracked_municipalities`. Pozadí načítá všechny aktivní obce hned po startu a každých 60 sekund, nezávisle na otevřených stránkách. Seznam zastupitelstev se získává z oficiálního registru ČSÚ ve formátu CSV v ZIP archivu a doplňuje se názvy krajů a okresů z číselníku NUTS ČSÚ; číselníky se cachují lokálně na 24 hodin. Změněné snímky ukládá do SQLite, a to jen když se změní počet zpracovaných okrsků. Odebrání z aktivního sledování uchová historické snímky.

Parser podporuje XML výsledky pro konkrétní zastupitelstvo ve volbách 2026. Načítá průběh zpracování, volební účast, počet volených zastupitelů, kandidátní listiny i volební obvody.

Výpočet mandátů snižuje kandidátně upravenou hranici od 5 % podle potřeby, přiděluje mandáty mezi volební strany pomocí d'Hondtových podílů a zaznamená případy, které vyžadují los. Rozdělení mandátů konkrétním kandidátům podle § 45 odst. 3 až 5 zatím není implementováno.

## Další úkol
Rozšířit webové rozhraní o prohlížení historických snímků a časový graf výsledků. Poté doplnit přidělování mandátů konkrétním kandidátům podle § 45 odst. 3 až 5.

Dokumentace zdroje: `https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm`. Formát XML je popsán v `KV2026_XML.htm`. Endpoint pro konkrétní zastupitelstvo má tvar `https://volby.gov.cz/appdata/kv2026/20261009/odata/zastup/vysledky_obec_{KODZASTUP}.xml`. Živá data nejsou dostupná před zahájením zpracování voleb, proto se parser testuje pomocí XML příkladů.

## Další cíle
- Zachovat parser jako samostatný modul.
- Usnadnit pozdější přidání pravidelného stahování.
- Ponechat výpočet virtuálních mandátů v samostatném modulu.
- Upřednostňovat přehledný a dobře testovatelný kód.

## Užitečný odkaz
- Otevřená data ČSÚ: `https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm`
