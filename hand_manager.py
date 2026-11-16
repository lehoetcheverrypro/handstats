import json
import os

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
            "historique_matchs": self.historique_matchs
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
            "historique_matchs": self.historique_matchs
        }

class EquipeManager:
    def __init__(self, fichier="effectif_hand.json"):
        dossier_script = os.path.dirname(os.path.abspath(__file__))
        self.fichier = os.path.join(dossier_script, fichier)
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
                        if d["type"] == "gardienne":
                            j = Gardienne(d["nom"], d["poste"], d["numero"])
                            j.arrets = d.get("arrets", 0)
                            j.tirs_subis = d.get("tirs_subis", 0)
                            j.buts_encaisses = d.get("buts_encaisses", 0)
                            j.buts = d.get("buts", 0)
                            j.tirs = d.get("tirs", 0)
                        else:
                            j = JoueuseDeChamp(d["nom"], d["poste"], d["numero"])
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

    def archiver_match(self, nom_match, attaques_adv_data=None, joueuses_actives=None, journal_actions=None, commentaires_staff=None):
        lignes_champ = [j for j in self.joueuses.values() if isinstance(j, JoueuseDeChamp) and (joueuses_actives is None or j.nom in joueuses_actives)]
        lignes_gard = [j for j in self.joueuses.values() if isinstance(j, Gardienne) and (joueuses_actives is None or j.nom in joueuses_actives)]
        
        score_eq = sum(j.buts for j in lignes_champ)
        for g in lignes_gard:
            score_eq += g.buts
        score_adv = sum(g.buts_encaisses for g in lignes_gard)

        for j in self.joueuses.values():
            if joueuses_actives is not None and j.nom not in joueuses_actives:
                continue

            match_common_data = {
                "match": nom_match,
                "score_equipe": score_eq,
                "score_adversaire": score_adv,
                "attaques_adversaires": attaques_adv_data or {},
                "journal_actions": journal_actions or [],
                "commentaires_staff": commentaires_staff or []
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
            
            # Remise à zéro
            j.cartons_jaunes = 0
            j.exclusions_2min = 0
            if isinstance(j, JoueuseDeChamp):
                j.buts = 0; j.tirs = 0; j.passes_decisives = 0
                j.pertes_de_balles_passe = 0; j.pertes_de_balles_faute = 0
                j.duels_off_gagnes = 0; j.duels_off_perdus = 0
                j.duels_def_gagnes = 0; j.duels_def_perdus = 0
                j.neutralisations = 0; j.interceptions = 0; j.pertes_balles_provoquees = 0
            elif isinstance(j, Gardienne):
                j.arrets = 0; j.tirs_subis = 0; j.buts_encaisses = 0; j.buts = 0; j.tirs = 0

        self.sauvegarder_donnees()

    def sauvegarder_commentaire_post_match(self, nom_match, texte_bilan):
        """Enregistre ou met à jour le bilan écrit post-match dans l'historique."""
        for j in self.joueuses.values():
            for m in j.historique_matchs:
                if m.get("match") == nom_match:
                    m["bilan_post_match"] = texte_bilan
        self.sauvegarder_donnees()

    @staticmethod
    def recuperer_toutes_les_joueuses_du_club(club_equipes):
        """
        Scanne les fichiers JSON de toutes les équipes du club 
        pour retourner un dictionnaire global {nom_joueuse: {"equipe": nom_eq, "objet": instance_joueuse}}
        Utile pour gérer les surclassements.
        """
        joueuses_club = {}
        for eq in club_equipes:
            nom_fichier = f"effectif_{eq.replace(' ', '_').replace('-', '')}.json"
            dossier_script = os.path.dirname(os.path.abspath(__file__))
            chemin_complet = os.path.join(dossier_script, nom_fichier)
            
            if os.path.exists(chemin_complet):
                try:
                    with open(chemin_complet, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        for nom, d in data.items():
                            # On évite les doublons stricts si déjà vu
                            if nom not in joueuses_club:
                                joueuses_club[nom] = {
                                    "equipe_origine": eq,
                                    "poste": d.get("poste"),
                                    "numero": d.get("numero"),
                                    "type": d.get("type")
                                }
                except Exception:
                    pass
        return joueuses_club

    def transferer_joueuse(self, nom_joueuse, autre_manager):
        if nom_joueuse in self.joueuses:
            joueuse_obj = self.joueuses[nom_joueuse]
            # On l'ajoute dans l'autre équipe
            autre_manager.joueuses[nom_joueuse] = joueuse_obj
            autre_manager.sauvegarder_donnees()
            # On la supprime de l'équipe actuelle
            self.supprimer_joueuse(nom_joueuse)
            return True
        return False