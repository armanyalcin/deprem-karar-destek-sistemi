"""
Bagimsiz dogrulama (backtest) script'i.

risk_analysis tablosundaki risk_score'lari, elle hazirlanmis harici bir tehlike
referansiyla (il_backtest_referans.csv) karsilastirir. Katalog yalnizca ~3 aylik
oldugu icin olay-bazli backtest yerine harici referansla korelasyon yontemi
kullanilir.

SALT-OKUNUR: yalnizca risk_analysis'ten SELECT yapar ve CSV okur; DB'ye veya koda
hicbir yazma yapmaz. Tek ciktilari konsol ozeti ve backtest_validation.png
(+ opsiyonel backtest_results.csv).

Pipeline'a ve diger dosyalara DOKUNMAZ.
"""

import matplotlib

matplotlib.use("Agg")  # ekran/GUI olmadan PNG uretmek icin
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

from config import get_connection, normalize_city

REFERENCE_CSV = "il_backtest_referans.csv"
OUTPUT_PNG = "backtest_validation.png"
OUTPUT_CSV = "backtest_results.csv"


def load_risk_scores():
    """risk_analysis tablosundan (city, risk_score) okur (read-only)."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT city, risk_score FROM risk_analysis WHERE risk_score IS NOT NULL;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    df = pd.DataFrame(rows, columns=["city", "risk_score"])
    df["risk_score"] = df["risk_score"].astype(float)
    return df


def load_reference():
    df = pd.read_csv(REFERENCE_CSV, encoding="utf-8")
    df["afad_hazard"] = pd.to_numeric(df["afad_hazard"], errors="coerce")
    df["historic_major_eq"] = pd.to_numeric(df["historic_major_eq"], errors="coerce")
    return df


def build_joined():
    risk = load_risk_scores()
    ref = load_reference()

    risk["norm"] = risk["city"].map(normalize_city)
    ref["norm"] = ref["city"].map(normalize_city)

    # Eslesme raporu
    risk_keys, ref_keys = set(risk["norm"]), set(ref["norm"])
    only_risk = risk[risk["norm"].isin(risk_keys - ref_keys)]["city"].tolist()
    only_ref = ref[ref["norm"].isin(ref_keys - risk_keys)]["city"].tolist()
    if only_risk:
        print("UYARI: referansta eslesmeyen risk ili:", only_risk)
    if only_ref:
        print(f"Bilgi: referansta olup risk tablosunda olmayan il(ler) (deprem yok): {only_ref}")

    # risk tablosu surucu; referansi normalize anahtarla ekle
    merged = risk.merge(
        ref[["norm", "afad_hazard", "historic_major_eq"]], on="norm", how="inner"
    )
    print(f"\nEslesen il sayisi: n={len(merged)}")
    return merged


def afad_validation(df):
    rho, p = spearmanr(df["risk_score"], df["afad_hazard"])
    print("\n=== 1. AFAD dogrulamasi (Spearman rank korelasyon) ===")
    print(f"  risk_score vs afad_hazard:  rho = {rho:.3f}   p = {p:.4g}   (n={len(df)})")
    if rho > 0 and p < 0.05:
        print("  -> Anlamli POZITIF uyum: yuksek risk_score'lu iller AFAD tehlike sirasinda da yuksek.")
    elif p >= 0.05:
        print("  -> Korelasyon istatistiksel olarak anlamli degil (p >= 0.05).")
    else:
        print("  -> Beklenmeyen yon (rho <= 0).")
    return rho, p


def historic_validation(df):
    g1 = df[df["historic_major_eq"] == 1]["risk_score"]
    g0 = df[df["historic_major_eq"] == 0]["risk_score"]
    print("\n=== 2. Tarihsel dogrulama (Mann-Whitney U) ===")
    print(f"  Gecmiste M>=6 yasamis (eq=1): n={len(g1)}  ortalama={g1.mean():.3f}  medyan={g1.median():.3f}")
    print(f"  Yasamamis            (eq=0): n={len(g0)}  ortalama={g0.mean():.3f}  medyan={g0.median():.3f}")
    u_greater, p_greater = mannwhitneyu(g1, g0, alternative="greater")
    _, p_two = mannwhitneyu(g1, g0, alternative="two-sided")
    print(f"  Mann-Whitney U (eq1 > eq0, tek yonlu): U={u_greater:.1f}  p={p_greater:.4g}")
    print(f"  (iki yonlu p = {p_two:.4g})")
    if p_greater < 0.05:
        print("  -> Tarihsel buyuk deprem yasamis iller anlamli sekilde DAHA YUKSEK risk_score'a sahip.")
    else:
        print("  -> Iki grup arasinda anlamli fark yok (p >= 0.05).")
    return g1, g0, u_greater, p_greater


def deviation_analysis(df, top_n=8):
    # Farkli olcekler -> yuzdelik sira ile karsilastir
    df = df.copy()
    df["risk_rank_pct"] = df["risk_score"].rank(pct=True)
    df["hazard_rank_pct"] = df["afad_hazard"].rank(pct=True)
    # pozitif: AFAD yuksek, model dusuk (model dusuk tahmin)
    df["deviation"] = df["hazard_rank_pct"] - df["risk_rank_pct"]

    under = df.sort_values("deviation", ascending=False).head(top_n)  # model dusuk tahmin
    over = df.sort_values("deviation", ascending=True).head(top_n)    # model yuksek tahmin

    print("\n=== 3. Sapma analizi (model vs AFAD referansi) ===")
    print("\n  [A] Model OLDUGUNDAN DUSUK tahmin (afad_hazard yuksek, risk_score dusuk):")
    print(f"      {'il':<15}{'risk':>7}{'afad':>6}{'sapma':>8}")
    for _, r in under.iterrows():
        print(f"      {r['city']:<15}{r['risk_score']:>7.3f}{int(r['afad_hazard']):>6}{r['deviation']:>8.3f}")

    print("\n  [B] Model OLDUGUNDAN YUKSEK tahmin (risk_score yuksek, afad_hazard dusuk):")
    print(f"      {'il':<15}{'risk':>7}{'afad':>6}{'sapma':>8}")
    for _, r in over.iterrows():
        print(f"      {r['city']:<15}{r['risk_score']:>7.3f}{int(r['afad_hazard']):>6}{r['deviation']:>8.3f}")

    # Istanbul'u acikca vurgula
    ist = df[df["norm"] == normalize_city("İstanbul")]
    if not ist.empty:
        r = ist.iloc[0]
        taraf = "model DUSUK tahmin" if r["deviation"] > 0 else "model YUKSEK tahmin"
        print(f"\n  >> Istanbul: risk_score={r['risk_score']:.3f}, afad_hazard={int(r['afad_hazard'])}, "
              f"sapma={r['deviation']:.3f}  ->  {taraf}")

    return df, under, over


def make_plot(df, under, over, rho, p):
    rng = np.random.default_rng(42)
    jitter = (rng.random(len(df)) - 0.5) * 0.25  # ayrik afad_hazard icin dikey jitter

    fig, ax = plt.subplots(figsize=(11, 7))
    colors = df["historic_major_eq"].map({1: "#c0392b", 0: "#2980b9"})
    ax.scatter(df["risk_score"], df["afad_hazard"] + jitter, c=colors, alpha=0.7,
               edgecolors="k", linewidths=0.3, s=55)

    # Sapan illeri etiketle
    label_rows = pd.concat([under, over]).drop_duplicates(subset=["city"])
    jitter_map = dict(zip(df["city"], jitter))
    for _, r in label_rows.iterrows():
        ax.annotate(r["city"],
                    (r["risk_score"], r["afad_hazard"] + jitter_map.get(r["city"], 0)),
                    fontsize=8, xytext=(4, 3), textcoords="offset points")

    ax.set_xlabel("Model risk_score (0-1)")
    ax.set_ylabel("AFAD tehlike seviyesi (1-5)")
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_title(f"Backtest: risk_score vs AFAD tehlike  (Spearman rho={rho:.3f}, p={p:.3g})\n"
                 f"kirmizi = gecmiste M>=6 yasamis, mavi = yasamamis; etiketli iller en buyuk sapanlar")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"\nGorsel kaydedildi: {OUTPUT_PNG}")


def main():
    print("Backtest dogrulamasi basliyor (salt-okunur)...")
    df = build_joined()

    rho, p = afad_validation(df)
    historic_validation(df)
    df_dev, under, over = deviation_analysis(df)
    make_plot(df_dev, under, over, rho, p)

    # Opsiyonel sonuc CSV'si (uretilmis cikti; .gitignore *.csv kapsiyor)
    out = df_dev[["city", "risk_score", "afad_hazard", "historic_major_eq",
                  "risk_rank_pct", "hazard_rank_pct", "deviation"]]
    out = out.sort_values("deviation", ascending=False)
    out.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"Sonuc tablosu kaydedildi: {OUTPUT_CSV}")
    print("\nBacktest tamamlandi.")


if __name__ == "__main__":
    main()
