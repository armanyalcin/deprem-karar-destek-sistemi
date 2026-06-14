"""
Optimal k karar-destek analizi (standalone).

KMeans kume sayisi (k) secimini istatistiksel olarak gerekcelendirir:
  - Elbow yontemi (inertia)
  - Silhouette skoru
k = 2..8 araliginda taranir.

ONEMLI: Bu script pipeline'a (run_pipeline.py) dahil DEGILDIR ve mevcut modeli
(train_clustering_model.py, k=3) DEGISTIRMEZ. Yalnizca analiz/raporlama yapar.

Feature kolonlari ve olcekleme, train_clustering_model.py ile BIREBIR aynidir.
"""

import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt

# train_clustering_model.py ile birebir ayni feature listesi (satir 14-23)
FEATURE_COLS = [
    "total_earthquakes",
    "avg_magnitude",
    "max_magnitude",
    "avg_depth",
    "recent_7d_count",
    "recent_30d_count",
    "magnitude_over_3_count",
    "magnitude_over_4_count",
]

K_RANGE = range(2, 9)          # k = 2..8
CURRENT_K = 3                  # mevcut modeldeki secim (degistirilmez)
RANDOM_STATE = 42
N_INIT = 10
OUTPUT_PNG = "optimal_k_analysis.png"


def load_scaled_features():
    """city_features.csv'yi okur ve train script'iyle ayni on isleme/olceklemeyi uygular."""
    df = pd.read_csv("city_features.csv")

    # train_clustering_model.py:25-26 ile ayni: secim + fillna(0)
    X = df[FEATURE_COLS].copy()
    X = X.fillna(0)

    # train_clustering_model.py:28-29 ile ayni: StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    return df, X, X_scaled


def scan_k(X_scaled):
    """Her k icin inertia ve ortalama silhouette skorunu hesaplar."""
    results = []
    for k in K_RANGE:
        kmeans = KMeans(n_clusters=k, random_state=RANDOM_STATE, n_init=N_INIT)
        labels = kmeans.fit_predict(X_scaled)
        sil = silhouette_score(X_scaled, labels)
        results.append({"k": k, "inertia": kmeans.inertia_, "silhouette": sil})
    return pd.DataFrame(results)


def plot_results(res):
    """Elbow (inertia) ve silhouette egrilerini tek figurde, iki panelde cizer."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

    # Sol panel: Elbow (k vs inertia)
    ax1.plot(res["k"], res["inertia"], "o-", color="#1f77b4")
    ax1.axvline(CURRENT_K, color="red", linestyle="--", alpha=0.7,
                label=f"mevcut k={CURRENT_K}")
    ax1.set_title("Elbow Yontemi (Inertia)")
    ax1.set_xlabel("Kume sayisi (k)")
    ax1.set_ylabel("Inertia (WCSS)")
    ax1.set_xticks(list(K_RANGE))
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Sag panel: Silhouette (k vs ortalama silhouette)
    ax2.plot(res["k"], res["silhouette"], "o-", color="#2ca02c")
    ax2.axvline(CURRENT_K, color="red", linestyle="--", alpha=0.7,
                label=f"mevcut k={CURRENT_K}")
    best_k = int(res.loc[res["silhouette"].idxmax(), "k"])
    ax2.axvline(best_k, color="orange", linestyle=":", alpha=0.9,
                label=f"en yuksek silhouette k={best_k}")
    ax2.set_title("Silhouette Skoru")
    ax2.set_xlabel("Kume sayisi (k)")
    ax2.set_ylabel("Ortalama silhouette skoru")
    ax2.set_xticks(list(K_RANGE))
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.suptitle("Optimal k analizi (k=2..8)", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUTPUT_PNG, dpi=150)
    print(f"\nGrafik kaydedildi: {OUTPUT_PNG}")


def print_summary(res):
    """Konsola hizalanmis ozet tablo ve onerilen k yorumunu basar."""
    print("\n" + "=" * 48)
    print("OZET TABLO (k = 2..8)")
    print("=" * 48)
    print(f"{'k':>3} | {'inertia':>12} | {'silhouette':>11}")
    print("-" * 48)
    for _, row in res.iterrows():
        marker = "  <- mevcut" if int(row["k"]) == CURRENT_K else ""
        print(f"{int(row['k']):>3} | {row['inertia']:>12.2f} | "
              f"{row['silhouette']:>11.4f}{marker}")

    best_k = int(res.loc[res["silhouette"].idxmax(), "k"])
    best_sil = res["silhouette"].max()
    current_sil = float(res.loc[res["k"] == CURRENT_K, "silhouette"].iloc[0])

    print("\n" + "=" * 48)
    print("YORUM (karar-destek)")
    print("=" * 48)
    print(f"Veriye gore onerilen k (en yuksek silhouette): k={best_k} "
          f"(silhouette={best_sil:.4f})")
    print(f"Mevcut secim: k={CURRENT_K} (silhouette={current_sil:.4f})")

    if best_k == CURRENT_K:
        print(f"-> Silhouette, mevcut k={CURRENT_K} secimini DOGRULUYOR.")
    else:
        print(f"-> Silhouette en yuksek degeri k={best_k}'de veriyor; "
              f"k={CURRENT_K} ile fark: {best_sil - current_sil:+.4f}.")
        print("   k degisikligi cluster etiketleme mantigini etkiler "
              "(app.py get_cluster_label_map); karar kullaniciya birakilir.")
    print("Not: Elbow egrisinde 'dirsek' noktasini sol paneldeki grafikten "
          "gorsel olarak da degerlendirin.")


def print_skew_note(X):
    """Feature dagilimi hakkinda kisa carpiklik (skew) gozlemi."""
    skew = X.skew().sort_values(ascending=False)
    print("\n" + "=" * 48)
    print("DAGILIM NOTU (carpiklik / skewness) - sadece gozlem")
    print("=" * 48)
    for col, val in skew.items():
        flag = "  [yuksek saga-carpik]" if val > 2 else ""
        print(f"{col:>24}: skew = {val:>7.2f}{flag}")
    print("\nGozlem: 'total_earthquakes' gibi feature'lar birkac sehirde asiri")
    print("yuksek (orn. Malatya ~1005). StandardScaler sonrasi bile bu uc")
    print("sehirler merkezden uzakta kalir; KMeans bunlari kendi kumesine")
    print("ayirma egilimindedir. Bu durum silhouette skorunu yapay olarak")
    print("yukseltebilir (gercek ayrisma degil, outlier izolasyonu). Bu")
    print("yalnizca bir gozlemdir; bu adimda veriye mudahale edilmez.")


def main():
    print("Optimal k analizi basliyor (k=2..8)...")
    df, X, X_scaled = load_scaled_features()
    print(f"{len(df)} sehir, {len(FEATURE_COLS)} feature okundu ve olceklendi.")

    res = scan_k(X_scaled)
    print_summary(res)
    print_skew_note(X)
    plot_results(res)
    print("\nAnaliz tamamlandi. (Mevcut model ve pipeline degistirilmedi.)")


if __name__ == "__main__":
    main()
