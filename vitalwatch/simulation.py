"""Patient virtuel, capteur connecté et réseau imparfait.

Le capteur publie une mesure toutes les `periode` secondes sous forme de message JSON
(comme sur un bus MQTT). Le réseau perd des messages, les retarde et peut les livrer
dans le désordre. Toutes les données sont simulées.
"""
import json

import numpy as np

BASE = {"fc": 72.0, "fr": 15.0, "spo2": 97.5, "pas": 122.0, "temp": 36.9}
BRUIT = {"fc": 2.0, "fr": 0.8, "spo2": 0.4, "pas": 3.0, "temp": 0.05}


def _rampe(t, debut, duree):
    return float(np.clip((t - debut) / duree, 0, 1))


def constantes(t, scenario):
    """Valeurs « vraies » à l'instant t (s) selon le scénario."""
    v = dict(BASE)
    if scenario == "sepsis":  # dégradation progressive à partir d'1 h, sur 3 h
        k = _rampe(t, 3600, 3 * 3600)
        v.update(fc=72 + 50 * k, fr=15 + 13 * k, pas=122 - 40 * k, temp=36.9 + 2.2 * k, spo2=97.5 - 4 * k)
    elif scenario == "desaturation":  # chute de SpO2 à partir de 2 h
        v["spo2"] = 97.5 - 9 * _rampe(t, 2 * 3600, 20 * 60)
        v["fr"] = 15 + 8 * _rampe(t, 2 * 3600, 20 * 60)
    return v


def simuler_capteur(scenario="stable", duree=6 * 3600, periode=10, graine=0,
                    capteur_decroche=(), conscience_perdue_a=None):
    """Liste des messages émis par le capteur (chaînes JSON), dans l'ordre d'émission.

    capteur_decroche : liste de (début, durée) en s pendant lesquelles l'oxymètre glisse
    du doigt (SpO2 et FC aberrantes : artefact, pas un vrai problème clinique).
    """
    rng = np.random.default_rng(graine)
    msgs = []
    for seq, t in enumerate(np.arange(0, duree, periode)):
        v = constantes(t, scenario)
        mesure = {k: v[k] + BRUIT[k] * rng.standard_normal() for k in v}
        for debut, d in capteur_decroche:
            if debut <= t < debut + d:
                mesure["spo2"] = float(rng.uniform(40, 70))
                mesure["fc"] = float(rng.uniform(0, 30))
        mesure["spo2"] = min(100.0, mesure["spo2"])
        msgs.append(json.dumps({
            "patient": "lit-12", "seq": seq, "t": float(t),
            "fc": round(mesure["fc"]), "fr": round(mesure["fr"]), "spo2": round(mesure["spo2"]),
            "pas": round(mesure["pas"]), "temp": round(mesure["temp"], 1),
            "oxygene": False,
            "conscience": "A" if conscience_perdue_a is None or t < conscience_perdue_a else "V",
        }))
    return msgs


def reseau(messages, perte=0.02, latence=0.4, gigue=0.3, graine=1, coupures=()):
    """Livre les messages comme un réseau sans fil : pertes, retard variable, désordre.

    coupures : liste de (début, durée) en s pendant lesquelles rien ne passe.
    Renvoie la liste de (instant d'arrivée, message) triée par instant d'arrivée.
    """
    rng = np.random.default_rng(graine)
    livres = []
    for m in messages:
        t = json.loads(m)["t"]
        if rng.random() < perte or any(a <= t < a + d for a, d in coupures):
            continue
        livres.append((t + latence + gigue * rng.exponential(), m))
    livres.sort(key=lambda x: x[0])
    return livres

