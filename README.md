# election-monitor

Pythonová aplikace pro sledování otevřených dat ČSÚ o volbách do zastupitelstev obcí, ukládání výsledků do SQLite a jejich přehledné zobrazení. **Aktuální verze: 0.2.0.**

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

Přidělování mandátů volebním stranám se počítá podle § 45 odst. 1 a 2 zákona č. 491/2001 Sb. Aplikace zohledňuje kandidátně upravenou hranici, její případné snižování a přidělování mandátů pomocí d'Hondtových podílů. Výpočet se provádí samostatně pro každý volební obvod. Po dokončení zpracování obecních výsledků zobrazuje oficiální jména zvolených zastupitelů a jejich hlasy z výsledkového XML ČSÚ. Pokud zákonné pravidlo vyžaduje los, aplikace na to upozorní. Stránka `/vysledky/{kód}/vyvoj` obsahuje vývoj výsledků a jmenovité složení zastupitelstva.

## Funkce

- Stahovat otevřená volební data pro jednu obec
- Ukládat průběžné výsledky do SQLite
- Zobrazovat aktuální výsledky a průběh zpracování
- Zobrazovat virtuální rozdělení mandátů mezi volební strany
- Zobrazovat zvolené zastupitele a jejich oficiální počty hlasů
- Vytvářet pro každou dokončenou sledovanou obec samostatnou prezentaci výsledků ve formátu A4 PDF
