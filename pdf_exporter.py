import os
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

def generer_pdf_match(nom_match, score_eq, score_adv, lignes_champ, lignes_gardiennes, attaques_adversaires=None):
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
    
    header_org = ParagraphStyle('HeaderOrg', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, textColor=ffh_blue, alignment=TA_CENTER)
    title_style = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=ffh_blue, alignment=TA_CENTER)
    subtitle_style = ParagraphStyle('DocSubtitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=ffh_red, alignment=TA_CENTER)
    h1_style = ParagraphStyle('SectionH1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=13, textColor=ffh_blue, spaceAfter=4, spaceBefore=6)
    cell_style = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8, leading=10, textColor=colors.HexColor("#111827"), alignment=TA_CENTER)
    cell_header_style = ParagraphStyle('TableHeader', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white, alignment=TA_CENTER)

    story = []

    # =========================================================================
    # PAGE 1 : VRAIE FEUILLE DE MATCH OFFICIELLE FFHANDBALL (Administrative)
    # =========================================================================
    story.append(Paragraph("FÉDÉRATION FRANÇAISE DE HANDBALL — CHAMPIONNAT D2F", header_org))
    story.append(Spacer(1, 4))
    story.append(Paragraph("FEUILLE DE MATCH OFFICIELLE", title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(nom_match, subtitle_style))
    story.append(Spacer(1, 10))
    
    # En-tête Scoreboard officiel
    res_text = "VICTOIRE" if score_eq > score_adv else ("DÉFAITE" if score_eq < score_adv else "MATCH NUL")
    res_color = "#10b981" if score_eq > score_adv else ("#ef4444" if score_eq < score_adv else "#f59e0b")
    
    score_data = [
        [Paragraph(f"<font color='{res_color}'><b>{res_text}</b></font>", ParagraphStyle('Res', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER))],
        [Paragraph(f"<b>{score_eq} - {score_adv}</b>", ParagraphStyle('Sc', parent=styles['Normal'], fontSize=26, leading=30, fontName='Helvetica-Bold', alignment=TA_CENTER))]
    ]
    t_score = Table(score_data, colWidths=[545])
    t_score.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_light),
        ('BOX', (0,0), (-1,-1), 1.5, ffh_blue),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_score)
    story.append(Spacer(1, 15))
    
    # Composition officielle - Joueuses de Champ
    story.append(Paragraph("COMPOSITION DE L'ÉQUIPE — JOUEUSES DE CHAMP", h1_style))
    headers_ffh_c = ["N°", "Nom de la Joueuse", "Poste", "Buts", "Avert. (Jaune)", "Exclusions (2min)"]
    table_data_ffh_c = [[Paragraph(h, cell_header_style) for h in headers_ffh_c]]
    
    for row in lignes_champ:
        table_data_ffh_c.append([
            Paragraph(str(row.get("N°", "")), cell_style),
            Paragraph(str(row.get("Joueuse", "")), ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
            Paragraph(str(row.get("Poste", "")), cell_style),
            Paragraph(str(row.get("Buts", 0)), cell_style),
            Paragraph(str(row.get("🟨", 0)), cell_style),
            Paragraph(str(row.get("⏱️ 2min", 0)), cell_style),
        ])
    
    t_ffh_champ = Table(table_data_ffh_c, colWidths=[35, 210, 140, 50, 55, 55])
    t_ffh_champ.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ffh_blue),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_ffh_champ)
    story.append(Spacer(1, 12))
    
    # Composition officielle - Gardiennes
    if lignes_gardiennes:
        story.append(Paragraph("COMPOSITION DE L'ÉQUIPE — GARDIENNES", h1_style))
        headers_ffh_g = ["N°", "Nom de la Gardienne", "Arrêts", "Tirs Subis", "% Arrêts", "Buts Encaissés", "Avert.", "2min"]
        table_data_ffh_g = [[Paragraph(h, cell_header_style) for h in headers_ffh_g]]
        for row in lignes_gardiennes:
            table_data_ffh_g.append([
                Paragraph(str(row.get("N°", "")), cell_style),
                Paragraph(str(row.get("Gardienne", "")), ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
                Paragraph(str(row.get("Arrêts", 0)), cell_style),
                Paragraph(str(row.get("Tirs Subis", 0)), cell_style),
                Paragraph(str(row.get("% Arrêts", "0%")), cell_style),
                Paragraph(str(row.get("Buts Encaissés", 0)), cell_style),
                Paragraph(str(row.get("🟨", 0)), cell_style),
                Paragraph(str(row.get("⏱️ 2min", 0)), cell_style),
            ])
        t_ffh_gard = Table(table_data_ffh_g, colWidths=[35, 215, 60, 65, 60, 65, 22, 23])
        t_ffh_gard.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), ffh_red),
            ('GRID', (0,0), (-1,-1), 0.5, border_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(t_ffh_gard)

    # =========================================================================
    # PAGE 2 : BILAN COLLECTIF AVANCÉ & ANALYSE TACTIQUE ADVERSE
    # =========================================================================
    story.append(PageBreak())
    story.append(Paragraph("RAPPORT ANALYTIQUE & COLLECTIF", subtitle_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("Bilan Statistique & Tactique — " + nom_match, title_style))
    story.append(Spacer(1, 15))
    
    story.append(Paragraph("Bilan Collectif Avancé — Joueuses de Champ", h1_style))
    headers_c = ["N°", "Joueuse", "Poste", "Buts/Tirs", "Réussite", "PD", "Pertes (P/F)", "Duels Off", "Duels Déf", "Int", "Neut", "Prov"]
    table_data_c = [[Paragraph(h, cell_header_style) for h in headers_c]]
    
    for row in lignes_champ:
        table_data_c.append([
            Paragraph(str(row.get("N°", "")), cell_style),
            Paragraph(str(row.get("Joueuse", "")), ParagraphStyle('L', parent=cell_style, alignment=TA_LEFT)),
            Paragraph(str(row.get("Poste", "")), cell_style),
            Paragraph(f"{row.get('Buts', 0)}/{row.get('Tirs', 0)}", cell_style),
            Paragraph(str(row.get("Réussite", "0%")), cell_style),
            Paragraph(str(row.get("Passes D.", 0)), cell_style),
            f"{row.get('Perte (Passe', 0) if 'Perte (Passe' in row else row.get('Perte (Passe)', 0)}/{row.get('Perte (Faute', 0) if 'Perte (Faute' in row else row.get('Perte (Faute)', 0)}",
            Paragraph(str(row.get("Duels Off", "0/0")), cell_style),
            Paragraph(str(row.get("Duels Déf", "0/0")), cell_style),
            Paragraph(str(row.get("Interceptions", 0)), cell_style),
            Paragraph(str(row.get("Neutralisations", 0)), cell_style),
            Paragraph(str(row.get("Provoquées", 0)), cell_style),
        ])
    
    t_champ = Table(table_data_c, colWidths=[20, 100, 75, 45, 50, 25, 50, 45, 45, 25, 30, 25])
    t_champ.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), ffh_blue),
        ('GRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, bg_light]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
    ]))
    story.append(t_champ)
    
    if attaques_adversaires:
        story.append(Spacer(1, 15))
        story.append(Paragraph("Analyse Tactique — Attaques Adverses (Yago, Yego...)", h1_style))
        att_data = [[Paragraph("Système d'Attaque Adverse", cell_header_style), Paragraph("Nombre d'Utilisations", cell_header_style)]]
        for sys_nom, count in attaques_adversaires.items():
            att_data.append([Paragraph(sys_nom, cell_style), Paragraph(str(count), cell_style)])
        t_att = Table(att_data, colWidths=[270, 275])
        t_att.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), ffh_red),
            ('GRID', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4)
        ]))
        story.append(t_att)

    # =========================================================================
    # PAGES SUIVANTES : FICHES INDIVIDUELLES DÉTAILLÉES PAR JOUEUSE
    # =========================================================================
    for row in lignes_champ:
        story.append(PageBreak())
        story.append(Paragraph("FICHE INDIVIDUELLE JOUEUSE", subtitle_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"#{row.get('N°')} — {row.get('Joueuse')} <i>({row.get('Poste')})</i>", title_style))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("Performances Offensives", h1_style))
        atk_summary = [
            [Paragraph("<b>Buts / Tirs</b>", cell_header_style), Paragraph("<b>Efficacité Tirs</b>", cell_header_style), Paragraph("<b>Passes Décisives</b>", cell_header_style)],
            [Paragraph(f"{row.get('Buts', 0)} / {row.get('Tirs', 0)}", cell_style), Paragraph(str(row.get('Réussite', '0%')), cell_style), Paragraph(str(row.get('Passes D.', 0)), cell_style)]
        ]
        t_atk1 = Table(atk_summary, colWidths=[181, 182, 182])
        t_atk1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ffh_blue), ('GRID', (0,0), (-1,-1), 0.5, border_color), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(t_atk1)
        story.append(Spacer(1, 10))
        
        atk_details = [
            [Paragraph("<b>Duels Offensifs (Gagnés / Perdus)</b>", cell_header_style), Paragraph("<b>Pertes de Balle (Passe / Faute)</b>", cell_header_style)],
            [Paragraph(str(row.get('Duels Off', '0/0')), cell_style), Paragraph(f"{row.get('Perte (Passe)', 0)} / {row.get('Perte (Faute)', 0)}", cell_style)]
        ]
        t_atk2 = Table(atk_details, colWidths=[272, 273])
        t_atk2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ffh_blue), ('GRID', (0,0), (-1,-1), 0.5, border_color), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(t_atk2)
        story.append(Spacer(1, 20))
        
        story.append(Paragraph("Performances Défensives & Discipline", h1_style))
        def_details = [
            [Paragraph("<b>Duels Défensifs</b>", cell_header_style), Paragraph("<b>Interceptions</b>", cell_header_style), Paragraph("<b>Neutralisations</b>", cell_header_style), Paragraph("<b>Balles Provoquées</b>", cell_header_style)],
            [Paragraph(str(row.get('Duels Déf', '0/0')), cell_style), Paragraph(str(row.get('Interceptions', 0)), cell_style), Paragraph(str(row.get('Neutralisations', 0)), cell_style), Paragraph(str(row.get('Provoquées', 0)), cell_style)]
        ]
        t_def = Table(def_details, colWidths=[136, 136, 136, 137])
        t_def.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ffh_red), ('GRID', (0,0), (-1,-1), 0.5, border_color), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(t_def)
        story.append(Spacer(1, 10))
        
        disc_details = [
            [Paragraph("<b>Cartons Jaunes (Avertissement)</b>", cell_header_style), Paragraph("<b>Exclusions 2 Minutes</b>", cell_header_style)],
            [Paragraph(str(row.get('🟨', 0)), cell_style), Paragraph(str(row.get('⏱️ 2min', 0)), cell_style)]
        ]
        t_disc = Table(disc_details, colWidths=[272, 273])
        t_disc.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ffh_blue), ('GRID', (0,0), (-1,-1), 0.5, border_color), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(t_disc)

    for row in lignes_gardiennes:
        story.append(PageBreak())
        story.append(Paragraph("RAPPORT INDIVIDUEL GARDIENNE", subtitle_style))
        story.append(Spacer(1, 2))
        story.append(Paragraph(f"#{row.get('N°')} — {row.get('Gardienne')} <i>(Gardienne)</i>", title_style))
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("Efficacité dans la Cage", h1_style))
        g_stats = [
            [Paragraph("<b>Arrêts / Tirs Subis</b>", cell_header_style), Paragraph("<b>Pourcentage d'Arrêts</b>", cell_header_style), Paragraph("<b>Buts Encaissés</b>", cell_header_style)],
            [Paragraph(f"{row.get('Arrêts', 0)} / {row.get('Tirs Subis', 0)}", cell_style), Paragraph(str(row.get('% Arrêts', '0%')), cell_style), Paragraph(str(row.get('Buts Encaissés', 0)), cell_style)]
        ]
        t_g1 = Table(g_stats, colWidths=[181, 182, 182])
        t_g1.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ffh_red), ('GRID', (0,0), (-1,-1), 0.5, border_color), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(t_g1)
        story.append(Spacer(1, 15))
        
        story.append(Paragraph("Relance & Discipline", h1_style))
        g_off = [
            [Paragraph("<b>Buts Marqués / Tirs Tentés</b>", cell_header_style), Paragraph("<b>Sanctions</b>", cell_header_style)],
            [Paragraph(str(row.get('Buts Marqués', '0/0')), cell_style), Paragraph(f"{row.get('🟨', 0)} Avertissement(s) / {row.get('⏱️ 2min', 0)} 2min", cell_style)]
        ]
        t_g2 = Table(g_off, colWidths=[272, 273])
        t_g2.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,0), ffh_blue), ('GRID', (0,0), (-1,-1), 0.5, border_color), ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(t_g2)

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()