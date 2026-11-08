"""Vérifications : python tests/test_vitalwatch.py"""
import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vitalwatch import news2, niveau, simuler_capteur, reseau, surveiller, Moniteur, est_artefact

n_ok = 0


def ok(cond, msg):
    global n_ok
    if not cond:
        raise AssertionError(msg)
    n_ok += 1


# NEWS2 : bornes du barème officiel
cas = [  # (fr, spo2, O2, pas, fc, alerte, temp) -> score attendu
    ((15, 97, False, 120, 70, True, 37.0), 0),
    ((8, 97, False, 120, 70, True, 37.0), 3), ((9, 97, False, 120, 70, True, 37.0), 1),
    ((21, 97, False, 120, 70, True, 37.0), 2), ((25, 97, False, 120, 70, True, 37.0), 3),
    ((15, 91, False, 120, 70, True, 37.0), 3), ((15, 93, False, 120, 70, True, 37.0), 2),
    ((15, 95, False, 120, 70, True, 37.0), 1), ((15, 97, True, 120, 70, True, 37.0), 2),
    ((15, 97, False, 90, 70, True, 37.0), 3), ((15, 97, False, 101, 70, True, 37.0), 1),
    ((15, 97, False, 220, 70, True, 37.0), 3),
    ((15, 97, False, 120, 40, True, 37.0), 3), ((15, 97, False, 120, 51, True, 37.0), 0),
    ((15, 97, False, 120, 111, True, 37.0), 2), ((15, 97, False, 120, 131, True, 37.0), 3),
    ((15, 97, False, 120, 70, False, 37.0), 3),
    ((15, 97, False, 120, 70, True, 35.0), 3), ((15, 97, False, 120, 70, True, 38.5), 1),
    ((15, 97, False, 120, 70, True, 39.1), 2),
    ((26, 90, True, 85, 135, False, 39.5), 3 + 3 + 2 + 3 + 3 + 3 + 2),
]
for args, attendu in cas:
    ok(news2(*args)[0] == attendu, f"NEWS2 {args} = {attendu}")
ok(niveau(*news2(15, 97, False, 120, 70, True, 37.0)) == "aucun", "niveau aucun")
ok(niveau(*news2(15, 97, False, 120, 70, False, 37.0)) == "bas-moyen", "un paramètre à 3 : bas-moyen")
ok(niveau(*news2(22, 94, False, 105, 95, True, 37.0)) == "moyen", "score 5 : moyen")
ok(niveau(*news2(26, 90, True, 85, 135, False, 39.5)) == "élevé", "score ≥ 7 : élevé")


def message(seq, **v):
    m = {"patient": "x", "seq": seq, "t": seq * 10.0, "fc": 72, "fr": 15, "spo2": 97, "pas": 120,
         "temp": 37.0, "oxygene": False, "conscience": "A"}
    m.update(v)
    return json.dumps(m)


def journal(valeurs, cle="spo2", autre=None):
    mon = Moniteur()
    for i, v in enumerate(valeurs):
        mon.recevoir(i * 10.0, message(i, **{cle: v, **(autre or {})}))
    return [j for j in mon.journal if j[1] == "clinique"]


# Persistance : un pic de 20 s ne déclenche rien, 40 s si
ok(journal([97] * 5 + [88] * 2 + [97] * 5) == [], "pic bref : pas d'alarme")
ok(sum("ALARME" in x[2] for x in journal([97] * 5 + [88] * 5 + [97] * 5)) == 1, "désaturation de 50 s : alarme")
# Hystérésis : valeur qui oscille autour du seuil -> une seule alarme, pas de clignotement
osc = [97] * 3 + [88] * 4 + [91, 89] * 10
j = journal(osc)
ok(len(j) == 1 and "ALARME" in j[0][2], "oscillation autour du seuil : une seule alarme")
j = journal([88] * 5 + [95] * 6)
ok([x[2].split()[0] for x in j] == ["ALARME", "fin"], "retour durable dans la zone normale : fin d'alarme")

# Artefact d'oxymètre : alarme technique, jamais clinique
ok(est_artefact({"spo2": 55, "fc": 20}, None) and not est_artefact({"spo2": 88, "fc": 80}, {"spo2": 90, "fc": 80}),
   "reconnaissance d'artefact")
mon = Moniteur()
for i in range(20):
    bad = 5 <= i < 12
    mon.recevoir(i * 10.0, message(i, spo2=50 if bad else 97, fc=10 if bad else 72))
ok(not [x for x in mon.journal if x[1] == "clinique"], "artefact : pas d'alarme clinique")
ok(any("vérifier le capteur" in x[2] for x in mon.journal), "artefact : alarme technique")

# Réseau : remise dans l'ordre, pertes comptées, silence détecté
msgs = simuler_capteur("sepsis", duree=4 * 3600, graine=3)
liv = reseau(msgs, perte=0.0, gigue=0.0)
ref = surveiller(liv).journal
melange = list(liv)
random.Random(0).shuffle(melange)
desordre = sorted(((a + random.Random(i).uniform(0, 15), m) for i, (a, m) in enumerate(liv)), key=lambda x: x[0])
ok(surveiller(desordre).journal == ref, "messages livrés dans le désordre : même journal")
liv = reseau(msgs, perte=0.1, graine=5)
mon = surveiller(liv)
ok(mon.perdus == len(msgs) - len(liv), "chaque message manquant est compté une fois")
mon = surveiller(reseau(simuler_capteur("stable", duree=3600), perte=0, coupures=[(1200, 200)]))
ok(any("liaison perdue" in x[2] for x in mon.journal), "coupure de 200 s : liaison perdue")
mon = surveiller(reseau(simuler_capteur("stable", duree=3600), perte=0, coupures=[(1200, 40)]))
ok(not any("liaison perdue" in x[2] for x in mon.journal), "coupure de 40 s : pas d'alarme")

# Scénarios complets
for g in range(5):
    mon = surveiller(reseau(simuler_capteur("stable", graine=g), graine=g))
    ok(mon.journal == [], f"patient stable : aucune alerte (graine {g})")
mon = surveiller(reseau(simuler_capteur("sepsis")))
t_news = next(t for t, genre, txt in mon.journal if genre == "NEWS2" and "élevé" in txt)
t_alarme = next(t for t, genre, txt in mon.journal if genre == "clinique")
ok(t_news < t_alarme - 15 * 60, "sepsis : NEWS2 élevé plus de 15 min avant la première alarme de seuil")
mon = surveiller(reseau(simuler_capteur("stable", conscience_perdue_a=3600)))
ok(any("bas-moyen" in x[2] for x in mon.journal), "perte de conscience : NEWS2 bas-moyen")

print(f"{n_ok} vérifications réussies")
