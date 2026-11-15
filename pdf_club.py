import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def creer_bandeau_en_tete(club_nom, equipe_nom, styles):
    """Crée un bandeau professionnel moderne avec le club, l'équipe et le logo."""
    logo_path = "logo_club.png"
    
    style_club = ParagraphStyle(
        'BandeauClub', parent=styles['Normal'], 
        fontName='Helvetica-Bold', fontSize=13, leading=15, textColor=colors.white
    )
    style_team = ParagraphStyle(
        'BandeauTeam', parent=styles['Normal'], 
        fontName='Helvetica-Bold', fontSize=9, leading=12, textColor=colors.HexColor("#38bdf8")
    )
    
    text_content = [
        Paragraph(club_nom.upper(), style_club),
        Spacer(1, 2),
        Paragraph(f"Équipe : {equipe_nom}", style_team)
    ]
    
    if os.path.exists(logo_path):
        try:
            img = Image(logo_path, width=42, height=42)
            img.hAlign = 'RIGHT'
            cell_right = img
        except Exception:
            cell_right = Paragraph("<b>CLUB</b>", ParagraphStyle('BandeauRight', parent=styles['Normal'], alignment=TA_RIGHT, fontSize=8, textColor=colors.white))
    else:
        cell_right = Paragraph("", styles['Normal'])

    bandeau_table = Table([[text_content, cell_right]], colWidths=[430, 115])
    bandeau_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#0B2545")),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 12),
        ('RIGHTPADDING', (0,0), (-1,-1), 12),
    ]))
    return bandeau_table

def generer_pdf_bilan_global(club_nom, synthese_data, total_matchs, total_victoires, pct_global):
    """Génère un rapport PDF complet de Bilan Global de Saison (PDF Club) pour la Direction / Président."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25, leftMargin=25,
        topMargin=25, bottomMargin=25
    )
    
    styles = getSampleStyleSheet()
    ffh_blue = colors.HexColor("#0B2545")
    ffh_red = colors.HexColor("#D90429")
    bg_light = colors.HexColor("#F4F6F8")
    border_color = colors.HexColor("#8D99AE")
    
    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=16, leading=20, textColor=ffh_blue, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=ffh_red, alignment=TA_CENTER)
    h1_style = ParagraphStyle('SectionH1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, textColor=ffh_blue, spaceAfter=6, spaceBefore=8)
    cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=11, textColor=colors.HexColor("#111827"), alignment=TA_CENTER)
    cell_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=11, textColor=colors.white, alignment=TA_CENTER)

    story = []
    
    # Bandeau Direction
    story.append(creer_bandeau_en_tete(club_nom, "Direction & Présidence", styles))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("RAPPORT INSTITUTIONNEL — BILAN DE SAISON GLOBAL", title_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Synthèse consolidée des performances de l'ensemble des équipes du club", subtitle_style))
    story.append(Spacer(1, 15))
    
    # Bloc Métriques Globales
    metriques_data = [
        [Paragraph("<b>Équipes Actives</b>", cell_header_style), Paragraph("<b>Matchs Joués</b>", cell_header_style), Paragraph("<b>Total Victoires</b>", cell_header_style), Paragraph("<b>Taux de Victoire Global</b>", cell_header_style)],
        [
            Paragraph(str(len(synthese_data)), cell_style),
            Paragraph(str(total_matchs), cell_style),
            Paragraph(str(total_victoires), cell_style),
            Paragraph(f"<b>{pct_global}%</b>", cell_style)
        ]
    ]
    t_metriques = Table(metriques_data, colWidths=[130, 135, 135, 145])
    t_metriques.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ffh_blue),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_metriques)
    story.append(Spacer(1, 20))
    
    # Tableau détaillé par équipe
    story.append(Paragraph("Détail par Équipe", h1_style))
    headers = ["Équipe", "Matchs Joués", "Victoires", "% Victoires", "Moy. Buts / Match"]
    table_data = [[Paragraph(h, cell_header_style) for h in headers]]
    
    for row in synthese_data:
        table_data.append([
            Paragraph(str(row.get("Équipe", "")), ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
            Paragraph(str(row.get("Matchs Joués", 0)), cell_style),
            Paragraph(str(row.get("Victoires", 0)), cell_style),
            Paragraph(str(row.get("% Victoires", "0%")), cell_style),
            Paragraph(str(row.get("Moy. Buts / Match", 0.0)), cell_style),
        ])
        
    t_detail = Table(table_data, colWidths=[145, 100, 100, 100, 100])
    t_detail.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ffh_red),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_detail)
    
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()