from datetime import datetime, timedelta
import hashlib
import json
import os
import re
import shutil

from supabase_store import delete_json, get_bytes, get_json, set_json, supprimer_scope

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_ROOT = os.environ.get("HANDSTAT_DATA_DIR", os.path.join(BASE_DIR, "data"))


def normaliser_slug_club(club_slug: str | None) -> str:
    if not club_slug:
        return "bordeaux_etudiants_club"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(club_slug).strip().lower()).strip("_")
    return slug or "club_default"


_LOGO_VERIFIE: dict[str, float] = {}


def _synchroniser_logo_local(slug: str, dossier: str, force: bool = False) -> None:
    """Recopie le logo du club (stocké dans Supabase) dans le dossier local temporaire,
    pour que les PDF et le thème le trouvent comme avant (logo_club.png)."""
    import time

    maintenant = time.time()
    if not force and maintenant - _LOGO_VERIFIE.get(slug, 0) < 30:
        return
    _LOGO_VERIFIE[slug] = maintenant
    try:
        data = get_bytes(slug, "logo_club.png")
        if data is None:
            return
        chemin = os.path.join(dossier, "logo_club.png")
        if os.path.exists(chemin):
            with open(chemin, "rb") as f:
                if f.read() == data:
                    return
        with open(chemin, "wb") as f:
            f.write(data)
    except Exception:
        pass  # le logo est facultatif : ne jamais bloquer l'application


def get_dossier_club(club_slug: str | None) -> str:
    """Dossier LOCAL temporaire du club (cache du logo). Les données, elles, sont dans Supabase."""
    dossier = os.path.join(DATA_ROOT, "clubs", normaliser_slug_club(club_slug))
    os.makedirs(dossier, exist_ok=True)
    _synchroniser_logo_local(normaliser_slug_club(club_slug), dossier)
    return dossier


def supprimer_dossier_club(club_slug: str | None) -> bool:
    """Supprime définitivement les données (Supabase) et le cache local d'un club."""
    if not club_slug:
        return False
    slug_propre = normaliser_slug_club(club_slug)
    supprimer_scope(slug_propre)
    racine_clubs = os.path.abspath(os.path.join(DATA_ROOT, "clubs"))
    cible = os.path.abspath(os.path.join(racine_clubs, slug_propre))

    # Sécurité : la cible doit rester strictement à l'intérieur de DATA_ROOT/clubs
    if os.path.commonpath([racine_clubs, cible]) != racine_clubs or cible == racine_clubs:
        return False

    if os.path.exists(cible):
        shutil.rmtree(cible)
    return True


def get_nom_fichier_equipe(nom_equipe: str) -> str:
    return f"effectif_{nom_equipe.replace(' ', '_').replace('-', '')}.json"


CHAMPS_LOURDS = ("journal_actions", "commentaires_staff", "attaques_adversaires")


class EntreeMatch(dict):
    """Entrée d'historique d'un match pour une joueuse.

    Les champs volumineux (journal chronologique, notes du staff, attaques adverses) sont identiques pour
    toutes les joueuses d'un match : ils ne sont donc plus recopiés dans chaque fiche mais stockés UNE fois
    par match, et chargés seulement quand on les lit. Pour le reste du code rien ne change :
    entree.get("journal_actions") et entree["journal_actions"] fonctionnent comme avant.
    """

    def __init__(self, donnees=(), chargeur=None, detail=None):
        super().__init__(donnees)
        self._chargeur = chargeur
        self._detail = detail

    def _lourd(self):
        if self._detail is None:
            mid = dict.get(self, "match_id")
            self._detail = (self._chargeur(mid) if (self._chargeur and mid) else None) or {}
        return self._detail

    def _delegue(self, cle):
        return cle in CHAMPS_LOURDS and not dict.__contains__(self, cle) and bool(dict.get(self, "match_id"))

    def __missing__(self, cle):
        if self._delegue(cle):
            detail = self._lourd()
            if cle in detail:
                return detail[cle]
        raise KeyError(cle)

    def get(self, cle, defaut=None):
        if self._delegue(cle):
            return self._lourd().get(cle, defaut)
        return dict.get(self, cle, defaut)

    def __contains__(self, cle):
        if self._delegue(cle):
            return cle in self._lourd()
        return dict.__contains__(self, cle)

    def copy(self):
        return EntreeMatch(self, self._chargeur, self._detail)


class Joueuse:
    def __init__(self, nom, poste, numero):
        self.nom = nom
        self.poste = poste
        self.numero = int(numero)
        self.cartons_jaunes = 0
        self.exclusions_2min = 0
        self.cartons_rouges = 0
        self.historique_matchs = []
        self.suivi_longitudinal = []

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
            "cartons_rouges": self.cartons_rouges,
            "historique_matchs": self.historique_matchs,
            "suivi_longitudinal": self.suivi_longitudinal,
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
            "cartons_rouges": self.cartons_rouges,
            "historique_matchs": self.historique_matchs,
            "suivi_longitudinal": self.suivi_longitudinal,
        }


class EquipeManager:
    def __init__(self, fichier="effectif_hand.json", club_slug=None):
        self.club_slug = normaliser_slug_club(club_slug)
        self.dossier_club = get_dossier_club(self.club_slug)
        nom_base = os.path.basename(fichier)
        self.cle_stockage = nom_base                     # clé dans Supabase (ancien nom de fichier)
        self.fichier = os.path.join(self.dossier_club, nom_base)   # conservé pour compatibilité
        self._charge_ok = True
        self._ids_charges = set()      # détails de match référencés au chargement (pour le ménage)
        self.live_hook = None          # défini par l'écran de match en direct (voir staff_app)
        self._details_cache = {}
        self.joueuses = {}
        self.charger_donnees()

    def ajouter_joueuse(self, nom, poste, numero, type_joueuse="champ"):
        if type_joueuse == "gardienne":
            self.joueuses[nom] = Gardienne(nom, poste, numero)
        else:
            self.joueuses[nom] = JoueuseDeChamp(nom, poste, numero)
        self.sauvegarder_donnees(force=True)

    def supprimer_joueuse(self, nom):
        if nom in self.joueuses:
            del self.joueuses[nom]
            self.sauvegarder_donnees(force=True)

    def sauvegarder_donnees(self, force=False):
        # Pendant un match en direct PARTAGÉ, les compteurs du live ne s'écrivent plus dans la fiche d'équipe :
        # l'état du match est publié (et fusionné) via live_hook. Seules les opérations de structure
        # (ajout de joueuse, archivage...) passent avec force=True.
        if not force and getattr(self, "live_hook", None):
            self.live_hook()
            return
        if not getattr(self, "_charge_ok", True):
            raise RuntimeError(
                "Sauvegarde bloquée : le chargement initial des données a échoué "
                "(évite d'écraser les données existantes). Rechargez la page."
            )
        data = {nom: j.to_dict() for nom, j in self.joueuses.items()}
        set_json(self.club_slug, self.cle_stockage, data)

        # Ménage : supprime les détails de match qui ne sont plus référencés (match archivé supprimé).
        actuels = self._ids_details_references()
        for mid in self._ids_charges - actuels:
            try:
                delete_json(self.club_slug, self._cle_detail(mid))
            except Exception:
                pass
        self._ids_charges = actuels

    # --- Détails de match (journal, notes, attaques adverses) stockés une seule fois par match ---
    def _cle_detail(self, match_id):
        racine = self.cle_stockage[:-5] if self.cle_stockage.lower().endswith(".json") else self.cle_stockage
        return f"detail_{racine}_{match_id}.json"

    @staticmethod
    def _id_detail(nom_match, detail):
        brut = json.dumps([nom_match, detail], sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha1(brut.encode("utf-8")).hexdigest()[:20]

    def _charger_detail(self, match_id):
        if match_id not in self._details_cache:
            self._details_cache[match_id] = get_json(
                self.club_slug, self._cle_detail(match_id), None, immuable=True
            )
        return self._details_cache[match_id]

    def _nouvelle_entree(self, donnees, detail=None):
        return EntreeMatch(donnees, self._charger_detail, detail)

    def _ids_details_references(self):
        ids = set()
        for j in self.joueuses.values():
            for m in j.historique_matchs:
                if isinstance(m, dict):
                    mid = dict.get(m, "match_id")
                    if mid:
                        ids.add(mid)
        return ids

    def _compacter_historique_ancien(self):
        """Migration automatique : ancien format (journal copié dans chaque joueuse) -> format compact.
        Les détails sont écrits AVANT de modifier quoi que ce soit ; en cas d'échec, rien n'est changé."""
        try:
            details = {}
            remplacements = []
            for j in self.joueuses.values():
                for idx, m in enumerate(j.historique_matchs):
                    if not isinstance(m, dict) or not any(dict.__contains__(m, k) for k in CHAMPS_LOURDS):
                        continue
                    detail = {
                        "attaques_adversaires": dict.get(m, "attaques_adversaires") or {},
                        "journal_actions": dict.get(m, "journal_actions") or [],
                        "commentaires_staff": dict.get(m, "commentaires_staff") or [],
                    }
                    propre = {k: v for k, v in m.items() if k not in CHAMPS_LOURDS}
                    if any(detail.values()):
                        mid = self._id_detail(dict.get(m, "match"), detail)
                        details[mid] = detail
                        propre["match_id"] = mid
                        remplacements.append((j, idx, propre, detail))
                    else:
                        remplacements.append((j, idx, propre, None))
            if not remplacements:
                return
            for mid, detail in details.items():
                set_json(self.club_slug, self._cle_detail(mid), detail)
            for j, idx, propre, detail in remplacements:
                j.historique_matchs[idx] = self._nouvelle_entree(propre, detail)
            self.sauvegarder_donnees(force=True)
        except Exception as exc:
            print(f"Compactage de l'historique reporté : {exc}")

    def charger_donnees(self):
        # Une erreur réseau/base remonte volontairement : on ne doit JAMAIS considérer
        # l'équipe comme vide si la lecture a échoué (risque d'écraser les données).
        self._charge_ok = False
        data = get_json(self.club_slug, self.cle_stockage, None)
        if data is None:
            self._charge_ok = True
            return
        try:
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
                j.cartons_rouges = d.get("cartons_rouges", 0)
                j.historique_matchs = [
                    self._nouvelle_entree(m) if isinstance(m, dict) else m
                    for m in d.get("historique_matchs", [])
                ]
                suivi_raw = d.get("suivi_longitudinal", [])
                j.suivi_longitudinal = suivi_raw if isinstance(suivi_raw, list) else []
                self.joueuses[nom] = j
            self._charge_ok = True
            self._ids_charges = self._ids_details_references()
            self._compacter_historique_ancien()
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
        capitaine=None,
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

        # Journal, notes et attaques adverses : stockés UNE fois pour le match (et non par joueuse).
        detail_match = {
            "attaques_adversaires": attaques_adv_data or {},
            "journal_actions": journal_actions or [],
            "commentaires_staff": commentaires_staff or [],
        }
        match_id = None
        if any(detail_match.values()):
            match_id = self._id_detail(nom_match, detail_match)
            set_json(self.club_slug, self._cle_detail(match_id), detail_match)
        champs_lourds = {"match_id": match_id} if match_id else {}

        for nom, j in self.joueuses.items():
            if joueuses_actives is not None and j.nom not in joueuses_actives:
                continue

            numero_a_archiver = numeros_match.get(j.nom, j.numero)
            match_common_data = {
                "match": nom_match,
                "score_equipe": score_eq,
                "score_adversaire": score_adv,
                "numero_match": numero_a_archiver,
                "capitaine": capitaine,
                **champs_lourds,
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
                    "cartons_rouges": j.cartons_rouges,
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
                    "cartons_rouges": j.cartons_rouges,
                }

            j.historique_matchs.append(self._nouvelle_entree(match_data, detail_match))

            j.cartons_jaunes = 0
            j.exclusions_2min = 0
            j.cartons_rouges = 0
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

        self.sauvegarder_donnees(force=True)

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
                    jp_orig.cartons_rouges = getattr(j_p, "cartons_rouges", 0)
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
                        "capitaine": capitaine,
                        **champs_lourds,
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
                            "cartons_rouges": jp_orig.cartons_rouges,
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
                            "cartons_rouges": jp_orig.cartons_rouges,
                        }

                    if match_id:
                        set_json(self.club_slug, mgr_orig._cle_detail(match_id), detail_match)
                    jp_orig.historique_matchs.append(mgr_orig._nouvelle_entree(match_data_p, detail_match))
                    jp_orig.cartons_jaunes = 0
                    jp_orig.exclusions_2min = 0
                    jp_orig.cartons_rouges = 0
                    if isinstance(jp_orig, JoueuseDeChamp):
                        jp_orig.buts = 0
                        jp_orig.tirs = 0
                        jp_orig.passes_decisives = 0
                        jp_orig.pertes_de_balles_passe = 0
                        jp_orig.pertes_de_balles_faute = 0
                        jp_orig.duels_off_gagnes = 0
                        jp_orig.duels_off_perdus = 0
                        jp_orig.duels_def_gagnes = 0
                        jp_orig.duels_def_perdus = 0
                        jp_orig.neutralisations = 0
                        jp_orig.interceptions = 0
                        jp_orig.pertes_balles_provoquees = 0
                    elif isinstance(jp_orig, Gardienne):
                        jp_orig.arrets = 0
                        jp_orig.tirs_subis = 0
                        jp_orig.buts_encaisses = 0
                        jp_orig.buts = 0
                        jp_orig.tirs = 0
                    mgr_orig.sauvegarder_donnees(force=True)

    def sauvegarder_commentaire_post_match(self, nom_match, texte_bilan):
        for j in self.joueuses.values():
            for m in j.historique_matchs:
                if m.get("match") == nom_match:
                    m["bilan_post_match"] = texte_bilan
        self.sauvegarder_donnees(force=True)

    @staticmethod
    def recuperer_toutes_les_joueuses_du_club(club_equipes, club_slug=None):
        joueuses_club = {}
        slug = normaliser_slug_club(club_slug)
        for eq in club_equipes or []:
            try:
                data = get_json(slug, get_nom_fichier_equipe(eq), None)
            except Exception:
                continue
            if not isinstance(data, dict):
                continue
            for nom, d in data.items():
                if nom not in joueuses_club and isinstance(d, dict):
                    joueuses_club[nom] = {
                        "equipe_origine": eq,
                        "poste": d.get("poste"),
                        "numero": d.get("numero"),
                        "type": d.get("type"),
                    }
        return joueuses_club

    def transferer_joueuse(self, nom_joueuse, autre_manager):
        if nom_joueuse in self.joueuses:
            joueuse_obj = self.joueuses[nom_joueuse]
            autre_manager.joueuses[nom_joueuse] = joueuse_obj
            autre_manager.sauvegarder_donnees(force=True)
            self.supprimer_joueuse(nom_joueuse)
            return True
        return False

    def ajouter_entree_longitudinale(
        self,
        nom_joueur,
        date_str,
        type_entree="Séance",
        duree_min=60,
        rpe=5,
        forme=3,
        libelle="",
        performance_score=None,
        note="",
    ):
        """Ajoute ou met à jour une entrée charge/forme/performance sur un joueur ou une gardienne."""
        if nom_joueur not in self.joueuses:
            return False

        j = self.joueuses[nom_joueur]
        duree_val = max(0, int(duree_min or 0))
        rpe_val = max(0, min(10, float(rpe if rpe is not None else 0)))
        forme_val = max(1, min(5, float(forme if forme is not None else 3)))
        charge_ua = round(duree_val * rpe_val, 1)

        entree = {
            "date": str(date_str),
            "type": str(type_entree),
            "libelle": str(libelle or type_entree),
            "duree_min": duree_val,
            "rpe": rpe_val,
            "charge_ua": charge_ua,
            "forme": forme_val,
            "performance_score": round(float(performance_score), 1) if performance_score is not None else None,
            "note": str(note or ""),
        }

        if not isinstance(getattr(j, "suivi_longitudinal", None), list):
            j.suivi_longitudinal = []

        # Remplace si même date + même type + même libellé de match pour éviter les doublons
        if type_entree == "Match" and libelle:
            j.suivi_longitudinal = [
                e for e in j.suivi_longitudinal
                if not (e.get("type") == "Match" and e.get("libelle") == libelle)
            ]

        j.suivi_longitudinal.append(entree)
        j.suivi_longitudinal.sort(key=lambda x: str(x.get("date", "")))
        self.sauvegarder_donnees(force=True)
        return True


def calculer_indice_performance_match(match_dict: dict, est_gardienne: bool = False) -> float:
    """Calcule un indice de rendement synthétique (0-100) à partir des stats d'un match archivé."""
    if not isinstance(match_dict, dict):
        return 0.0

    if est_gardienne:
        arrets = float(match_dict.get("arrets", 0) or 0)
        subis = float(match_dict.get("tirs_subis", 0) or 0)
        buts_g = float(match_dict.get("buts", 0) or 0)
        cj = float(match_dict.get("cartons_jaunes", 0) or 0)
        e2 = float(match_dict.get("exclusions_2min", 0) or 0)
        cr = float(match_dict.get("cartons_rouges", 0) or 0)
        pct_arr = (arrets / subis * 100.0) if subis > 0 else 0.0
        score = pct_arr + (buts_g * 3.0) - (cj * 2.0) - (e2 * 4.0) - (cr * 8.0)
        return round(max(0.0, min(100.0, score)), 1)

    buts = float(match_dict.get("buts", 0) or 0)
    tirs = float(match_dict.get("tirs", 0) or 0)
    pd = float(match_dict.get("passes_decisives", 0) or 0)
    inter = float(match_dict.get("interceptions", 0) or 0)
    neut = float(match_dict.get("neutralisations", 0) or 0)
    prov = float(match_dict.get("balles_provoquees", 0) or 0)
    dog = float(match_dict.get("duels_off_gagnes", 0) or 0)
    ddg = float(match_dict.get("duels_def_gagnes", 0) or 0)
    pertes = float(match_dict.get("pertes_passe", 0) or 0) + float(match_dict.get("pertes_faute", 0) or 0)
    dop = float(match_dict.get("duels_off_perdus", 0) or 0)
    ddp = float(match_dict.get("duels_def_perdus", 0) or 0)
    cj = float(match_dict.get("cartons_jaunes", 0) or 0)
    e2 = float(match_dict.get("exclusions_2min", 0) or 0)
    cr = float(match_dict.get("cartons_rouges", 0) or 0)

    eff_tirs = (buts / tirs * 100.0) if tirs > 0 else 50.0
    points_positifs = (buts * 4.0) + (pd * 3.5) + (inter * 2.5) + (neut * 2.0) + (prov * 2.5) + ((dog + ddg) * 1.2)
    points_negatifs = (pertes * 2.5) + ((dop + ddp) * 1.0) + (cj * 2.0) + (e2 * 4.0) + (cr * 8.0)

    # Base neutre à 50, modulée par le volume/efficacité et le solde d'actions
    score = 50.0 + ((eff_tirs - 50.0) * 0.25) + (points_positifs - points_negatifs) * 1.5
    return round(max(0.0, min(100.0, score)), 1)


def resumer_charge_forme_joueur(joueur_obj, date_reference: str | None = None) -> dict:
    """Calcule charge 7j, charge 28j, ratio ACWR, forme moyenne et statut de vigilance."""
    entrees = list(getattr(joueur_obj, "suivi_longitudinal", []) or [])
    if not entrees:
        return {
            "charge_7j": 0.0,
            "moy_hebdo_28j": 0.0,
            "acwr": None,
            "forme_moy": None,
            "dernier_rpe": None,
            "statut": "⚪ Sans donnée",
        }

    try:
        dt_ref = datetime.strptime(str(date_reference), "%Y-%m-%d").date() if date_reference else datetime.now().date()
    except ValueError:
        dt_ref = datetime.now().date()

    seuil_7j = dt_ref - timedelta(days=7)
    seuil_28j = dt_ref - timedelta(days=28)

    charge_7j = 0.0
    charge_28j = 0.0
    formes_recentes = []
    dernier_rpe = None

    for e in sorted(entrees, key=lambda x: str(x.get("date", ""))):
        d_str = str(e.get("date", ""))[:10]
        try:
            d_val = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            d_val = dt_ref

        c_ua = float(e.get("charge_ua") or (float(e.get("duree_min", 0) or 0) * float(e.get("rpe", 0) or 0)))
        if seuil_28j <= d_val <= dt_ref:
            charge_28j += c_ua
        if seuil_7j <= d_val <= dt_ref:
            charge_7j += c_ua
            if e.get("forme") is not None:
                formes_recentes.append(float(e.get("forme")))
        if e.get("rpe") is not None:
            dernier_rpe = float(e.get("rpe"))

    moy_hebdo_28j = round(charge_28j / 4.0, 1)
    acwr = round(charge_7j / moy_hebdo_28j, 2) if moy_hebdo_28j > 0 else None

    if not formes_recentes:
        all_formes = [float(e.get("forme")) for e in entrees if e.get("forme") is not None]
        formes_recentes = all_formes[-5:]

    forme_moy = round(sum(formes_recentes) / len(formes_recentes), 1) if formes_recentes else None

    if (acwr is not None and acwr > 1.5) or (forme_moy is not None and forme_moy <= 2.0):
        statut = "🔴 Vigilance / Charge"
    elif (acwr is not None and (acwr < 0.7 or acwr > 1.3)) or (forme_moy is not None and forme_moy < 3.0):
        statut = "🟠 À surveiller"
    else:
        statut = "🟢 Optimal"

    return {
        "charge_7j": round(charge_7j, 1),
        "moy_hebdo_28j": moy_hebdo_28j,
        "acwr": acwr,
        "forme_moy": forme_moy,
        "dernier_rpe": dernier_rpe,
        "statut": statut,
    }