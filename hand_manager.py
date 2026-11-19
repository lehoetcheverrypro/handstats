import json
import os
import re
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.environ.get("HANDSTAT_DATA_DIR", os.path.join(BASE_DIR, "data"))


def normaliser_slug_club(club_slug: str | None) -> str:
    if not club_slug:
        return "bordeaux_etudiants_club"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(club_slug).strip().lower()).strip("_")
    return slug or "club_default"


def get_dossier_club(club_slug: str | None) -> str:
    dossier = os.path.join(DATA_ROOT, "clubs", normaliser_slug_club(club_slug))
    os.makedirs(dossier, exist_ok=True)
    return dossier


def supprimer_dossier_club(club_slug: str | None) -> bool:
    """Supprime définitivement le dossier de données d'un club si existant."""
    if not club_slug:
        return False
    slug_propre = normaliser_slug_club(club_slug)
    racine_clubs = os.path.abspath(os.path.join(DATA_ROOT, "clubs"))
    cible = os.path.abspath(os.path.join(racine_clubs, slug_propre))

    # Sécurité : s'assurer que la cible reste strictement à l'intérieur de DATA_ROOT/clubs
    if os.path.commonpath([racine_clubs, cible]) != racine_clubs or cible == racine_clubs:
        return False

    if os.path.exists(cible):
        shutil.rmtree(cible)
    return True


def get_nom_fichier_equipe(nom_equipe: str) -> str:
    return f"effectif_{nom_equipe.replace(' ', '_').replace('-', '')}.json"


class Joueuse:
    def __init__(self, nom, poste, numero):
        self.nom = nom
        self.poste = poste
        self.numero = int(numero)
        self.cartons_jaunes = 0
        self.exclusions_2min = 0
        self.historique_matchs = []

    def to_dict(self):
        raise NotImplementedError


class JoueuseDeChamp(Joueuse):
    def __init__(self, nom, poste, numero):
        super().__init__(nom, poste, numero)
        self.buts = 0
        self.tirs = 0
        self.passes_decisives = 0
        self.pertes_de_balles_passe = 0
        self.pertes_de_balles_faute = 0
        self.duels_off_gagnes = 0
        self.duels_off_perdus = 0
        self.duels_def_gagnes = 0
        self.duels_def_perdus = 0
        self.neutralisations = 0
        self.interceptions = 0
        self.pertes_balles_provoquees = 0

    def efficacite_tirs(self):
        if self.tirs == 0:
            return 0.0
        return round((self.buts / self.tirs) * 100, 1)

    def to_dict(self):
        return {
            "type": "champ",
            "nom": self.nom,
            "poste": self.poste,
            "numero": self.numero,
            "buts": self.buts,
            "tirs": self.tirs,
            "passes_decisives": self.passes_decisives,
            "pertes_de_balles_passe": self.pertes_de_balles_passe,
            "pertes_de_balles_faute": self.pertes_de_balles_faute,
            "duels_off_gagnes": self.duels_off_gagnes,
            "duels_off_perdus": self.duels_off_perdus,
            "duels_def_gagnes": self.duels_def_gagnes,
            "duels_def_perdus": self.duels_def_perdus,
            "neutralisations": self.neutralisations,
            "interceptions": self.interceptions,
            "pertes_balles_provoquees": self.pertes_balles_provoquees,
            "cartons_jaunes": self.cartons_jaunes,
            "exclusions_2min": self.exclusions_2min,
            "historique_matchs": self.historique_matchs,
        }


class Gardienne(Joueuse):
    def __init__(self, nom, poste, numero):
        super().__init__(nom, poste, numero)
        self.arrets = 0
        self.tirs_subis = 0
        self.buts_encaisses = 0
        self.buts = 0
        self.tirs = 0

    def pourcentage_arrets(self):
        if self.tirs_subis == 0:
            return 0.0
        return round((self.arrets / self.tirs_subis) * 100, 1)

    def to_dict(self):
        return {
            "type": "gardienne",
            "nom": self.nom,
            "poste": self.poste,
            "numero": self.numero,
            "arrets": self.arrets,
            "tirs_subis": self.tirs_subis,
            "buts_encaisses": self.buts_encaisses,
            "buts": self.buts,
            "tirs": self.tirs,
            "cartons_jaunes": self.cartons_jaunes,
            "exclusions_2min": self.exclusions_2min,
            "historique_matchs": self.historique_matchs,
        }


class EquipeManager:
    def __init__(self, fichier="effectif_hand.json", club_slug=None):
        self.club_slug = normaliser_slug_club(club_slug)
        self.dossier_club = get_dossier_club(self.club_slug)
        nom_base = os.path.basename(fichier)
        self.fichier = os.path.join(self.dossier_club, nom_base)
        self.joueuses = {}
        self.charger_donnees()

    def ajouter_joueuse(self, nom, poste, numero, type_joueuse="champ"):
        if type_joueuse == "gardienne":
            self.joueuses[nom] = Gardienne(nom, poste, numero)
        else:
            self.joueuses[nom] = JoueuseDeChamp(nom, poste, numero)
        self.sauvegarder_donnees()

    def supprimer_joueuse(self, nom):
        if nom in self.joueuses:
            del self.joueuses[nom]
            self.sauvegarder_donnees()

    def sauvegarder_donnees(self):
        os.makedirs(self.dossier_club, exist_ok=True)
        data = {nom: j.to_dict() for nom, j in self.joueuses.items()}
        with open(self.fichier, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def charger_donnees(self):
        if os.path.exists(self.fichier):
            try:
                with open(self.fichier, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.joueuses = {}
                    for nom, d in data.items():
                        if not isinstance(d, dict):
                            continue
                        if d.get("type") == "gardienne":
                            j = Gardienne(d.get("nom", nom), d.get("poste", "Gardienne"), d.get("numero", 1))
                            j.arrets = d.get("arrets", 0)
                            j.tirs_subis = d.get("tirs_subis", 0)
                            j.buts_encaisses = d.get("buts_encaisses", 0)
                            j.buts = d.get("buts", 0)
                            j.tirs = d.get("tirs", 0)
                        else:
                            j = JoueuseDeChamp(d.get("nom", nom), d.get("poste", "Arrière gauche"), d.get("numero", 1))
                            j.buts = d.get("buts", 0)
                            j.tirs = d.get("tirs", 0)
                            j.passes_decisives = d.get("passes_decisives", 0)
                            j.pertes_de_balles_passe = d.get("pertes_de_balles_passe", 0)
                            j.pertes_de_balles_faute = d.get("pertes_de_balles_faute", 0)
                            j.duels_off_gagnes = d.get("duels_off_gagnes", 0)
                            j.duels_off_perdus = d.get("duels_off_perdus", 0)
                            j.duels_def_gagnes = d.get("duels_def_gagnes", 0)
                            j.duels_def_perdus = d.get("duels_def_perdus", 0)
                            j.neutralisations = d.get("neutralisations", 0)
                            j.interceptions = d.get("interceptions", 0)
                            j.pertes_balles_provoquees = d.get("pertes_balles_provoquees", 0)

                        j.cartons_jaunes = d.get("cartons_jaunes", 0)
                        j.exclusions_2min = d.get("exclusions_2min", 0)
                        j.historique_matchs = d.get("historique_matchs", [])
                        self.joueuses[nom] = j
            except Exception as e:
                print(f"Erreur lors du chargement : {e}")

    def archiver_match(
        self,
        nom_match,
        attaques_adv_data=None,
        joueuses_actives=None,
        journal_actions=None,
        commentaires_staff=None,
        numeros_match=None,
        pretes_dict=None,
        club_equipes=None,
    ):
        if numeros_match is None:
            numeros_match = {}
        if pretes_dict is None:
            pretes_dict = {}
        if club_equipes is None:
            club_equipes = []

        lignes_champ = [
            j
            for j in self.joueuses.values()
            if isinstance(j, JoueuseDeChamp) and (joueuses_actives is None or j.nom in joueuses_actives)
        ]
        lignes_gard = [
            j
            for j in self.joueuses.values()
            if isinstance(j, Gardienne) and (joueuses_actives is None or j.nom in joueuses_actives)
        ]

        for j_p in pretes_dict.values():
            if joueuses_actives is None or j_p.nom in joueuses_actives:
                if isinstance(j_p, JoueuseDeChamp):
                    lignes_champ.append(j_p)
                else:
                    lignes_gard.append(j_p)

        score_eq = sum(j.buts for j in lignes_champ)
        for g in lignes_gard:
            score_eq += g.buts
        score_adv = sum(g.buts_encaisses for g in lignes_gard)

        for nom, j in self.joueuses.items():
            if joueuses_actives is not None and j.nom not in joueuses_actives:
                continue

            numero_a_archiver = numeros_match.get(j.nom, j.numero)
            match_common_data = {
                "match": nom_match,
                "score_equipe": score_eq,
                "score_adversaire": score_adv,
                "numero_match": numero_a_archiver,
                "attaques_adversaires": attaques_adv_data or {},
                "journal_actions": journal_actions or [],
                "commentaires_staff": commentaires_staff or [],
            }

            if isinstance(j, JoueuseDeChamp):
                match_data = {
                    **match_common_data,
                    "buts": j.buts,
                    "tirs": j.tirs,
                    "passes_decisives": j.passes_decisives,
                    "pertes_passe": j.pertes_de_balles_passe,
                    "pertes_faute": j.pertes_de_balles_faute,
                    "duels_off_gagnes": j.duels_off_gagnes,
                    "duels_off_perdus": j.duels_off_perdus,
                    "duels_def_gagnes": j.duels_def_gagnes,
                    "duels_def_perdus": j.duels_def_perdus,
                    "neutralisations": j.neutralisations,
                    "interceptions": j.interceptions,
                    "balles_provoquees": j.pertes_balles_provoquees,
                    "cartons_jaunes": j.cartons_jaunes,
                    "exclusions_2min": j.exclusions_2min,
                }
            else:
                match_data = {
                    **match_common_data,
                    "arrets": j.arrets,
                    "tirs_subis": j.tirs_subis,
                    "buts_encaisses": j.buts_encaisses,
                    "buts": j.buts,
                    "tirs": j.tirs,
                    "cartons_jaunes": j.cartons_jaunes,
                    "exclusions_2min": j.exclusions_2min,
                }

            j.historique_matchs.append(match_data)

            j.cartons_jaunes = 0
            j.exclusions_2min = 0
            if isinstance(j, JoueuseDeChamp):
                j.buts = 0
                j.tirs = 0
                j.passes_decisives = 0
                j.pertes_de_balles_passe = 0
                j.pertes_de_balles_faute = 0
                j.duels_off_gagnes = 0
                j.duels_off_perdus = 0
                j.duels_def_gagnes = 0
                j.duels_def_perdus = 0
                j.neutralisations = 0
                j.interceptions = 0
                j.pertes_balles_provoquees = 0
            elif isinstance(j, Gardienne):
                j.arrets = 0
                j.tirs_subis = 0
                j.buts_encaisses = 0
                j.buts = 0
                j.tirs = 0

        self.sauvegarder_donnees()

        # Archivage des joueuses surclassées uniquement au sein du même club
        toutes_du_club = self.recuperer_toutes_les_joueuses_du_club(club_equipes, club_slug=self.club_slug)

        for nom_p, j_p in pretes_dict.items():
            if joueuses_actives is not None and j_p.nom not in joueuses_actives:
                continue
            if nom_p in toutes_du_club:
                eq_orig = toutes_du_club[nom_p]["equipe_origine"]
                nom_f_orig = get_nom_fichier_equipe(eq_orig)
                mgr_orig = EquipeManager(fichier=nom_f_orig, club_slug=self.club_slug)
                if nom_p in mgr_orig.joueuses:
                    jp_orig = mgr_orig.joueuses[nom_p]

                    jp_orig.cartons_jaunes = j_p.cartons_jaunes
                    jp_orig.exclusions_2min = j_p.exclusions_2min
                    if isinstance(jp_orig, JoueuseDeChamp):
                        jp_orig.buts = j_p.buts
                        jp_orig.tirs = j_p.tirs
                        jp_orig.passes_decisives = j_p.passes_decisives
                        jp_orig.pertes_de_balles_passe = j_p.pertes_de_balles_passe
                        jp_orig.pertes_de_balles_faute = j_p.pertes_de_balles_faute
                        jp_orig.duels_off_gagnes = j_p.duels_off_gagnes
                        jp_orig.duels_off_perdus = j_p.duels_off_perdus
                        jp_orig.duels_def_gagnes = j_p.duels_def_gagnes
                        jp_orig.duels_def_perdus = j_p.duels_def_perdus
                        jp_orig.neutralisations = j_p.neutralisations
                        jp_orig.interceptions = j_p.interceptions
                        jp_orig.pertes_balles_provoquees = j_p.pertes_balles_provoquees
                    elif isinstance(jp_orig, Gardienne):
                        jp_orig.arrets = j_p.arrets
                        jp_orig.tirs_subis = j_p.tirs_subis
                        jp_orig.buts_encaisses = j_p.buts_encaisses
                        jp_orig.buts = j_p.buts
                        jp_orig.tirs = j_p.tirs

                    numero_a_archiver_p = numeros_match.get(jp_orig.nom, jp_orig.numero)
                    match_common_data_p = {
                        "match": nom_match,
                        "score_equipe": score_eq,
                        "score_adversaire": score_adv,
                        "numero_match": numero_a_archiver_p,
                        "attaques_adversaires": attaques_adv_data or {},
                        "journal_actions": journal_actions or [],
                        "commentaires_staff": commentaires_staff or [],
                    }

                    if isinstance(jp_orig, JoueuseDeChamp):
                        match_data_p = {
                            **match_common_data_p,
                            "buts": jp_orig.buts,
                            "tirs": jp_orig.tirs,
                            "passes_decisives": jp_orig.passes_decisives,
                            "pertes_passe": jp_orig.pertes_de_balles_passe,
                            "pertes_faute": jp_orig.pertes_de_balles_faute,
                            "duels_off_gagnes": jp_orig.duels_off_gagnes,
                            "duels_off_perdus": jp_orig.duels_off_perdus,
                            "duels_def_gagnes": jp_orig.duels_def_gagnes,
                            "duels_def_perdus": jp_orig.duels_def_perdus,
                            "neutralisations": jp_orig.neutralisations,
                            "interceptions": jp_orig.interceptions,
                            "balles_provoquees": jp_orig.pertes_balles_provoquees,
                            "cartons_jaunes": jp_orig.cartons_jaunes,
                            "exclusions_2min": jp_orig.exclusions_2min,
                        }
                    else:
                        match_data_p = {
                            **match_common_data_p,
                            "arrets": jp_orig.arrets,
                            "tirs_subis": jp_orig.tirs_subis,
                            "buts_encaisses": jp_orig.buts_encaisses,
                            "buts": jp_orig.buts,
                            "tirs": jp_orig.tirs,
                            "cartons_jaunes": jp_orig.cartons_jaunes,
                            "exclusions_2min": jp_orig.exclusions_2min,
                        }

                    jp_orig.historique_matchs.append(match_data_p)
                    mgr_orig.sauvegarder_donnees()

    def sauvegarder_commentaire_post_match(self, nom_match, texte_bilan):
        for j in self.joueuses.values():
            for m in j.historique_matchs:
                if m.get("match") == nom_match:
                    m["bilan_post_match"] = texte_bilan
        self.sauvegarder_donnees()

    @staticmethod
    def recuperer_toutes_les_joueuses_du_club(club_equipes, club_slug=None):
        joueuses_club = {}
        dossier_c = get_dossier_club(club_slug)
        for eq in club_equipes or []:
            nom_fichier = get_nom_fichier_equipe(eq)
            chemin_complet = os.path.join(dossier_c, nom_fichier)
            if os.path.exists(chemin_complet):
                try:
                    with open(chemin_complet, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for nom, d in data.items():
                            if nom not in joueuses_club and isinstance(d, dict):
                                joueuses_club[nom] = {
                                    "equipe_origine": eq,
                                    "poste": d.get("poste"),
                                    "numero": d.get("numero"),
                                    "type": d.get("type"),
                                }
                except Exception:
                    pass
        return joueuses_club

    def transferer_joueuse(self, nom_joueuse, autre_manager):
        if nom_joueuse in self.joueuses:
            joueuse_obj = self.joueuses[nom_joueuse]
            autre_manager.joueuses[nom_joueuse] = joueuse_obj
            autre_manager.sauvegarder_donnees()
            self.supprimer_joueuse(nom_joueuse)
            return True
        return False