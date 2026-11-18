import streamlit as st

def afficher_selecteur_zone_terrain(key_suffix="terrain"):
    """
    Affiche le choix de la zone de départ du tir sur le demi-terrain :
    - Aile Gauche / Droite
    - 6m Centre
    - Extérieur 9m Gauche / Centre / Droite
    """
    st.markdown("""
        <div style='text-align: center; font-weight: 600; margin-bottom: 12px; color: #334155; font-size: 15px;'>
            📍 Étape 1/2 : D'où part le tir sur le terrain ?
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    zone_choisie = None
    
    with col1:
        if st.button("⬅️ Aile Gauche", key=f"ter_ag_{key_suffix}", use_container_width=True):
            zone_choisie = "Aile Gauche"
        if st.button("🎯 Extérieur 9m Gauche", key=f"ter_9mg_{key_suffix}", use_container_width=True):
            zone_choisie = "Exter 9m Gauche"
            
    with col2:
        if st.button("📍 6m Centre", key=f"ter_6mc_{key_suffix}", use_container_width=True):
            zone_choisie = "6m Centre"
        if st.button("🎯 Extérieur 9m Centre", key=f"ter_9mc_{key_suffix}", use_container_width=True):
            zone_choisie = "Exter 9m Centre"
            
    with col3:
        if st.button("➡️ Aile Droite", key=f"ter_ad_{key_suffix}", use_container_width=True):
            zone_choisie = "Aile Droite"
        if st.button("🎯 Extérieur 9m Droite", key=f"ter_9md_{key_suffix}", use_container_width=True):
            zone_choisie = "Exter 9m Droite"
            
    return zone_choisie


def afficher_grille_saisie_interactive(key_suffix, action_type=None):
    """
    Affiche une grille interactive de la cage de handball (zones 1 à 9 avec flèches).
    Le bouton 'Hors cadre' n'apparaît QUE si action_type == "Tir raté".
    """
    st.markdown("""
        <div style='text-align: center; font-weight: 600; margin-bottom: 10px; color: #334155; font-size: 14px;'>
            🎯 Étape 2/2 : Localisation de la frappe (Cage 3x3)
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    zone_choisie = None
    
    with col1:
        if st.button("↖️ Haut-G", key=f"z1_{key_suffix}", use_container_width=True):
            zone_choisie = "Haut-Gauche"
        if st.button("⬅️ Mi-G", key=f"z4_{key_suffix}", use_container_width=True):
            zone_choisie = "Milieu-Gauche"
        if st.button("↙️ Bas-G", key=f"z7_{key_suffix}", use_container_width=True):
            zone_choisie = "Bas-Gauche"
            
    with col2:
        if st.button("⬆️ Haut-C", key=f"z2_{key_suffix}", use_container_width=True):
            zone_choisie = "Haut-Centre"
        if st.button("⏺️ Mi-C", key=f"z5_{key_suffix}", use_container_width=True):
            zone_choisie = "Milieu-Centre"
        if st.button("⬇️ Bas-C", key=f"z8_{key_suffix}", use_container_width=True):
            zone_choisie = "Bas-Centre"
            
    with col3:
        if st.button("↗️ Haut-D", key=f"z3_{key_suffix}", use_container_width=True):
            zone_choisie = "Haut-Droite"
        if st.button("➡️ Mi-D", key=f"z6_{key_suffix}", use_container_width=True):
            zone_choisie = "Milieu-Droite"
        if st.button("↘️ Bas-D", key=f"z9_{key_suffix}", use_container_width=True):
            zone_choisie = "Bas-Droite"
            
    # Le bouton Hors cadre apparaît UNIQUEMENT pour un tir raté
    if action_type == "Tir raté":
        st.markdown("<div style='margin-top: 8px;'></div>", unsafe_allow_html=True)
        if st.button("❌ Tir Hors Cadre", key=f"z_hors_{key_suffix}", use_container_width=True, type="secondary"):
            zone_choisie = "Hors cadre"
            
    return zone_choisie


def afficher_cage_recapitulative(donnees_zones, titre="Récapitulatif des Tirs", inclure_hors_cadre=True):
    """
    Affiche un récapitulatif visuel sous forme de grille 3x3 de la cage de handball.
    """
    st.markdown(f"**{titre}**")
    
    zones_standard = [
        ["Haut-Gauche", "Haut-Centre", "Haut-Droite"],
        ["Milieu-Gauche", "Milieu-Centre", "Milieu-Droite"],
        ["Bas-Gauche", "Bas-Centre", "Bas-Droite"]
    ]
    
    zones_a_afficher = donnees_zones.copy()
    if not inclure_hors_cadre and "Hors cadre" in zones_a_afficher:
        zones_a_afficher.pop("Hors cadre")
        
    if not zones_a_afficher and not (inclure_hors_cadre and donnees_zones.get("Hors cadre", {}).get("echec", 0) > 0):
        st.info("Aucune donnée de tir enregistrée pour le moment.")
        return

    for ligne in zones_standard:
        c1, c2, c3 = st.columns(3)
        for idx, z_nom in enumerate(ligne):
            stats = zones_a_afficher.get(z_nom, {"succes": 0, "echec": 0})
            succes = stats.get("succes", 0)
            echec = stats.get("echec", 0)
            total = succes + echec
            pct = round((succes / total * 100), 1) if total > 0 else 0.0
            
            if total == 0:
                bg_color = "#f8fafc"
                border_color = "#cbd5e1"
            elif pct >= 60:
                bg_color = "#ecfdf5"
                border_color = "#34d399"
            elif pct >= 30:
                bg_color = "#fffbeb"
                border_color = "#fbbf24"
            else:
                bg_color = "#fef2f2"
                border_color = "#f87171"
            
            col_cible = [c1, c2, c3][idx]
            with col_cible:
                st.markdown(f"""
                    <div style="background-color: {bg_color} !important; border: 1px solid {border_color}; border-radius: 8px; padding: 10px; text-align: center; margin-bottom: 8px; font-size: 12px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); color: #0f172a !important;">
                        <div style="font-weight: 700; color: #334155 !important; margin-bottom: 4px; font-size: 11px; text-transform: uppercase;">{z_nom.replace('-', ' ')}</div>
                        <div style="color: #0f172a !important; font-weight: 600;"><b>{succes} / {echec}</b></div>
                        <div style="color: #0284c7 !important; font-weight: bold; margin-top: 3px; font-size: 13px;">{pct}% <span style="font-size: 10px; color: #64748b !important;">({total})</span></div>
                    </div>
                """, unsafe_allow_html=True)

    if inclure_hors_cadre and "Hors cadre" in donnees_zones:
        stats_hors = donnees_zones["Hors cadre"]
        echec_h = stats_hors.get("echec", 0)
        st.markdown(f"""
            <div style="background-color: #fef2f2 !important; border: 1px solid #fca5a5; border-radius: 8px; padding: 8px; text-align: center; margin-top: 4px; font-size: 12px; color: #991b1b !important;">
                <span style="font-weight: 700; color: #991b1b !important;">Tir Hors Cadre :</span> <b style="color: #991b1b !important;">{echec_h}</b> raté(s)
            </div>
        """, unsafe_allow_html=True)