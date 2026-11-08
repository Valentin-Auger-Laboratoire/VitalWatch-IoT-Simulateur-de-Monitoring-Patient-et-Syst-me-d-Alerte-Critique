"""Simule 6 h de surveillance d'un patient et affiche le journal des alertes.

Usage : python simulateur.py [stable | sepsis | desaturation | capteur | reseau]
"""
import sys

from vitalwatch import simuler_capteur, reseau, surveiller

SCENARIOS = {
    "stable": dict(capteur=dict(scenario="stable"), reseau=dict()),
    "sepsis": dict(capteur=dict(scenario="sepsis"), reseau=dict()),
    "desaturation": dict(capteur=dict(scenario="desaturation"), reseau=dict()),
    "capteur": dict(capteur=dict(scenario="stable", capteur_decroche=[(5400, 90), (9000, 8)]), reseau=dict()),
    "reseau": dict(capteur=dict(scenario="stable"), reseau=dict(perte=0.10, coupures=[(7200, 180)])),
}


def hm(t):
    return f"{int(t // 3600)} h {int(t % 3600 // 60):02d}"


def lancer(nom):
    cfg = SCENARIOS[nom]
    msgs = simuler_capteur(**cfg["capteur"])
    livres = reseau(msgs, **cfg["reseau"])
    mon = surveiller(livres)
    print(f"== Scénario {nom} : {len(msgs)} mesures émises, {len(livres)} reçues, "
          f"{mon.perdus} déclarées perdues, {mon.en_retard} arrivées trop tard")
    if not mon.journal:
        print("   aucune alerte")
    for t, genre, texte in mon.journal:
        print(f"   {hm(t)}  [{genre}] {texte}")
    print(f"   NEWS2 final : {mon.historique_news[-1][1]} ({mon.historique_news[-1][2]})")


if __name__ == "__main__":
    for nom in (sys.argv[1:] or SCENARIOS):
        lancer(nom)
        print()
