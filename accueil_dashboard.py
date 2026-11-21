"""Tableau de bord de l'accueil staff : chiffres clés, forme récente, meilleurs buteurs."""
import html

import streamlit as st

from hand_manager import Gardienne
from theme import kpi_html


def calculer_resume_saison(manager) -> dict:
    matchs = {}  # nom -> (buts pour, buts contre), dans l'ordre d'archivage
    buts_par_membre = {}
    buts_champ = tirs_champ = 0
    arrets = tirs_subis = 0

    for membre in manager.joueuses.values():
        est_gardien = isinstance(membre, Gardienne)
        for m in getattr(membre, "historique_matchs", []) or []:
            nom = m.get("match")
            if nom and nom not in matchs:
                matchs[nom] = (int(m.get("score_equipe", 0) or 0), int(m.get("score_adversaire", 0) or 0))
            buts = int(m.get("buts", 0) or 0)
            if buts:
                buts_par_membre[membre.nom] = buts_par_membre.get(membre.nom, 0) + buts
            if est_gardien:
                arrets += int(m.get("arrets", 0) or 0)
                tirs_subis += int(m.get("tirs_subis", 0) or 0)
            else:
                buts_champ += buts
                tirs_champ += int(m.get("tirs", 0) or 0)

    liste = [(nom, pour, contre) for nom, (pour, contre) in matchs.items()]
    v = sum(1 for _, p, c in liste if p > c)
    n = sum(1 for _, p, c in liste if p == c)
    d = sum(1 for _, p, c in liste if p < c)
    nb = len(liste)
    return {
        "matchs": liste,
        "nb": nb,
        "v": v, "n": n, "d": d,
        "pour": sum(p for _, p, _ in liste),
        "contre": sum(c for _, _, c in liste),
        "eff_tirs": round(buts_champ / tirs_champ * 100, 1) if tirs_champ else None,
        "buts_champ": buts_champ, "tirs_champ": tirs_champ,
        "pct_arrets": round(arrets / tirs_subis * 100, 1) if tirs_subis else None,
        "arrets": arrets, "tirs_subis": tirs_subis,
        "top_buteurs": sorted(buts_par_membre.items(), key=lambda x: x[1], reverse=True)[:5],
    }


def _res(p, c):
    if p > c:
        return "v", "V"
    if p < c:
        return "d", "D"
    return "n", "N"


def afficher_tableau_de_bord(r: dict, feminin: bool = True) -> None:
    nb = r["nb"]
    if nb == 0:
        st.markdown(
            '<div class="hs-card"><div class="hs-card-title">Aucun match archivé</div>'
            '<div class="hs-empty">Le tableau de bord se remplit dès le premier match terminé : '
            "bilan, forme récente, efficacité au tir et meilleurs buteurs.</div></div>",
            unsafe_allow_html=True,
        )
        return

    moy_pour = round(r["pour"] / nb, 1)
    moy_contre = round(r["contre"] / nb, 1)
    diff = r["pour"] - r["contre"]
    signe = "+" if diff > 0 else ""
    pct_v = round(r["v"] / nb * 100)

    kpis = "".join([
        kpi_html("Matchs joués", nb, f"{pct_v} % de victoires"),
        kpi_html("Bilan", f'{r["v"]}-{r["n"]}-{r["d"]}', "victoires, nuls, défaites"),
        kpi_html("Buts marqués", moy_pour, f'{r["pour"]} au total', "/match"),
        kpi_html("Buts encaissés", moy_contre, f"Différence {signe}{diff}", "/match"),
        kpi_html(
            "Efficacité au tir",
            f'{r["eff_tirs"]}' if r["eff_tirs"] is not None else "n.d.",
            f'{r["buts_champ"]} buts sur {r["tirs_champ"]} tirs' if r["tirs_champ"] else "",
            "%" if r["eff_tirs"] is not None else "",
        ),
        kpi_html(
            "Arrêts gardiens",
            f'{r["pct_arrets"]}' if r["pct_arrets"] is not None else "n.d.",
            f'{r["arrets"]} arrêts sur {r["tirs_subis"]} tirs' if r["tirs_subis"] else "",
            "%" if r["pct_arrets"] is not None else "",
        ),
    ])

    recents = list(reversed(r["matchs"]))[:6]
    forme = "".join(
        f'<span class="hs-res hs-res-{_res(p, c)[0]}">{_res(p, c)[1]}</span>' for _, p, c in recents[:5]
    )
    lignes = ""
    for nom, p, c in recents:
        cls, lettre = _res(p, c)
        dif = p - c
        css_dif = "hs-pos" if dif > 0 else ("hs-neg" if dif < 0 else "hs-nul")
        lignes += (
            f'<div class="hs-row"><span class="hs-res hs-res-{cls}">{lettre}</span>'
            f'<span class="hs-row-name">{html.escape(str(nom))}</span>'
            f'<span class="hs-row-score">{p} – {c}</span>'
            f'<span class="hs-row-diff {css_dif}">{"+" if dif > 0 else ""}{dif}</span></div>'
        )

    top = r["top_buteurs"]
    maxi = top[0][1] if top else 1
    leaders = "".join(
        f'<div class="hs-lead"><div class="hs-lead-top"><span>{html.escape(str(nom))}</span><b>{b}</b></div>'
        f'<div class="hs-bar"><i style="width:{round(b / maxi * 100)}%"></i></div></div>'
        for nom, b in top
    ) or '<div class="hs-empty">Aucun but enregistré.</div>'
    titre_top = "Meilleures buteuses" if feminin else "Meilleurs buteurs"

    st.markdown(
        f'<div class="hs-kpis">{kpis}</div>'
        '<div class="hs-cols">'
        '<div class="hs-card"><div class="hs-card-head"><span class="hs-card-title">Derniers matchs</span>'
        f'<span class="hs-form">{forme}</span></div>{lignes}</div>'
        f'<div class="hs-card"><div class="hs-card-head"><span class="hs-card-title">{titre_top}</span></div>{leaders}</div>'
        "</div>",
        unsafe_allow_html=True,
    )
