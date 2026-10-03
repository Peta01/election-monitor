# Uživatelský manuál

## Co aplikace umí

Aplikace nabízí výběr zastupitelstva z číselníku ČSÚ. Výběrem obec trvale přidáte do seznamu sledovaných obcí; aplikace její výsledky kontroluje a ukládá každých 60 sekund na pozadí. Sledování pokračuje i po zavření výsledkové stránky a obnoví se po restartu aplikace. Pokud jsou k dispozici úplné výsledky, vypočítá se také virtuální počet mandátů pro jednotlivé volební strany podle § 45 odst. 1 a 2 zákona č. 491/2001 Sb.

Ukládá se jen snímek, ve kterém se změnil počet zpracovaných okrsků; ostatní kontroly ČSÚ novou řádku nevytvářejí. Historie se ukládá do SQLite, ale její prohlížení zatím není implementováno.

## Požadavky

- Windows a PowerShell
- Python 3.11 nebo novější
- Připojení k internetu pro stažení dat ČSÚ

## Instalace

Otevřete PowerShell v kořenové složce repozitáře a vytvořte virtuální prostředí:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Virtuální prostředí stačí vytvořit a nainstalovat jednou. Při dalších spuštěních otevřete PowerShell v kořenové složce projektu a znovu ho aktivujte:

```powershell
.\.venv\Scripts\Activate.ps1
```

Pokud PowerShell blokuje aktivaci skriptu, lze použít přímo Python z virtuálního prostředí a prostředí aktivovat nemusíte:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

## Výběr obce a kód zastupitelstva

Aplikace načte aktuální registr zastupitelstev z webu ČSÚ. Při prvním spuštění a po vypršení 24hodinové mezipaměti je k načtení seznamu nutné připojení k internetu. Při výpadku ČSÚ se použije poslední uložená mezipaměť, pokud existuje.

Po spuštění v prohlížeči postupně vyberte **kraj**, **okres** a **obec**. Nabídka každého kroku se zúží podle předchozí volby. Poté stiskněte **Začít sledovat obec**. Kód zastupitelstva (`KODZASTUP`) se předá aplikaci automaticky a obec zůstane ve sledování, i když zavřete její stránku.

## Stažení a uložení výsledků

Spuštění aplikace:

```powershell
python -m election_monitor
```

Příkaz spustí místní webový server na `http://127.0.0.1:8000` a otevře tuto adresu v prohlížeči. Aplikace je určena pro místní použití na počítači, kde běží.

Po přidání zastupitelstva aplikace okamžitě zahájí stahování jeho XML dat. Na pozadí ověřuje kód a každých 60 sekund znovu načte výsledky všech sledovaných obcí; není nutné nechávat otevřený prohlížeč. Výsledková stránka se také obnovuje každých 60 sekund a zobrazuje naposledy uložená data. Pokud se nezměnil počet zpracovaných okrsků, další snímek se do databáze nepřidá. Databáze se ukládá do:

```text
data/election_monitor.sqlite3
```

Na úvodní stránce se zobrazí sledované obce, čas posledního úspěšného načtení nebo případná chyba. Novou obec přidáte dalším výběrem. Tlačítkem **Přestat sledovat** ji vyřadíte z pravidelného stahování; již uložené snímky zůstanou v databázi.

Sledování probíhá jen po dobu, kdy běží místní server. Server ukončíte zavřením okna terminálu nebo stisknutím `Ctrl+C`; při příštím spuštění se uložené obce začnou znovu stahovat.

## Světlý a tmavý režim

Tlačítkem v pravé části horní lišty přepnete mezi světlým a tmavým vzhledem. Vybraný režim se uloží v prohlížeči a zůstane zachovaný při automatickém obnovení výsledků. Pokud jste režim ještě nenastavili, stránka se přizpůsobí vzhledu systému.

## Jak číst stav výpočtu

- Výpočet přiděluje mandáty volebním stranám samostatně za každý volební obvod.
- Průběžné výsledky nemusí obsahovat platné hlasy ve všech obvodech. V takovém případě se mandáty nevypočítají a aplikace vypíše upozornění.
- Pokud podle zákonných pravidel rozhoduje o mandátu los, aplikace vypíše varování. Uložené virtuální rozdělení v takovém případě používá pořadí kódů kandidátních listin pouze jako deterministický náhled; není to výsledek losování ČSÚ.
- Konkrétní kandidáty s mandáty aplikace určuje orientačně: podle pořadí na hlasovacím lístku (§ 45 odst. 3). Přeřazení podle hlasů kandidátů (odst. 4) se použije, až ČSÚ hlasy kandidátů zveřejní; průběžná data ČSÚ je zatím neobsahují. Náhradníci (odst. 5) nejsou implementováni.

## Kandidáti, vývoj výsledků a složení zastupitelstva

- Na stránce výsledků obce jsou pod tabulkou listin rozbalovací seznamy kandidátů každé listiny (jméno, věk, povolání, bydliště; hlasy kandidáta, až budou ve zdroji, jinak „—“). Kandidáti se berou z registru ČSÚ.
- Odkaz „Vývoj výsledků a složení zastupitelstva“ otevře stránku s grafy podílu hlasů a virtuálních mandátů stran podle počtu zpracovaných okrsků a se složením zastupitelstva jmenovitě. Stav složení lze vybrat po zpracování libovolného uloženého počtu okrsků; tabulka změn ukazuje, kdo se v čase přidal nebo vypadl.
- Složení je orientační a závisí na uložených snímcích; při losu je jen náhledem.
- Při úspěšném načtení výsledky odpovídají poslední uložené odpovědi ČSÚ. Pokud se zdroj dočasně odmlčí, aplikace zobrazí poslední známé výsledky a chybu aktualizace; další pokus provede na pozadí za 60 sekund.

## Řešení potíží

### Číselník obcí se nepodařilo načíst

Zkontrolujte připojení k internetu. Pokud jste aplikaci už dříve spustili a má uloženou mezipaměť číselníku, zobrazí ji i při dočasném výpadku ČSÚ; jinak zkuste stránku obnovit později.

### Zdroj vrací chybu nebo stránku nenalezl

Ověřte správnost kódu zastupitelstva a připojení k internetu. Živá data ČSÚ nemusejí být dostupná před zahájením zpracování voleb; endpoint může před zveřejněním výsledků vracet chybu HTTP 404 nebo XML s chybovým hlášením. Zkuste stažení znovu později.

### Výsledky jsou neúplné

ČSÚ zveřejňuje průběžné výsledky. Dokud nejsou zpracovány všechny potřebné volební obvody, aplikace nemusí spočítat virtuální mandáty. Dalším spuštěním stáhnete nový snímek, pokud ČSÚ mezitím zveřejnil aktualizovaná data.

### Databáze nebo uložené snímky

Databáze je soubor `data/election_monitor.sqlite3` v repozitáři. Pokud chcete uloženou historii zachovat, soubor nemažte; před případnou údržbou si vytvořte jeho kopii. Aplikace zatím nemá uživatelské rozhraní pro prohlížení, export ani mazání snímků.

### Port 8000 je obsazený

Zavřete jinou aplikaci používající adresu `http://127.0.0.1:8000` a spusťte volební přehled znovu.

## Zdroj dat a právní informace

- Otevřená data ČSÚ: <https://volby.gov.cz/opendata/kv2026/kv2026_opendata.htm>
- Výpočet mandátů mezi volební strany: § 45 odst. 1 a 2 zákona č. 491/2001 Sb.
- Virtuální rozdělení mandátů je informativní výpočet aplikace; při losu nemůže nahrazovat oficiální postup ČSÚ.
