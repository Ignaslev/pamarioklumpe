"""Printable A4 daily purchase report using the same totals as the web page."""
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


FONT = "PurchaseDejaVu"
INK = colors.HexColor("#181818")
MUTED = colors.HexColor("#626262")
LINE = colors.HexColor("#d5d5d5")
GOLD = colors.HexColor("#f9edca")
PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 15 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN


def money(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f").replace(".", ",") + " €"


def quantity(value):
    if value is None:
        return "-"
    return format(value, ".3f").rstrip("0").rstrip(".").replace(".", ",")


def build_daily_purchase_pdf(context):
    # Bundle the font with the repository so Linux and Windows render alike.
    if FONT not in pdfmetrics.getRegisteredFontNames():
        font_path = Path(__file__).resolve().parent / "assets" / "fonts" / "DejaVuSans.ttf"
        pdfmetrics.registerFont(TTFont(FONT, str(font_path)))

    body = ParagraphStyle("purchase-body", fontName=FONT, fontSize=8.1, leading=10.5, textColor=INK)
    small = ParagraphStyle("purchase-small", parent=body, fontSize=7, leading=9, textColor=MUTED)
    heading = ParagraphStyle("purchase-heading", parent=body, fontSize=11, leading=14,
                             spaceBefore=7, spaceAfter=4, keepWithNext=True)
    title = ParagraphStyle("purchase-title", parent=body, fontSize=19, leading=23, spaceAfter=5)
    subtitle = ParagraphStyle("purchase-subtitle", parent=body, fontSize=10, leading=14, spaceAfter=9)
    number = ParagraphStyle("purchase-number", parent=body, alignment=TA_RIGHT)

    def text(value, style=body):
        return Paragraph(escape(str(value)), style)

    def table(rows, widths, total_row=True):
        result = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
        commands = [
            ("FONTNAME", (0, 0), (-1, -1), FONT),
            ("FONTSIZE", (0, 0), (-1, -1), 8.1),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 7),
            ("RIGHTPADDING", (0, 0), (-1, -1), 7),
            ("TOPPADDING", (0, 0), (-1, -1), 2.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ("BACKGROUND", (0, 0), (-1, 0), GOLD),
            ("LINEBELOW", (0, 0), (-1, 0), .65, INK),
            ("LINEBELOW", (0, 1), (-1, -1), .25, LINE),
        ]
        if total_row:
            commands.extend([
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f3f3f3")),
                ("LINEABOVE", (0, -1), (-1, -1), .5, INK),
                ("NOSPLIT", (0, -2), (-1, -1)),
            ])
        result.setStyle(TableStyle(commands))
        return result

    day = context["selected_date"].isoformat()
    output = BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=12 * mm, bottomMargin=15 * mm,
        title=f"Prekių pirkimas - {day}", author="Pamario Klumpė",
    )
    story = [text("PAMARIO KLUMPĖ", small), Spacer(1, 4),
             text("Prekių pirkimas", title), text(f"Dienos ataskaita | {day}", subtitle)]
    widths = [CONTENT_WIDTH - 72 * mm, 18 * mm, 12 * mm, 23 * mm, 19 * mm]
    for group in context["purchase_groups"]:
        story.append(text(group["name"], heading))
        rows = [[text("Prekė"), text("Kiekis", number), text("Vnt."),
                 text("Vid. kaina", number), text("Suma", number)]]
        for product in group["products"]:
            rows.append([
                text(product["name"]), text(quantity(product["quantity"]), number),
                text(product["unit"] or "-"),
                text(money(product["average_price"]) if product["average_price"] is not None else "-", number),
                text(money(product["total"]), number),
            ])
        if not group["products"]:
            rows.append([text("Pirkimų nėra.", small), "", "", "", ""])
        rows.append([text("Kategorijos suma"), "", "", "", text(money(group["total"]), number)])
        story.append(table(rows, widths))

    story.append(text("Išlaidos parduotuvėse", heading))
    rows = [[text("Parduotuvė"), text("Sumokėta", number)]]
    rows.extend([[text(store["name"]), text(money(store["total"]), number)] for store in context["store_totals"]])
    rows.append([text("IŠ VISO SUMOKĖTA"), text(money(context["grand_total"]), number)])
    story.append(table(rows, [CONTENT_WIDTH - 38 * mm, 38 * mm]))
    story.extend([
        Spacer(1, 7),
        text(f"Prekių suma po nuolaidų: {money(context['goods_total'])}. "
             f"Mokėjimo korekcijos: {money(context['payment_adjustments'])}.", small),
        text("Korekcijos apima grynųjų apvalinimą ir lojalumo pinigų panaudojimą. "
             "Vidutinė kaina apskaičiuota po nuolaidų. Visos sumos su PVM, kai jis taikomas. "
             "Brūkšnys reiškia, kad kiekis arba kaina čekyje nenurodyti.", small),
    ])

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 11 * mm, PAGE_WIDTH - MARGIN, 11 * mm)
        canvas.setFont(FONT, 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 7 * mm, f"Pamario Klumpė | {day}")
        canvas.drawRightString(PAGE_WIDTH - MARGIN, 7 * mm, f"Lapas {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    output.seek(0)
    return output
