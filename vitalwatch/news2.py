"""Score NEWS2 (National Early Warning Score 2, Royal College of Physicians, 2017).

Barème de l'échelle 1 de SpO2 (patient sans insuffisance respiratoire hypercapnique).
"""


def points_fr(fr):  # fréquence respiratoire (/min)
    if fr <= 8: return 3
    if fr <= 11: return 1
    if fr <= 20: return 0
    if fr <= 24: return 2
    return 3


def points_spo2(spo2):  # %, échelle 1
    if spo2 <= 91: return 3
    if spo2 <= 93: return 2
    if spo2 <= 95: return 1
    return 0


def points_pas(pas):  # pression artérielle systolique (mmHg)
    if pas <= 90: return 3
    if pas <= 100: return 2
    if pas <= 110: return 1
    if pas <= 219: return 0
    return 3


def points_fc(fc):  # fréquence cardiaque (/min)
    if fc <= 40: return 3
    if fc <= 50: return 1
    if fc <= 90: return 0
    if fc <= 110: return 1
    if fc <= 130: return 2
    return 3


def points_temp(t):  # °C
    if t <= 35.0: return 3
    if t <= 36.0: return 1
    if t <= 38.0: return 0
    if t <= 39.0: return 1
    return 2


def news2(fr, spo2, oxygene, pas, fc, conscience_alerte, temp):
    """Renvoie (score total, détail par paramètre)."""
    d = {
        "fr": points_fr(fr),
        "spo2": points_spo2(spo2),
        "oxygene": 2 if oxygene else 0,
        "pas": points_pas(pas),
        "fc": points_fc(fc),
        "conscience": 0 if conscience_alerte else 3,
        "temp": points_temp(temp),
    }
    return sum(d.values()), d


def niveau(score, detail):
    """Niveau de réponse clinique recommandé."""
    if score >= 7:
        return "élevé"
    if score >= 5:
        return "moyen"
    if any(v == 3 for v in detail.values()):
        return "bas-moyen"
    if score >= 1:
        return "bas"
    return "aucun"
