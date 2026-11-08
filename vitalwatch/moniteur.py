"""Moniteur central : réception des messages, alarmes cliniques et techniques, NEWS2.

Règles :
- les messages sont remis dans l'ordre (numéro de séquence) ; un trou qui dure plus de
  `attente` s est compté comme perdu ;
- une alarme clinique ne se déclenche que si la condition dure au moins `persistance` s
  (évite les fausses alarmes sur un pic isolé) et ne s'arrête qu'une fois revenue dans
  la zone normale avec une marge (hystérésis) pendant le même temps ;
- une mesure aberrante d'oxymètre (chute brutale de SpO2 avec FC effondrée) est traitée
  comme un artefact : alarme technique « vérifier le capteur », pas d'alarme clinique ;
- sans message pendant `silence` s : alarme technique « liaison perdue » ;
- NEWS2 calculé toutes les 5 min sur les médianes des 5 dernières minutes valides.
"""
import json
from collections import deque
from statistics import median

from .news2 import news2, niveau

# (paramètre, sens, seuil d'alarme, seuil de retour)
SEUILS = [
    ("fc", "haut", 130, 120), ("fc", "bas", 40, 45),
    ("spo2", "bas", 90, 92),
    ("fr", "haut", 25, 22), ("fr", "bas", 8, 10),
    ("pas", "bas", 90, 95),
    ("temp", "haut", 39.0, 38.5),
]
ORDRE_NIVEAUX = ["aucun", "bas", "bas-moyen", "moyen", "élevé"]


def est_artefact(m, precedent):
    if m["spo2"] < 75 and m["fc"] < 35:
        return True
    return precedent is not None and precedent["spo2"] - m["spo2"] > 15


class Moniteur:
    def __init__(self, periode=10, persistance=30, attente=30, silence=60):
        self.periode, self.persistance, self.attente, self.silence = periode, persistance, attente, silence
        self.journal = []
        self.attendu = 0
        self.tampon = {}
        self.perdus = self.en_retard = self.recus = 0
        self.precedent = None
        self.dernier_t = None
        self.debut = {}      # condition -> instant où elle a commencé à être vraie
        self.actives = set()
        self.fin = {}        # condition active -> instant où elle est redevenue normale
        self.artefact_depuis = None
        self.alarme_capteur = False
        self.fenetre = deque()
        self.prochain_news = 300
        self.niveau = "aucun"
        self.historique_news = []

    def _log(self, t, genre, texte):
        self.journal.append((t, genre, texte))

    # --- réception ---------------------------------------------------------
    def recevoir(self, arrivee, brut):
        m = json.loads(brut)
        self.recus += 1
        if m["seq"] < self.attendu:
            self.en_retard += 1  # arrivé après qu'on l'a déclaré perdu
            return
        self.tampon[m["seq"]] = m
        self._vider(arrivee)

    def _vider(self, maintenant):
        while True:
            if self.attendu in self.tampon:
                self._traiter(self.tampon.pop(self.attendu))
                self.attendu += 1
            elif self.tampon and maintenant - self.attendu * self.periode > self.attente:
                self.perdus += 1  # trou trop long : on n'attend plus ce message
                self.attendu += 1
            else:
                return

    def terminer(self, maintenant):
        self._vider(maintenant + 10 ** 9)

    # --- traitement d'une mesure --------------------------------------------
    def _traiter(self, m):
        t = m["t"]
        if self.dernier_t is not None and t - self.dernier_t > self.silence:
            self._log(self.dernier_t + self.silence, "technique", f"liaison perdue ({t - self.dernier_t:.0f} s sans mesure)")
            self._log(t, "technique", "liaison rétablie")
        self.dernier_t = t
        artefact = est_artefact(m, self.precedent)
        if artefact:
            if self.artefact_depuis is None:
                self.artefact_depuis = t
            if not self.alarme_capteur and t - self.artefact_depuis >= 20:
                self.alarme_capteur = True
                self._log(t, "technique", "oxymètre : signal aberrant, vérifier le capteur")
        else:
            if self.alarme_capteur:
                self._log(t, "technique", "oxymètre : signal correct")
            self.artefact_depuis, self.alarme_capteur = None, False
            self.precedent = m
            self._alarmes(m)
            self.fenetre.append(m)
        while self.fenetre and self.fenetre[0]["t"] < t - 300:
            self.fenetre.popleft()
        if t >= self.prochain_news and self.fenetre:
            self._news(t)
            self.prochain_news += 300

    def _alarmes(self, m):
        t = m["t"]
        for p, sens, seuil, retour in SEUILS:
            cle = (p, sens)
            v = m[p]
            dehors = v > seuil if sens == "haut" else v < seuil
            rentre = v < retour if sens == "haut" else v > retour
            if cle not in self.actives:
                if dehors:
                    self.debut.setdefault(cle, t)
                    if t - self.debut[cle] >= self.persistance:
                        self.actives.add(cle)
                        self._log(t, "clinique", f"ALARME {p} {'trop haute' if sens == 'haut' else 'trop basse'} ({v})")
                else:
                    self.debut.pop(cle, None)
            else:
                if rentre:
                    self.fin.setdefault(cle, t)
                    if t - self.fin[cle] >= self.persistance:
                        self.actives.discard(cle)
                        self.fin.pop(cle)
                        self.debut.pop(cle, None)
                        self._log(t, "clinique", f"fin d'alarme {p} ({v})")
                else:
                    self.fin.pop(cle, None)

    def _news(self, t):
        med = {k: median(x[k] for x in self.fenetre) for k in ("fr", "spo2", "pas", "fc", "temp")}
        alerte = self.fenetre[-1]["conscience"] == "A"
        score, detail = news2(med["fr"], med["spo2"], self.fenetre[-1]["oxygene"], med["pas"], med["fc"], alerte, med["temp"])
        nv = niveau(score, detail)
        self.historique_news.append((t, score, nv))
        if ORDRE_NIVEAUX.index(nv) > ORDRE_NIVEAUX.index(self.niveau):
            self._log(t, "NEWS2", f"score {score} : niveau de réponse {nv}")
        self.niveau = nv


def surveiller(livraisons, **kw):
    mon = Moniteur(**kw)
    for arrivee, msg in livraisons:
        mon.recevoir(arrivee, msg)
    if livraisons:
        mon.terminer(livraisons[-1][0])
    return mon
