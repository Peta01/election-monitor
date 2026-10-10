from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape as escape_xml

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .candidates import Candidate, get_candidates
from .composition import Seat, council_composition
from .models import ElectedRepresentative, ElectionSnapshot, PartyResult

PRESENTATION_FORMAT_VERSION = 4
_BLUE = colors.HexColor("#123b69")
_LIGHT_BLUE = colors.HexColor("#eaf1f8")
_TEXT = colors.HexColor("#172b4d")
_MUTED = colors.HexColor("#52657b")


def generate_election_presentation(snapshot: ElectionSnapshot, output_path: Path) -> None:
    """Create a printable, A4-sized PDF summary for one completed municipality."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    regular_font, bold_font = _register_fonts()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "PresentationTitle",
        parent=styles["Title"],
        fontName=bold_font,
        fontSize=22,
        leading=27,
        textColor=_BLUE,
        alignment=TA_LEFT,
        spaceAfter=5,
    )
    subtitle_style = ParagraphStyle(
        "PresentationSubtitle",
        parent=styles["Normal"],
        fontName=regular_font,
        fontSize=10,
        leading=14,
        textColor=_MUTED,
    )
    heading_style = ParagraphStyle(
        "PresentationHeading",
        parent=styles["Heading2"],
        fontName=bold_font,
        fontSize=14,
        leading=18,
        textColor=_BLUE,
        spaceBefore=14,
        spaceAfter=7,
    )
    cell_style = ParagraphStyle(
        "PresentationCell",
        parent=styles["BodyText"],
        fontName=regular_font,
        fontSize=8.5,
        leading=11,
        textColor=_TEXT,
    )
    header_style = ParagraphStyle(
        "PresentationHeader",
        parent=cell_style,
        fontName=bold_font,
        textColor=colors.white,
    )
    note_style = ParagraphStyle(
        "PresentationNote",
        parent=subtitle_style,
        fontSize=8,
        leading=11,
    )
    elected_style = ParagraphStyle(
        "ElectedRepresentative",
        parent=cell_style,
        fontSize=9,
        leading=12,
    )

    fetched_at = snapshot.fetched_at.astimezone().strftime("%d. %m. %Y %H:%M")
    story = [
        Paragraph("Výsledky voleb do zastupitelstva", title_style),
        Paragraph(
            f"{escape_xml(snapshot.municipality.name)} · stav k {fetched_at} · "
            "zdroj: Český statistický úřad",
            subtitle_style,
        ),
        Spacer(1, 0.55 * cm),
    ]
    turnout = (
        f"{snapshot.progress.turnout_percent:.2f} %".replace(".", ",")
        if snapshot.progress.turnout_percent is not None
        else "—"
    )
    stats = Table(
        [
            [
                _stat_cell(
                    "Zpracované okrsky",
                    f"{snapshot.progress.processed_districts} / "
                    f"{snapshot.progress.total_districts} (100 %)",
                    regular_font,
                    bold_font,
                ),
                _stat_cell("Volební účast", turnout, regular_font, bold_font),
                _stat_cell(
                    "Volených zastupitelů",
                    str(snapshot.seats_to_elect),
                    regular_font,
                    bold_font,
                ),
            ]
        ],
        colWidths=[6 * cm] * 3,
    )
    stats.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_BLUE),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#dce3eb")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ]
        )
    )
    story.extend([stats, Paragraph("Výsledky kandidátních listin", heading_style)])

    has_districts = len({party.constituency_id for party in snapshot.party_results}) > 1
    headings = (
        ["Obvod", "Kandidátní listina", "Hlasy", "Podíl", "Mandáty"]
        if has_districts
        else ["Kandidátní listina", "Hlasy", "Podíl", "Mandáty"]
    )
    data = [[Paragraph(label, header_style) for label in headings]]
    sorted_parties = sorted(
        snapshot.party_results,
        key=lambda party: (
            party.constituency_id,
            -party.votes,
            (0, int(party.list_id))
            if party.list_id.isdigit()
            else (1, party.list_id),
        ),
    )
    for party in sorted_parties:
        row = _party_row(party, has_districts, cell_style)
        data.append(row)
    if not sorted_parties:
        empty = Paragraph("ČSÚ nezveřejnil žádné výsledky kandidátních listin.", cell_style)
        data.append(([Paragraph("—", cell_style), empty] if has_districts else [empty]) + ["", "", ""])

    widths = [2 * cm, 7 * cm, 3 * cm, 3 * cm, 3 * cm] if has_districts else [
        9 * cm,
        3 * cm,
        3 * cm,
        3 * cm,
    ]
    results = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    results.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_BLUE]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 0), (-1, 0), 1, _BLUE),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#dce3eb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(results)

    if snapshot.elected_representatives:
        elected = snapshot.elected_representatives
    else:
        elected = _elected_representatives(
            snapshot, get_candidates(snapshot.municipality.code)
        )
    story.append(Paragraph("Zvolení zastupitelé", heading_style))
    elected_headings = (
        ["Obvod", "Zastupitel", "Kandidátní listina", "Hlasy kandidáta"]
        if has_districts
        else ["Zastupitel", "Kandidátní listina", "Hlasy kandidáta"]
    )
    elected_data = [
        [Paragraph(label, header_style) for label in elected_headings]
    ]
    for seat in elected:
        if isinstance(seat, ElectedRepresentative):
            name = seat.name
            party_name = seat.party_name
            votes = seat.votes
            constituency_id = seat.constituency_id
        else:
            name = seat.candidate.name
            party_name = seat.party_name
            votes = seat.candidate.votes
            constituency_id = seat.constituency_id
        row = [
            Paragraph(escape_xml(name), elected_style),
            Paragraph(escape_xml(party_name), elected_style),
            f"{votes:,}".replace(",", "\u00a0"),
        ]
        if has_districts:
            row.insert(0, Paragraph(f"Obvod {constituency_id}", elected_style))
        elected_data.append(row)
    if not elected:
        elected_data.append(
            [Paragraph("ČSÚ zatím nezveřejnil údaje potřebné pro určení zastupitelů.", elected_style)]
            + [""] * (len(elected_headings) - 1)
        )
    elected_widths = [1.8 * cm, 8.4 * cm, 4.3 * cm, 3.5 * cm] if has_districts else [
        9.2 * cm,
        5.0 * cm,
        3.8 * cm,
    ]
    elected_table = Table(elected_data, colWidths=elected_widths, repeatRows=1, hAlign="LEFT")
    elected_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _BLUE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_BLUE]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#dce3eb")),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(elected_table)
    notes = []
    if snapshot.elected_representatives:
        notes.append("Jména a hlasy zvolených zastupitelů jsou převzaty z oficiálního XML ČSÚ.")
    elif elected:
        notes.append(
            "Složení vychází z výpočtu mandátů aplikace a pořadí kandidátů; "
            "při losu je pouze orientační."
        )
        if any(seat.candidate.votes is None for seat in elected):
            notes.append(
                "Hlasy kandidátů nejsou v dostupných datech ČSÚ; pomlčka neznamená nula hlasů."
            )
    if snapshot.lottery_required:
        notes.append(
            "U některého mandátu rozhoduje los; virtuální rozdělení je pouze orientační."
        )
    if snapshot.allocation_error:
        notes.append(
            "Virtuální mandáty se nepodařilo vypočítat: "
            f"{escape_xml(snapshot.allocation_error)}"
        )
    elif snapshot.threshold_percent is not None:
        notes.append(f"Použitá hranice pro postup: {snapshot.threshold_percent} %.")
    if notes:
        story.extend(
            [
                Spacer(1, 0.3 * cm),
                Paragraph("<br/>".join(notes), note_style),
            ]
        )
    story.extend(
        [
            Spacer(1, 0.35 * cm),
            Paragraph(f"Zdroj dat: {escape_xml(snapshot.source_url)}", note_style),
        ]
    )
    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.3 * cm,
        bottomMargin=1.3 * cm,
        title=f"Výsledky voleb – {snapshot.municipality.name}",
        author="Volební přehled",
    )
    document.build(story)


def _elected_representatives(
    snapshot: ElectionSnapshot, candidates: list[Candidate]
) -> list[Seat]:
    return council_composition(snapshot, candidates)


def _party_row(
    party: PartyResult, has_districts: bool, style: ParagraphStyle
) -> list[Paragraph | str]:
    percent = f"{party.percent:.2f} %".replace(".", ",") if party.percent is not None else "—"
    values = [
        Paragraph(escape_xml(party.name), style),
        Paragraph(f"{party.votes:,}".replace(",", "\u00a0"), style),
        Paragraph(percent, style),
        Paragraph(
            str(party.mandates_virtual) if party.mandates_virtual is not None else "—",
            style,
        ),
    ]
    if has_districts:
        values.insert(0, Paragraph(f"Obvod {party.constituency_id}", style))
    return values


def _stat_cell(label: str, value: str, regular_font: str, bold_font: str) -> Table:
    label_style = ParagraphStyle(
        "StatLabel", fontName=regular_font, fontSize=8, textColor=_MUTED
    )
    value_style = ParagraphStyle(
        "StatValue", fontName=bold_font, fontSize=15, leading=19, textColor=_BLUE
    )
    return Table(
        [[Paragraph(label, label_style)], [Paragraph(value, value_style)]],
        colWidths=[5.2 * cm],
        style=TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0)]),
    )


def _register_fonts() -> tuple[str, str]:
    regular_name = "ElectionSans"
    bold_name = "ElectionSansBold"
    regular_path, bold_path = _font_paths()
    pdfmetrics.registerFont(TTFont(regular_name, str(regular_path)))
    pdfmetrics.registerFont(TTFont(bold_name, str(bold_path or regular_path)))
    return regular_name, bold_name


def _font_paths() -> tuple[Path, Path | None]:
    candidates = [
        (
            Path(r"C:\Windows\Fonts\arial.ttf"),
            Path(r"C:\Windows\Fonts\arialbd.ttf"),
        ),
        (
            Path(r"C:\Windows\Fonts\segoeui.ttf"),
            Path(r"C:\Windows\Fonts\segoeuib.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
            Path("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ),
        (
            Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
            Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        ),
    ]
    for regular, bold in candidates:
        if regular.is_file():
            return regular, bold if bold.is_file() else None
    raise RuntimeError("A Unicode TrueType font is required to generate election PDFs.")
