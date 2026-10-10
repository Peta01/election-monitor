from __future__ import annotations

import sqlite3
from contextlib import asynccontextmanager
from html import escape
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from . import municipalities
from .candidates import Candidate, get_candidates
from .charts import legend_html, line_chart_svg
from .composition import candidates_for_party, council_composition
from .config import DB_PATH, DEFAULT_POLL_INTERVAL_SECONDS
from .db import Repository
from .models import ElectionSnapshot
from .municipalities import RegistryError
from .polling import PollingService


@asynccontextmanager
async def lifespan(_app: FastAPI):
    polling_service.start()
    try:
        yield
    finally:
        polling_service.stop()


polling_service = PollingService(Repository(DB_PATH))
app = FastAPI(title="Volební přehled", lifespan=lifespan)

STYLES = """
<style>
:root, [data-theme="light"] {
  color-scheme: light;
  --page: #f2f5f9;
  --surface: #ffffff;
  --surface-muted: #f2f6fa;
  --text: #172b4d;
  --text-muted: #52657b;
  --border: #dce3eb;
  --border-subtle: #e1e7ee;
  --control-border: #9aaabd;
  --alert: #fff4dc;
  --alert-border: #d68c00;
  --bar-track: #e0e8f1;
  --bar-fill: #2475b9;
  --shadow: #18314a0b;
}
[data-theme="dark"] {
  color-scheme: dark;
  --page: #111820;
  --surface: #1b2632;
  --surface-muted: #243241;
  --text: #e5edf5;
  --text-muted: #b1c0d0;
  --border: #3b4b5c;
  --border-subtle: #334354;
  --control-border: #718398;
  --alert: #382e1c;
  --alert-border: #e2a935;
  --bar-track: #344354;
  --bar-fill: #68aee8;
  --shadow: #00000030;
}
* { color-scheme: inherit; }
html { background: var(--page); }
body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; color: var(--text);
  background: var(--page); font-synthesis: none; }
* { box-sizing: border-box; }
header { display: flex; justify-content: space-between; align-items: center; gap: 1rem;
  background: #123b69; color: white; padding: .35rem max(1rem, calc((100vw - 980px) / 2)); font-size: .95rem; }
header a { color: white; text-decoration: none; }
main { width: min(980px, calc(100% - 2rem)); margin: 2rem auto; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: clamp(1.1rem, 3vw, 2rem); box-shadow: 0 4px 18px var(--shadow); }
h1 { margin-top: 0; font-size: clamp(1.5rem, 4vw, 2rem); }
h2 { margin-top: 2rem; }
p { line-height: 1.55; }
label { display: block; font-weight: 600; margin: 1.2rem 0 .4rem; }
input, select, button { font: inherit; }
input[type=search], select { width: 100%; min-height: 2.8rem; padding: .55rem .7rem;
  border: 1px solid var(--control-border); border-radius: 6px; background: var(--surface);
  color: var(--text); }
button, .button { display: inline-block; border: 0; border-radius: 6px; background: #145da0;
  color: white; font-weight: 600; padding: .75rem 1.1rem; cursor: pointer; text-decoration: none; }
button:hover, .button:hover { background: #0d477d; }
.theme-toggle { border: 1px solid #ffffff90; background: transparent; padding: .2rem .6rem;
  font-size: .85rem; white-space: nowrap; }
.theme-toggle:hover { background: #ffffff20; }
.theme-toggle:focus-visible, button:focus-visible, a:focus-visible, select:focus-visible {
  outline: 3px solid #f0b429; outline-offset: 2px; }
.actions { display: flex; flex-wrap: wrap; align-items: center; gap: .8rem; margin-top: 1.2rem; }
.muted { color: var(--text-muted); }
.alert { padding: 1rem; border-radius: 7px; background: var(--alert);
  border-left: 4px solid var(--alert-border); }
.stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: .8rem; }
.stat { padding: 1rem; background: var(--surface-muted); border-radius: 8px; }
.stat strong { display: block; font-size: 1.35rem; margin-top: .3rem; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
th, td { text-align: left; padding: .7rem .6rem; border-bottom: 1px solid var(--border-subtle); }
th { background: var(--surface-muted); white-space: nowrap; }
td.numeric, th.numeric { text-align: right; font-variant-numeric: tabular-nums; }
.bar { height: .5rem; background: var(--bar-track); border-radius: 10px; overflow: hidden; }
.bar span { display: block; height: 100%; background: var(--bar-fill); }
footer { width: min(980px, calc(100% - 2rem)); margin: 1rem auto 2rem;
  color: var(--text-muted); font-size: .9rem; }
.tracked-list { list-style: none; padding: 0; margin: 0; }
.tracked-list li { display: flex; justify-content: space-between; align-items: center;
  gap: 1rem; padding: .8rem 0; border-bottom: 1px solid var(--border-subtle); }
.tracked-link { color: var(--text); text-decoration: none; }
.tracked-link:hover { color: #2475b9; text-decoration: underline; }
.tracked-list form { margin: 0; }
.remove-button { background: transparent; color: var(--text-muted); border: 1px solid var(--border);
  padding: .45rem .65rem; }
.remove-button:hover { background: var(--alert); color: var(--text); }
.chart { width: 100%; height: auto; margin-top: .5rem; }
.legend { list-style: none; display: flex; flex-wrap: wrap; gap: .4rem 1.1rem; padding: 0;
  margin: .4rem 0 0; font-size: .9rem; }
.swatch { display: inline-block; width: .8rem; height: .8rem; border-radius: 2px;
  margin-right: .4rem; }
details { margin-top: .6rem; border: 1px solid var(--border-subtle); border-radius: 8px;
  padding: .3rem .8rem; }
summary { cursor: pointer; font-weight: 600; padding: .4rem 0; }
@media (max-width: 520px) { main { margin: 1rem auto; } th, td { padding: .6rem .4rem; } }
</style>
"""

THEME_SCRIPT = """
<script>
(() => {
  let savedTheme = null;
  try {
    savedTheme = localStorage.getItem("election-monitor-theme");
  } catch {}
  const theme = savedTheme === "dark" || savedTheme === "light"
    ? savedTheme
    : (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  document.documentElement.dataset.theme = theme;
})();
</script>
"""

THEME_TOGGLE = """
<button class="theme-toggle" id="theme-toggle" type="button"
  aria-label="Přepnout barevný režim" aria-pressed="false">
  <span id="theme-toggle-label">Tmavý režim</span>
</button>
<script>
(() => {
  const button = document.getElementById("theme-toggle");
  const label = document.getElementById("theme-toggle-label");
  function updateButton(theme) {
    const isDark = theme === "dark";
    label.textContent = isDark ? "Světlý režim" : "Tmavý režim";
    button.setAttribute("aria-pressed", String(isDark));
  }
  updateButton(document.documentElement.dataset.theme);
  button.addEventListener("click", () => {
    const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = theme;
    updateButton(theme);
    try {
      localStorage.setItem("election-monitor-theme", theme);
    } catch {}
  });
})();
</script>
"""


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    try:
        options = municipalities.get_municipalities()
    except municipalities.RegistryError as exc:
        return _page(
            "Výběr obce",
            f'<div class="alert"><strong>Číselník obcí se nepodařilo načíst.</strong>'
            f"<p>{escape(str(exc))}</p><p>Zkontrolujte připojení k internetu a "
            "obnovte stránku.</p></div>",
        )
    except requests.RequestException:
        return _page(
            "Výběr obce",
            '<div class="alert"><strong>Číselník obcí ČSÚ je momentálně nedostupný.</strong>'
            "<p>Zkontrolujte připojení k internetu a obnovte stránku.</p></div>",
        )

    tracked_municipalities = polling_service.repository.list_tracked_municipalities()
    tracked_codes = {item["code"] for item in tracked_municipalities}
    regions = sorted(
        {(option.region_code, option.region_name) for option in options},
        key=lambda item: item[1].casefold(),
    )
    region_options = "\n".join(
        f'<option value="{escape(code, quote=True)}">{escape(name)}</option>'
        for code, name in regions
    )
    districts = sorted(
        {
            (option.region_code, option.district_code, option.district_name)
            for option in options
        },
        key=lambda item: (item[0], item[2].casefold()),
    )
    district_options = "\n".join(
        f'<option value="{escape(code, quote=True)}" '
        f'data-region="{escape(region_code, quote=True)}">{escape(name)}</option>'
        for region_code, code, name in districts
    )
    municipality_options = "\n".join(
        f'<option value="{escape(option.code, quote=True)}" '
        f'data-region="{escape(option.region_code, quote=True)}" '
        f'data-district="{escape(option.district_code, quote=True)}" '
        f'data-tracked="{"true" if option.code in tracked_codes else "false"}">'
        f"{escape(option.label)} ({escape(option.code)})"
        f"{' — již sledujete' if option.code in tracked_codes else ''}</option>"
        for option in options
    )
    tracked_html = "".join(
        _tracked_municipality_html(item) for item in tracked_municipalities
    )
    tracked_section = (
        f"<h2>Sledované obce ({len(tracked_municipalities)})</h2>"
        f'<ul class="tracked-list">{tracked_html}</ul>'
        if tracked_municipalities
        else '<h2>Sledované obce</h2><p class="muted">Zatím nesledujete žádnou obec.</p>'
    )
    body = f"""
    <section class="card">
      <h1>Vyberte obec</h1>
      <p class="muted">Přidejte obec ke sledování. Její výsledky se budou stahovat každých
      {DEFAULT_POLL_INTERVAL_SECONDS} sekund, i když zavřete stránku.</p>
      <form action="/vyber" method="get">
        <label for="region-select">Kraj</label>
        <select id="region-select" required>
          <option value="" selected disabled>Nejprve vyberte kraj…</option>
          {region_options}
        </select>
        <label for="district-select">Okres</label>
        <select id="district-select" disabled required>
          <option value="" selected disabled>Nejprve vyberte okres…</option>
          {district_options}
        </select>
        <label for="municipality-select">Obec</label>
        <select id="municipality-select" name="code" disabled required>
          <option value="" selected disabled>Nejprve vyberte obec…</option>
          {municipality_options}
        </select>
        <div class="actions">
          <button type="submit">Začít sledovat obec</button>
          <span class="muted">{len(regions)} krajů · {len(districts)} okresů ·
          {len(options)} obcí a zastupitelstev ČSÚ</span>
        </div>
      </form>
    </section>
    <section class="card" style="margin-top:1rem">{tracked_section}</section>
    <script>
      const region = document.getElementById("region-select");
      const district = document.getElementById("district-select");
      const municipality = document.getElementById("municipality-select");
      function filterOptions(select, matches) {{
        for (const option of select.options) {{
          if (option.value) option.hidden = !matches(option);
        }}
        select.value = "";
      }}
      region.addEventListener("change", () => {{
        filterOptions(district, option => option.dataset.region === region.value);
        filterOptions(municipality, option => option.dataset.region === region.value);
        district.disabled = false;
        municipality.disabled = true;
      }});
      district.addEventListener("change", () => {{
        filterOptions(municipality, option =>
          option.dataset.region === region.value && option.dataset.district === district.value);
        municipality.disabled = false;
      }});
    </script>
    """
    return _page("Výběr obce", body)


@app.get("/vyber")
def select_municipality(code: str) -> RedirectResponse:
    try:
        options = municipalities.get_municipalities()
    except (municipalities.RegistryError, requests.RequestException):
        return RedirectResponse("/", status_code=303)
    selected = next((option for option in options if option.code == code), None)
    if selected is None:
        return RedirectResponse("/", status_code=303)
    polling_service.track(selected)
    return RedirectResponse(f"/vysledky/{code}", status_code=303)


@app.post("/sledovani/{code}/odebrat")
def remove_municipality(code: str) -> RedirectResponse:
    if len(code) == 6 and code.isascii() and code.isdigit():
        polling_service.repository.remove_tracked_municipality(code)
    return RedirectResponse("/", status_code=303)


@app.get("/prezentace/{code}")
def presentation(code: str) -> Response:
    if not _valid_code(code):
        raise HTTPException(status_code=404, detail="Prezentace není dostupná.")
    generated = polling_service.repository.get_presentation(code)
    if generated is None:
        raise HTTPException(status_code=404, detail="Prezentace ještě nebyla vytvořena.")
    path = Path(generated["file_path"])
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Soubor prezentace není dostupný.")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"vysledky-{code}.pdf",
    )


@app.get("/vysledky/{code}", response_class=HTMLResponse)
def results(code: str) -> HTMLResponse:
    if len(code) != 6 or not code.isascii() or not code.isdigit():
        return RedirectResponse("/", status_code=303)
    tracking = polling_service.repository.get_tracking_status(code)
    if tracking is None:
        return RedirectResponse("/", status_code=303)

    snapshot = polling_service.repository.get_latest_snapshot(code)
    if snapshot is None:
        message = (
            "ČSÚ zatím neposkytl výsledky."
            if tracking["last_error"]
            else "Obec byla přidána ke sledování. Čekáme na první odpověď ČSÚ."
        )
        if tracking["last_error"]:
            message += f" Poslední chyba: {escape(tracking['last_error'])}"
        return _results_error(code, message, _council_label(tracking))
    return _results_page(_council_label(tracking), snapshot, tracking)


def _results_error(
    code: str, message: str, title: str = "Vybrané zastupitelstvo"
) -> HTMLResponse:
    body = f"""
    <section class="card">
      <p><a href="/">← Změnit obec</a></p>
      <h1>{escape(title)}</h1>
      <div class="alert"><strong>Výsledky nejsou právě dostupné.</strong>
        <p>{message}</p>
      </div>
      <p class="muted">Další pokus proběhne za {DEFAULT_POLL_INTERVAL_SECONDS} sekund.</p>
    </section>
    """
    return _page(title, body, refresh_code=code)


def _results_page(
    title: str, snapshot: ElectionSnapshot, tracking: sqlite3.Row
) -> HTMLResponse:
    processed = snapshot.progress.processed_districts
    total = snapshot.progress.total_districts
    progress = 100 * processed / total if total else 0
    turnout = _percent(snapshot.progress.turnout_percent)
    changed = snapshot.fetched_at.astimezone().strftime("%d. %m. %Y %H:%M:%S")
    checked = (
        _local_time(tracking["last_success_at"])
        if tracking["last_success_at"]
        else changed
    )
    status = (
        "Výsledky jsou úplné."
        if total > 0 and processed == total
        else "Výsledky se stále zpracovávají."
    )
    # Sloupec s obvodem má smysl jen u obcí rozdělených na více volebních obvodů.
    has_districts = len({party.constituency_id for party in snapshot.party_results}) > 1
    district_header = "<th>Volební obvod</th>" if has_districts else ""
    columns = 5 if has_districts else 4
    rows = "\n".join(
        "<tr>"
        + (f"<td>Obvod {escape(party.constituency_id)}</td>" if has_districts else "")
        + f"<td>{escape(party.name)}</td>"
        f'<td class="numeric">{_number(party.votes)}</td>'
        f'<td class="numeric">{_percent(party.percent)}</td>'
        f'<td class="numeric">{party.mandates_virtual if party.mandates_virtual is not None else "—"}</td>'
        "</tr>"
        for party in snapshot.party_results
    )
    if not rows:
        rows = (
            f'<tr><td colspan="{columns}">'
            "ČSÚ zatím nezveřejnil výsledky kandidátních listin.</td></tr>"
        )
    candidates_html = _candidates_html(snapshot, has_districts)
    if not snapshot.source_url.startswith("SIMULATION://"):
        simulation_snapshot = next(
            (
                item
                for item in reversed(
                    polling_service.repository.list_snapshots(snapshot.municipality.code)
                )
                if item.source_url.startswith("SIMULATION://")
            ),
            None,
        )
        if simulation_snapshot is not None:
            candidates_html += (
                "<h3>Hlasy kandidátů – testovací simulace</h3>"
                f'<p class="muted">Syntetický stav: '
                f'{simulation_snapshot.progress.processed_districts} / '
                f'{simulation_snapshot.progress.total_districts} okrsků. '
                "Tato čísla nejsou skutečné výsledky ČSÚ.</p>"
                + _candidates_html(simulation_snapshot, has_districts)
            )

    allocation_note = ""
    poll_error = tracking["last_error"]
    if poll_error:
        allocation_note += (
            '<p class="alert">Poslední aktualizace se nezdařila. Zobrazeny jsou '
            f"naposledy úspěšně stažené výsledky. Chyba: {escape(poll_error)}</p>"
        )
    if snapshot.allocation_error:
        allocation_note = (
            '<p class="alert">Virtuální mandáty se nepodařilo vypočítat: '
            f"{escape(snapshot.allocation_error)}</p>"
        )
    elif snapshot.lottery_required:
        allocation_note = (
            '<p class="alert">U některého mandátu rozhoduje los. Zobrazené rozdělení '
            "je pouze orientační náhled, nikoli výsledek losování.</p>"
        )
    elif snapshot.threshold_percent is not None:
        allocation_note = (
            f'<p class="muted">Použitá hranice pro postup: '
            f"{snapshot.threshold_percent} %.</p>"
        )

    presentation_link = ""
    generated_presentation = polling_service.repository.get_presentation(
        snapshot.municipality.code
    )
    if (
        processed == total
        and total > 0
        and generated_presentation is not None
        and Path(generated_presentation["file_path"]).is_file()
    ):
        presentation_link = (
            f'<a class="button" href="/prezentace/{snapshot.municipality.code}">'
            "Stáhnout prezentaci A4 (PDF)</a>"
        )

    body = f"""
    <section class="card">
      <p><a href="/">← Změnit obec</a></p>
      <h1>{escape(title)}</h1>
      <p class="muted">      {status} Poslední kontrola ČSÚ: {checked}.
                  Poslední změna dat (počtu okrsků): {changed}.
                  Aplikace kontroluje ČSÚ každých {DEFAULT_POLL_INTERVAL_SECONDS} sekund.</p>
      <div class="stats">
        <div class="stat">Zpracované okrsky<strong>{_number(processed)} / {_number(total)}</strong>
          <div class="bar" role="progressbar" aria-valuenow="{progress:.0f}"
            aria-valuemin="0" aria-valuemax="100" aria-label="Zpracování okrsků">
            <span style="width:{progress:.2f}%"></span>
          </div>
        </div>
        <div class="stat">Volební účast<strong>{turnout}</strong></div>
        <div class="stat">Počet volených zastupitelů<strong>{_number(snapshot.seats_to_elect)}</strong></div>
      </div>
      <h2>Výsledky kandidátních listin</h2>
      {allocation_note}
      <div class="table-wrap">
        <table>
          <thead><tr>{district_header}<th>Kandidátní listina</th>
            <th class="numeric">Hlasy</th><th class="numeric">Podíl</th>
            <th class="numeric">Virtuální mandáty</th></tr></thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
      <h2>Kandidáti</h2>
      {candidates_html}
      <p class="actions"><a class="button" href="/vysledky/{snapshot.municipality.code}/vyvoj">
        Vývoj výsledků a složení zastupitelstva →</a>{presentation_link}</p>
    </section>
    """
    return _page(title, body, refresh_code=snapshot.municipality.code)


def _load_candidates(code: str) -> tuple[list[Candidate], str | None]:
    try:
        return get_candidates(code), None
    except (requests.RequestException, RegistryError, OSError, ValueError) as exc:
        return [], str(exc)


_NO_CANDIDATE_VOTES = (
    "Hlasy jednotlivých kandidátů ČSÚ v průběžných výsledcích zatím neposkytuje; "
    "zobrazí se, jakmile budou ve zdroji."
)


def _candidates_html(
    snapshot: ElectionSnapshot,
    has_districts: bool,
    candidates: list[Candidate] | None = None,
) -> str:
    if candidates is None:
        candidates, error = _load_candidates(snapshot.municipality.code)
        if error:
            if snapshot.elected_representatives:
                return (
                    f'<p class="alert">Kandidáty se nepodařilo načíst: {escape(error)}</p>'
                    + _official_elected_html(snapshot, has_districts)
                )
            return f'<p class="alert">Kandidáty se nepodařilo načíst: {escape(error)}</p>'
    if not candidates:
        return '<p class="muted">Registr ČSÚ pro toto zastupitelstvo neobsahuje kandidáty.</p>'
    is_simulation = snapshot.source_url.startswith("SIMULATION://")
    simulation_groups = _candidate_groups(candidates) if is_simulation else []
    official_candidate_votes = {
        (
            representative.constituency_id,
            representative.list_id,
            representative.order,
        ): representative.votes
        for representative in snapshot.elected_representatives
    }
    note = (
        '<p class="muted">Hlasy kandidátů jsou v simulaci uměle rozděleny v rámci '
        "hlasů kandidátní listiny; nejde o skutečné ani odhadované výsledky.</p>"
        if is_simulation
        else (
            '<p class="muted">Hlasy zvolených zastupitelů jsou převzaty z oficiálního '
            "XML ČSÚ; u ostatních kandidátů nejsou v tomto zdroji uvedeny.</p>"
        )
        if snapshot.elected_representatives
        else f'<p class="muted">{_NO_CANDIDATE_VOTES}</p>'
        if all(candidate.votes is None for candidate in candidates)
        else ""
    )
    sections = []
    for party_index, party in enumerate(snapshot.party_results):
        party_candidates = candidates_for_party(party, candidates)
        if is_simulation and party_index < len(simulation_groups):
            party_candidates = _with_simulated_votes(
                simulation_groups[party_index], party.votes, party_index
            )
        if not party_candidates:
            continue
        prefix = f"Obvod {party.constituency_id} · " if has_districts else ""
        rows = ""
        for candidate in sorted(party_candidates, key=lambda item: item.order):
            official_votes = official_candidate_votes.get(
                (party.constituency_id, party.list_id, candidate.order)
            )
            votes = official_votes if official_votes is not None else candidate.votes
            rows += (
                "<tr>"
                f'<td class="numeric">{candidate.order}</td>'
                f"<td>{escape(candidate.name)}</td>"
                f'<td class="numeric">{candidate.age if candidate.age is not None else "—"}</td>'
                f"<td>{escape(candidate.occupation)}</td>"
                f"<td>{escape(candidate.residence)}</td>"
                f'<td class="numeric">{_number(votes) if votes is not None else "—"}</td>'
                "</tr>"
            )
        sections.append(
            f"<details><summary>{escape(prefix + party.name)} "
            f"({len(party_candidates)} kandidátů)</summary>"
            '<div class="table-wrap"><table><thead><tr>'
            '<th class="numeric">Pořadí</th><th>Jméno</th><th class="numeric">Věk</th>'
            "<th>Povolání</th><th>Bydliště</th>"
            '<th class="numeric">Hlasy</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></details>"
        )
    return note + "".join(sections)


def _official_elected_html(snapshot: ElectionSnapshot, has_districts: bool) -> str:
    if not snapshot.elected_representatives:
        return ""
    district_heading = "<th>Obvod</th>" if has_districts else ""
    rows = "".join(
        "<tr>"
        + (
            f"<td>Obvod {escape(representative.constituency_id)}</td>"
            if has_districts
            else ""
        )
        + f"<td>{escape(representative.name)}</td>"
        + f"<td>{escape(representative.party_name)}</td>"
        + f'<td class="numeric">{_number(representative.votes)}</td>'
        + "</tr>"
        for representative in snapshot.elected_representatives
    )
    return (
        '<h3>Zvolení zastupitelé a jejich hlasy z oficiálního XML ČSÚ</h3>'
        '<div class="table-wrap"><table><thead><tr>'
        f"{district_heading}<th>Jméno</th><th>Kandidátní listina</th>"
        '<th class="numeric">Hlasy</th></tr></thead>'
        f"<tbody>{rows}</tbody></table></div>"
    )


def _tracked_municipality_html(item: sqlite3.Row) -> str:
    snapshot = polling_service.repository.get_latest_snapshot(item["code"])
    if snapshot is None:
        progress = "Výsledky zatím nejsou dostupné."
    else:
        progress = (
            f'Okrsky: {snapshot.progress.processed_districts} / '
            f'{snapshot.progress.total_districts}'
        )
    code = escape(item["code"], quote=True)
    generated = polling_service.repository.get_presentation(item["code"])
    presentation_link = (
        f' · <a href="/prezentace/{code}">Stáhnout prezentaci A4 (PDF)</a>'
        if generated is not None and Path(generated["file_path"]).is_file()
        else ""
    )
    return (
        f'<li><span><a class="tracked-link" href="/vysledky/{code}">'
        f"<strong>{escape(_council_label(item))}</strong></a>"
        f'<br><span class="muted">{escape(item["district_name"])} · '
        f"{escape(item['region_name'])}</span>"
        f'<br><span class="muted">{escape(progress)} · '
        f"{escape(_tracking_label(item))}{presentation_link}</span></span>"
        f'<form action="/sledovani/{code}/odebrat" method="post">'
        '<button class="remove-button" type="submit">Přestat sledovat</button></form></li>'
    )


def _candidate_groups(candidates: list[Candidate]) -> list[list[Candidate]]:
    groups: dict[tuple[str, str], list[Candidate]] = {}
    for candidate in candidates:
        groups.setdefault((candidate.constituency_id, candidate.list_id), []).append(candidate)
    return [
        sorted(group, key=lambda candidate: candidate.order)
        for _, group in sorted(groups.items(), key=lambda item: (item[0][0], int(item[0][1])))
    ]


def _with_simulated_votes(
    candidates: list[Candidate], party_votes: int, party_index: int
) -> list[Candidate]:
    weights = [100 + ((candidate.order * 17 + party_index * 29) % 51) for candidate in candidates]
    total_weight = sum(weights)
    votes = [party_votes * weight // total_weight for weight in weights]
    votes[0] += party_votes - sum(votes)
    return [
        Candidate(
            constituency_id=candidate.constituency_id,
            list_id=candidate.list_id,
            order=candidate.order,
            name=candidate.name,
            age=candidate.age,
            occupation=candidate.occupation,
            residence=candidate.residence,
            votes=votes[index],
        )
        for index, candidate in enumerate(candidates)
    ]


def _valid_code(code: str) -> bool:
    return len(code) == 6 and code.isascii() and code.isdigit()


@app.get("/vysledky/{code}/vyvoj", response_class=HTMLResponse)
def development(code: str, okrsky: int | None = None) -> HTMLResponse:
    if not _valid_code(code):
        return RedirectResponse("/", status_code=303)
    tracking = polling_service.repository.get_tracking_status(code)
    if tracking is None:
        return RedirectResponse("/", status_code=303)
    snapshots = polling_service.repository.list_snapshots(code)
    if not snapshots:
        return RedirectResponse(f"/vysledky/{code}", status_code=303)

    by_processed: dict[int, ElectionSnapshot] = {}
    for item in snapshots:
        by_processed[item.progress.processed_districts] = item
    steps = sorted(by_processed)
    selected = okrsky if okrsky in by_processed else steps[-1]
    latest = by_processed[steps[-1]]
    total = latest.progress.total_districts
    title = _council_label(tracking)
    constituencies = sorted({party.constituency_id for party in latest.party_results}, key=int)
    has_districts = len(constituencies) > 1

    charts = []
    for constituency_id in constituencies:
        latest_parties = [
            party for party in latest.party_results if party.constituency_id == constituency_id
        ]
        percent_series = []
        mandate_series = []
        for party in latest_parties:
            percent_points = []
            mandate_points = []
            for step in steps:
                match = next(
                    (
                        item
                        for item in by_processed[step].party_results
                        if item.constituency_id == constituency_id
                        and item.list_id == party.list_id
                    ),
                    None,
                )
                if match is None:
                    continue
                percent_points.append((step, match.percent or 0.0))
                if match.mandates_virtual is not None:
                    mandate_points.append((step, float(match.mandates_virtual)))
            percent_series.append((party.name, percent_points))
            mandate_series.append((party.name, mandate_points))
        prefix = f"Obvod {constituency_id}: " if has_districts else ""
        mandate_max = max(
            (y for _, points in mandate_series for _, y in points),
            default=1.0,
        )
        has_mandates = any(points for _, points in mandate_series)
        names = [party.name for party in latest_parties]
        charts.append(
            f"<h3>{escape(prefix)}Podíl hlasů stran (%)</h3>"
            + line_chart_svg(
                percent_series, total, "Podíl hlasů (%)", label=f"{prefix}podíl hlasů stran"
            )
            + legend_html(names)
            + f"<h3>{escape(prefix)}Virtuální mandáty stran</h3>"
            + (
                line_chart_svg(
                    mandate_series,
                    total,
                    "Mandáty",
                    y_max=max(mandate_max, 1.0),
                    label=f"{prefix}virtuální mandáty stran",
                )
                if has_mandates
                else '<p class="muted">Mandáty se zatím nepočítají (čeká se na hlasy).</p>'
            )
        )

    candidates, candidate_error = _load_candidates(code)
    if candidate_error:
        composition_html = (
            f'<p class="alert">Kandidáty se nepodařilo načíst: {escape(candidate_error)}</p>'
        )
        candidate_results_html = ""
    else:
        composition_html = _composition_html(
            by_processed, steps, selected, candidates, has_districts, total, code
        )
        selected_snapshot = by_processed[selected]
        candidate_results_html = (
            "<h2>Hlasy jednotlivých kandidátů</h2>"
            + _candidates_html(selected_snapshot, has_districts, candidates)
            if selected_snapshot.source_url.startswith("SIMULATION://")
            else ""
        )

    body = f"""
    <section class="card">
      <p><a href="/vysledky/{code}">← Výsledky obce</a></p>
      <h1>{escape(title)} – vývoj výsledků</h1>
      <p class="muted">Osa x je počet zpracovaných okrsků (z {_number(total)}). Každý bod je
        uložený stav výsledků; ukládá se jen při změně počtu zpracovaných okrsků.</p>
      {"".join(charts)}
      <h2>Složení zastupitelstva jmenovitě</h2>
      {composition_html}
      {candidate_results_html}
    </section>
    """
    path = f"/vysledky/{code}/vyvoj" + (f"?okrsky={okrsky}" if okrsky is not None else "")
    return _page(f"{title} – vývoj", body, refresh_path=path)


def _composition_html(
    by_processed: dict[int, ElectionSnapshot],
    steps: list[int],
    selected: int,
    candidates: list[Candidate],
    has_districts: bool,
    total: int,
    code: str,
) -> str:
    seats = council_composition(by_processed[selected], candidates)
    options = "".join(
        f'<option value="{step}"{" selected" if step == selected else ""}>'
        f"{step} / {total} okrsků</option>"
        for step in steps
    )
    selector = (
        f'<form method="get" action="/vysledky/{code}/vyvoj" class="actions">'
        '<label for="step" style="margin:0">Stav po zpracování</label>'
        f'<select id="step" name="okrsky" style="width:auto">{options}</select>'
        "<button>Zobrazit</button></form>"
    )
    note = (
        '<p class="muted">Orientační složení podle § 45 odst. 3–5 zákona č. 491/2001 Sb.: '
        "mandáty stran se přidělují kandidátům v pořadí na hlasovacím lístku. "
        "Přeřazení podle hlasů kandidátů se použije, až je ČSÚ zveřejní.</p>"
    )
    if not seats:
        return (
            selector
            + note
            + '<p class="alert">Pro vybraný stav zatím nelze určit mandáty '
            "(čeká se na hlasy všech obvodů).</p>"
        )
    rows = "".join(
        "<tr>"
        + (f"<td>Obvod {escape(seat.constituency_id)}</td>" if has_districts else "")
        + f"<td>{escape(seat.party_name)}</td>"
        f'<td class="numeric">{seat.candidate.order}</td>'
        f"<td>{escape(seat.candidate.name)}</td>"
        "</tr>"
        for seat in seats
    )
    district_header = "<th>Obvod</th>" if has_districts else ""
    table = (
        '<div class="table-wrap"><table><thead><tr>'
        f'{district_header}<th>Kandidátní listina</th><th class="numeric">Pořadí</th>'
        f"<th>Zastupitel</th></tr></thead><tbody>{rows}</tbody></table></div>"
    )

    changes = []
    previous: set[tuple[str, str, int]] | None = None
    names: dict[tuple[str, str, int], str] = {}
    for step in steps:
        current_seats = council_composition(by_processed[step], candidates)
        current = set()
        for seat in current_seats:
            key = (seat.constituency_id, seat.candidate.list_id, seat.candidate.order)
            current.add(key)
            names[key] = (
                f"{seat.candidate.name} — {seat.party_name} "
                f"(pořadí {seat.candidate.order})"
            )
        if previous is not None and current != previous:
            for change_type, members in (
                ("Nový zastupitel", sorted(current - previous)),
                ("Vypadl", sorted(previous - current)),
            ):
                if members:
                    changes.extend(
                        f'<tr><td>{step} / {total}</td>'
                        f"<td>{change_type}</td><td>{escape(names[key])}</td></tr>"
                        for key in members
                    )
        previous = current
    history = (
        "<h3>Změny složení v čase</h3>"
        '<div class="table-wrap"><table><thead><tr><th>Okrsků</th><th>Změna</th>'
        f"<th>Zastupitel</th></tr></thead><tbody>{''.join(changes)}</tbody></table></div>"
        if changes
        else '<p class="muted">Složení se zatím v čase nezměnilo.</p>'
    )
    return selector + note + table + history


def _page(
    title: str,
    body: str,
    refresh_code: str | None = None,
    refresh_path: str | None = None,
) -> HTMLResponse:
    target = refresh_path or (f"/vysledky/{refresh_code}" if refresh_code else None)
    refresh = (
        f'<meta http-equiv="refresh" content="{DEFAULT_POLL_INTERVAL_SECONDS};'
        f'url={escape(target, quote=True)}">'
        if target
        else ""
    )
    footer = (
        "Zdroj výsledků: Český statistický úřad · stránka se obnovuje každých "
        f"{DEFAULT_POLL_INTERVAL_SECONDS} sekund."
        if target
        else "Seznam zastupitelstev je načítán z oficiálního číselníku Českého statistického úřadu."
    )
    document = f"""<!doctype html>
    <html lang="cs"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <meta name="robots" content="noindex">
      {refresh}<title>{escape(title)} | Volební přehled</title>{THEME_SCRIPT}{STYLES}
    </head><body>
      <header><a href="/"><strong>Volební přehled</strong></a>{THEME_TOGGLE}</header>
      <main>{body}</main>
      <footer>{footer}</footer>
    </body></html>"""
    return HTMLResponse(document, headers={"Cache-Control": "no-store"})


def _council_label(tracking: sqlite3.Row) -> str:
    council_name = tracking["council_name"]
    municipality_name = tracking["municipality_name"]
    if council_name.casefold() == municipality_name.casefold():
        return council_name
    return f"{council_name} — {municipality_name}"


def _tracking_label(tracking: sqlite3.Row) -> str:
    if tracking["last_error"]:
        return f"Chyba při poslední kontrole: {tracking['last_error']}"
    if tracking["last_success_at"]:
        return f"Naposledy aktualizováno: {_local_time(tracking['last_success_at'])}"
    return "Čeká se na první načtení výsledků"


def _local_time(value: str) -> str:
    from datetime import datetime

    return datetime.fromisoformat(value).astimezone().strftime("%d. %m. %Y %H:%M:%S")


def _number(value: int) -> str:
    return f"{value:,}".replace(",", "\u00a0")


def _percent(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f} %".replace(".", ",")
