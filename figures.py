"""Génère images/sepsis.png (nécessite matplotlib) : python figures.py"""
import json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from vitalwatch import simuler_capteur, reseau, surveiller

msgs = simuler_capteur("sepsis")
mon = surveiller(reseau(msgs))
d = [json.loads(m) for m in msgs]
t = [x["t"] / 3600 for x in d]
fig, ax = plt.subplots(2, 1, figsize=(11, 6), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
for k, lab, c in (("fc", "FC (/min)", "C3"), ("fr", "FR (/min)", "C0"), ("pas", "PAS (mmHg)", "C2"), ("spo2", "SpO2 (%)", "C4")):
    ax[0].plot(t, [x[k] for x in d], c, lw=.8, label=lab)
for tt, genre, txt in mon.journal:
    if genre == "clinique":
        ax[0].axvline(tt / 3600, c="#c8102e", ls="--", lw=.8)
ax[0].set_title("Sepsis simulé : constantes et alarmes de seuil (pointillés)")
ax[0].legend(ncol=4, fontsize=8); ax[0].grid(alpha=.3)
hn = mon.historique_news
ax[1].step([h[0] / 3600 for h in hn], [h[1] for h in hn], where="post", c="k")
ax[1].axhspan(5, 7, color="orange", alpha=.15); ax[1].axhspan(7, 20, color="#c8102e", alpha=.15)
ax[1].set(ylim=(0, 14), xlabel="heures", ylabel="NEWS2", title="NEWS2 : niveau élevé atteint 34 min avant la 1re alarme de seuil")
ax[1].grid(alpha=.3)
fig.tight_layout(); fig.savefig("images/sepsis.png", dpi=120)
