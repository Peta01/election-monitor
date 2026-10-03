# election-monitor

Pythonová aplikace pro stahování otevřených dat o volbách do zastupitelstev obcí, ukládání průběžných výsledků do SQLite a jejich zobrazení v časové řadě.

## Lokální spuštění

**Pro běžné uživatele (Windows):** stáhněte ZIP z GitHubu, rozbalte, spusťte `INSTALOVAT.bat` a potom `SPUSTIT.bat`. Podrobný návod je v [NAVOD-INSTALACE.md](NAVOD-INSTALACE.md). Instalace případně doinstaluje i Python.

**Pro vývojáře:**

Podrobný návod k instalaci, nastavení, stahování výsledků a řešení potíží najdete v [uživatelském manuálu](docs/uzivatelsky-manual.md).

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m election_monitor
```

Po spuštění aplikace otevře prohlížeč na místní stránce s kaskádovým výběrem kraje, okresu a obce. Seznam vychází z oficiálních číselníků ČSÚ. Výběrem obec trvale přidáte do sledování; aplikace stahuje výsledky všech sledovaných obcí každých 60 sekund, i když jejich stránka není otevřená. Sledované obce zůstávají uložené i po restartu aplikace a lze je odebrat na úvodní stránce. Číselníky se ukládají do místní mezipaměti. Databáze výsledků je `data/election_monitor.sqlite3`.

V horní části stránky lze přepínat světlý a tmavý režim. Volba se uloží v prohlížeči a zůstane zachována i po automatickém obnovení výsledků.

Přidělování mandátů volebním stranám se počítá podle § 45 odst. 1 a 2 zákona č. 491/2001 Sb. Aplikace zohledňuje kandidátně upravenou hranici, její případné snižování a přidělování mandátů pomocí d'Hondtových podílů. Výpočet se provádí samostatně pro každý volební obvod. Pokud zákonné pravidlo vyžaduje los, aplikace na to upozorní a pořadí kódů kandidátních listin použije pouze pro deterministický náhled. Pořadí konkrétních kandidátů se určuje orientačně podle lístku (§ 45 odst. 3); přeřazení podle hlasů kandidátů (odst. 4) se použije, jakmile je zdroj poskytne, náhradníci (odst. 5) zatím implementováni nejsou. Detail obce obsahuje seznam kandidátů z registru ČSÚ a stránku `/vysledky/{kód}/vyvoj` s grafy v čase a jmenovitým složením zastupitelstva.

## Funkce

- Stahovat otevřená volební data pro jednu obec
- Ukládat průběžné výsledky do SQLite
- Zobrazovat aktuální výsledky a průběh zpracování
- Zobrazovat virtuální rozdělení mandátů mezi volební strany
