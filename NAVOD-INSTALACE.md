# Návod k instalaci (Windows 10 / 11)

Postup je určen i pro úplné začátečníky. Nepotřebujete nic předem instalovat, instalace případně doinstaluje Python sama.

## Instalace

1. Otevřete stránku projektu na GitHubu: <https://github.com/Peta01/election-monitor>.
2. Klikněte na zelené tlačítko **Code** a vyberte **Download ZIP**.
3. Stažený soubor `election-monitor-main.zip` **rozbalte** (pravé tlačítko myši → *Extrahovat vše…*). Soubory nespouštějte přímo z archivu.
4. V rozbalené složce dvakrát klikněte na **`INSTALOVAT.bat`**.
   - Pokud Windows zobrazí „Windows ochránil váš počítač“, klikněte na *Další informace* → *Přesto spustit*.
   - Když skript nenajde Python 3.11 nebo novější, nainstaluje ho přes `winget`. Může se zobrazit okno s dotazem, které potvrďte.
   - Pokud automatická instalace Pythonu selže, skript otevře stránku python.org. Stáhněte Python, při instalaci **zaškrtněte „Add python.exe to PATH“** a pak spusťte `INSTALOVAT.bat` znovu.
5. Počkejte na hlášku **„Instalace dokončena“** (potřebujete připojení k internetu).

## Spuštění

1. Dvakrát klikněte na **`SPUSTIT.bat`**.
2. Po chvíli se otevře prohlížeč na adrese <http://127.0.0.1:8000>.
3. Vyberte kraj, okres a obec, kterou chcete sledovat.
4. **Okno s černým pozadím nezavírejte.** Dokud běží, aplikace každých 60 sekund stahuje výsledky vybraných obcí. Po jeho zavření se sledování zastaví.

Obce je vhodné přidat před zahájením sčítání (volby 9. 10. 2026), aby se data ukládala od začátku. Sledované obce a výsledky zůstávají uložené ve složce `data` i po restartu.

## Aktualizace

Stáhněte novou verzi jako ZIP, rozbalte ji do nové složky a spusťte `INSTALOVAT.bat`. Chcete-li zachovat dosavadní data, zkopírujte do nové složky původní složku `data`.

## Řešení potíží

| Problém | Řešení |
|---|---|
| Okno se hned zavře | Spouštějte soubor dvojklikem z rozbalené složky, ne z archivu ZIP. |
| „Python nebyl nalezen“ po instalaci | Zavřete okno a spusťte `INSTALOVAT.bat` znovu, nebo restartujte počítač. |
| Prohlížeč se neotevřel | Ručně otevřete <http://127.0.0.1:8000>. |
| „Address already in use“ | Aplikace už běží v jiném okně. Zavřete ho a zkuste to znovu. |
| Chyba při stahování knihoven | Zkontrolujte připojení k internetu a spusťte `INSTALOVAT.bat` znovu. |

Další informace najdete v [uživatelském manuálu](docs/uzivatelsky-manual.md).
