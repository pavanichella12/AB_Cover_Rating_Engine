"""
Generate a PDF of the Final Calculation Results for download/save.
"""

from io import BytesIO
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak


def _style():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", fontSize=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="Body", fontSize=10, spaceAfter=4))
    return styles


def build_results_pdf(results: dict, rating_inputs: dict) -> bytes:
    """
    Build a PDF of the final calculation results.
    Returns PDF as bytes for st.download_button.
    """
    buf = BytesIO()
    # Landscape so the wide "Calculation Breakdown by School Year" table fits without being cut off
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter), rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=inch, bottomMargin=inch)
    styles = _style()
    story = []

    # Title and date
    story.append(Paragraph("ABCover – Final Calculation Results", styles["Title"]))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles["Body"]))
    story.append(Spacer(1, 0.3 * inch))

    # Input parameters
    deductible = results.get("deductible", rating_inputs.get("deductible", 20))
    cc_days = results.get("cc_days", rating_inputs.get("cc_days", 60))
    cc_maximum = results.get("cc_maximum", deductible + cc_days)
    replacement_cost = results.get("replacement_cost", rating_inputs.get("replacement_cost", 150.0))
    school_year_days = results.get("school_year_days") or rating_inputs.get("school_year_days") or 180
    ark_rate = rating_inputs.get("ark_commission_rate", 0.15)
    abcover_rate = rating_inputs.get("abcover_commission_rate", 0.15)

    story.append(Paragraph("Input parameters", styles["Heading2"]))
    params = [
        ["Deductible (Days)", str(deductible)],
        ["CC Days per Teacher", str(cc_days)],
        ["CC Maximum", str(cc_maximum)],
        ["Replacement Cost per Day", f"${replacement_cost:.2f}"],
        ["School Year Days", str(school_year_days)],
        ["Carrier Profit Margin", f"{ark_rate * 100:.1f}%"],
        ["ABCover Acquisition Costs", f"{abcover_rate * 100:.1f}%"],
    ]
    t = Table(params, colWidths=[2.5 * inch, 2 * inch])
    t.setStyle(TableStyle([("FONTNAME", (0, 0), (-1, -1), "Helvetica"), ("FONTSIZE", (0, 0), (-1, -1), 10)]))
    story.append(t)
    story.append(Spacer(1, 0.25 * inch))

    # Per-school-year metrics (if present)
    if results.get("per_school_year_metrics"):
        story.append(Paragraph("School Year Metrics (From Cleaned Data)", styles["Heading2"]))
        psm = results["per_school_year_metrics"]
        headers = ["School Year", "Total Staff", "Total Absences", "Total Replacement Cost ($)"]
        rows = [headers]
        for sy in sorted(psm.keys()):
            m = psm[sy]
            rows.append([str(sy), str(m["total_staff"]), f"{m['total_absences']:,.2f}", f"{m['total_replacement_cost']:,.2f}"])
        t = Table(rows, colWidths=[1.2 * inch, 1 * inch, 1.2 * inch, 1.8 * inch])
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.2 * inch))
        overall = f"Overall: {results.get('overall_total_staff', 0):,} staff, {results.get('overall_total_absences', 0):,.2f} absences, ${results.get('overall_total_replacement_cost', 0):,.2f} total replacement cost"
        story.append(Paragraph(overall, styles["Body"]))
        story.append(Spacer(1, 0.25 * inch))

    # Calculation breakdown by school year (if present)
    if results.get("per_school_year_breakdown"):
        story.append(Paragraph("Calculation Breakdown by School Year", styles["Heading2"]))
        breakdown = results["per_school_year_breakdown"]
        headers = ["School Year", "Teachers", "Below Ded.", "In CC", "High", "CC Days", "Excess", "Repl. Cost ($)", "Carrier ($)", "ABCover ($)", "Premium ($)"]
        rows = [headers]
        for sy in sorted(breakdown.keys()):
            b = breakdown[sy]
            rows.append([
                str(sy),
                str(b["total_teachers"]),
                str(b["below_deductible"]),
                str(b["in_cc_range"]),
                str(b["high_claimant"]),
                f"{b['total_cc_days']:,.1f}",
                f"{b['excess_days']:,.1f}",
                f"{b.get('replacement_cost_cc', 0):,.2f}",
                f"{b.get('ark_commission', 0):,.2f}",
                f"{b.get('abcover_commission', 0):,.2f}",
                f"{b['premium']:,.2f}",
            ])
        # Landscape page width 11" - 1.5" margins = 9.5"; 11 cols -> ~0.86" each so table fits
        avail_width = 11 * inch - 1.5 * inch
        col_widths = [avail_width / 11] * 11
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.25 * inch))

    # Coverage metrics
    story.append(Paragraph("Coverage Metrics", styles["Heading2"]))
    story.append(Paragraph(
        f"Staff in CC Range: {results.get('num_staff_cc_range', 0):,}  |  "
        f"Total CC Days: {results.get('total_cc_days', 0):,.2f}  |  "
        f"Replacement Cost × CC Days: ${results.get('replacement_cost_cc', 0):,.2f}",
        styles["Body"]
    ))
    story.append(Spacer(1, 0.15 * inch))

    # High claimant metrics
    story.append(Paragraph("High Claimant Metrics", styles["Heading2"]))
    story.append(Paragraph(
        f"High Claimant Staff: {results.get('num_high_claimant', 0):,}  |  "
        f"Excess Days: {results.get('excess_days', 0):,.2f}  |  "
        f"High Claimant Cost: ${results.get('high_claimant_cost', 0):,.2f}",
        styles["Body"]
    ))
    story.append(Spacer(1, 0.25 * inch))

    # Premium calculation
    story.append(Paragraph("Premium Calculation", styles["Heading2"]))
    rc_cc = results.get("replacement_cost_cc", 0)
    ark = results.get("ark_commission", 0)
    abcover = results.get("abcover_commission", 0)
    total = results.get("total_premium", 0)
    premium_rows = [
        ["Replacement Cost (CC)", f"${rc_cc:,.2f}"],
        ["Carrier Profit Margin", f"${ark:,.2f}"],
        ["ABCover Acquisition Costs", f"${abcover:,.2f}"],
        ["TOTAL PREMIUM", f"${total:,.2f}"],
    ]
    t = Table(premium_rows, colWidths=[2.5 * inch, 1.5 * inch])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
    ]))
    story.append(t)

    doc.build(story)
    buf.seek(0)
    return buf.read()
