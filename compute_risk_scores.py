"""
Risk skoru hesaplama adimi.

Risk = tehlike x maruziyet mantigiyla uc bilesenli bir skor uretir ve
risk_analysis tablosunu yeniden doldurur:

  (a) Aktivite  -> city_features (total_earthquakes, magnitude_over_3_count,
                   magnitude_over_4_count, max_magnitude)
  (b) b-degeri  -> earthquakes tablosundaki ham magnitude dagilimi
                   (Gutenberg-Richter, Aki-Utsu MLE)
  (c) Nufus     -> il_nufus.csv

Seffaflik icin risk_analysis sadece final skoru degil, her bilesenin
alt-skorunu ve ham b-degerini de saklar.

Bu script run_pipeline.py icinde build_city_features.py'dan SONRA calisir.
"""

import math
import warnings

import numpy as np
import pandas as pd

from config import get_connection, normalize_city

# pd.read_sql psycopg2 baglantisiyla calisir ama SQLAlchemy oneren kozmetik bir
# UserWarning uretir; proje genelinde psycopg2 kullanildigi icin bastiriyoruz.
warnings.filterwarnings("ignore", message="pandas only supports SQLAlchemy")

# --- Degistirilebilir sabitler -------------------------------------------------
# Bilesen agirliklari (baslangicta esit). Toplamlari 1 olmasi zorunlu degil;
# istenirse biri 0 yapilip etki devre disi birakilabilir.
W_ACTIVITY = 1 / 4
W_BVALUE = 1 / 4
W_POPULATION = 1 / 4
W_FAULT = 1 / 4

# Tamamlik magnitudu Mc. None ise katalogtan MAXC (maximum curvature) + 0.2
# ile otomatik hesaplanir. Sabit deger vermek istersen (ornegin 1.4) ata.
MC = 1.4

DELTA_M = 0.1  # Katalog magnitude bin genisligi (AFAD verisi 0.1 hassasiyette)

# Bir sehrin kendi b-degerinin hesaplanmasi icin gereken minimum, Mc ustu
# (M >= Mc) olay sayisi. Bunun altindaki sehirler ulke geneli b-degerini
# (fallback) alir.
B_MIN_EVENTS = 50

# Il olmayan / yurt disi kayitlar (deniz bolgeleri, komsu ulkeler). Risk
# hesabina alinmaz. Normalize anahtarla karsilastirilir.
EXCLUDED_PLACES = {
    "Akdeniz", "Karadeniz", "Yunanistan", "Ege Denizi",
    "Kuzey Kıbrıs Türk Cumhuriyeti", "Güney Kıbrıs Rum Yönetimi", "Azerbaycan",
}

LOG10_E = math.log10(math.e)  # ~0.4342944819


# --- Veri okuma ----------------------------------------------------------------
def fetch_city_features(conn):
    """Aktivite bilesenini ve tamamlayici istatistikleri saglayan surucu tablo."""
    query = """
        SELECT
            city,
            total_earthquakes,
            avg_magnitude,
            max_magnitude,
            avg_depth,
            magnitude_over_3_count,
            magnitude_over_4_count
        FROM city_features
        ORDER BY total_earthquakes DESC;
    """
    return pd.read_sql(query, conn)


def fetch_magnitudes(conn):
    """earthquakes tablosundaki ham (city, magnitude) ciftleri (b-degeri icin)."""
    query = """
        SELECT city, magnitude
        FROM earthquakes
        WHERE city IS NOT NULL AND TRIM(city) <> '' AND magnitude IS NOT NULL;
    """
    df = pd.read_sql(query, conn)
    df["magnitude"] = pd.to_numeric(df["magnitude"], errors="coerce")
    df = df.dropna(subset=["magnitude"])

    excluded_keys = {normalize_city(p) for p in EXCLUDED_PLACES}
    df["norm"] = df["city"].map(normalize_city)
    df = df[~df["norm"].isin(excluded_keys)].copy()
    return df


def load_population(path="il_nufus.csv"):
    df = pd.read_csv(path, encoding="utf-8")
    df["norm"] = df["city"].map(normalize_city)
    return dict(zip(df["norm"], df["population"]))


def load_fault(path="il_fay.csv"):
    """Fay yakinligi verisi: {norm: (fault_zone, fault_score)}."""
    df = pd.read_csv(path, encoding="utf-8")
    df["norm"] = df["city"].map(normalize_city)
    df["fault_score"] = pd.to_numeric(df["fault_score"], errors="coerce")
    return {r["norm"]: (r["fault_zone"], r["fault_score"]) for _, r in df.iterrows()}


# --- b-degeri hesabi -----------------------------------------------------------
def determine_mc(magnitudes):
    """MAXC (maximum curvature): non-cumulative FMD'nin modu + 0.2 duzeltme."""
    mags = np.asarray(magnitudes, dtype=float)
    if mags.size == 0:
        return None
    # 0.1 binli histogram; en yogun bin = mod
    rounded = np.round(mags / DELTA_M) * DELTA_M
    values, counts = np.unique(np.round(rounded, 1), return_counts=True)
    mode_mag = values[np.argmax(counts)]
    return round(float(mode_mag) + 0.2, 1)


def aki_utsu_b(magnitudes, mc):
    """
    Aki-Utsu maximum likelihood b-degeri (binli duzeltmeli):
        b = log10(e) / ( mean(M) - (Mc - dM/2) )
    Sadece M >= Mc olaylar kullanilir. Yetersiz/gecersiz veride None doner.
    """
    mags = np.asarray(magnitudes, dtype=float)
    above = mags[mags >= mc - 1e-9]
    n = above.size
    if n == 0:
        return None, 0
    mean_m = above.mean()
    denom = mean_m - (mc - DELTA_M / 2.0)
    if denom <= 0:
        return None, n
    return LOG10_E / denom, n


# --- Normalizasyon (skor) ------------------------------------------------------
def log1p_minmax(series):
    """log1p donusumu + 0-1 min-max normalizasyon. Tum degerler esitse 0.0."""
    vals = np.log1p(series.astype(float).fillna(0.0).clip(lower=0))
    lo, hi = vals.min(), vals.max()
    if hi - lo < 1e-12:
        return pd.Series(np.zeros(len(vals)), index=series.index)
    return (vals - lo) / (hi - lo)


# --- DB yazimi -----------------------------------------------------------------
NEW_COLUMNS = [
    ("population", "BIGINT"),
    ("b_value", "NUMERIC"),
    ("b_is_fallback", "BOOLEAN"),
    ("activity_score", "NUMERIC"),
    ("bvalue_score", "NUMERIC"),
    ("population_score", "NUMERIC"),
    ("fault_zone", "VARCHAR"),
    ("fault_score", "NUMERIC"),
]


def ensure_columns(cur):
    """Seffaflik kolonlarini idempotent ekler (app.py'nin kolonlari korunur)."""
    for name, coltype in NEW_COLUMNS:
        cur.execute(f"ALTER TABLE risk_analysis ADD COLUMN IF NOT EXISTS {name} {coltype};")


def write_risk_analysis(conn, df):
    cur = conn.cursor()
    ensure_columns(cur)
    cur.execute("DELETE FROM risk_analysis;")

    insert = """
        INSERT INTO risk_analysis (
            city, district, total_earthquakes,
            avg_magnitude, max_magnitude, avg_depth,
            population, b_value, b_is_fallback,
            activity_score, bvalue_score, population_score,
            fault_zone, fault_score,
            risk_score, calculated_at
        )
        VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP);
    """

    def num(v):
        return None if pd.isna(v) else float(v)

    for _, r in df.iterrows():
        cur.execute(insert, (
            r["city"],
            int(r["total_earthquakes"]),
            num(r["avg_magnitude"]),
            num(r["max_magnitude"]),
            num(r["avg_depth"]),
            None if pd.isna(r["population"]) else int(r["population"]),
            num(r["b_value"]),
            bool(r["b_is_fallback"]),
            round(float(r["activity_score"]), 4),
            round(float(r["bvalue_score"]), 4),
            round(float(r["population_score"]), 4),
            None if pd.isna(r["fault_zone"]) else str(r["fault_zone"]),
            num(r["fault_score"]),
            round(float(r["risk_score"]), 4),
        ))

    conn.commit()
    cur.close()


# --- Ana akis ------------------------------------------------------------------
def main():
    print("Risk skoru hesaplaniyor...")
    conn = get_connection()

    features = fetch_city_features(conn)
    quakes = fetch_magnitudes(conn)
    population = load_population()
    fault = load_fault()

    if features.empty:
        print("city_features bos. Once build_city_features.py calistirin.")
        conn.close()
        return

    # Mc belirle (sabit ya da MAXC)
    mc = MC if MC is not None else determine_mc(quakes["magnitude"].values)
    maxc_ref = determine_mc(quakes["magnitude"].values)
    print(f"Tamamlik magnitudu Mc = {mc}  (referans MAXC+0.2 = {maxc_ref})")

    # Ulke geneli b-degeri (fallback)
    country_b, country_n = aki_utsu_b(quakes["magnitude"].values, mc)
    if country_b is None:
        raise RuntimeError("Ulke geneli b-degeri hesaplanamadi (M>=Mc olay yok).")
    print(f"Ulke geneli b-degeri (fallback) = {country_b:.3f}  (M>=Mc olay: {country_n})")

    # Sehir bazli ham magnitude listeleri (normalize anahtarla)
    mags_by_city = quakes.groupby("norm")["magnitude"].apply(list).to_dict()

    features["norm"] = features["city"].map(normalize_city)

    b_values, b_fallbacks = [], []
    for key in features["norm"]:
        city_mags = mags_by_city.get(key, [])
        b, n_above = aki_utsu_b(city_mags, mc) if city_mags else (None, 0)
        if b is not None and n_above >= B_MIN_EVENTS:
            b_values.append(b)
            b_fallbacks.append(False)
        else:
            b_values.append(country_b)
            b_fallbacks.append(True)

    features["b_value"] = b_values
    features["b_is_fallback"] = b_fallbacks
    features["population"] = features["norm"].map(population)

    # Nufusu eslesmeyen kayitlar il degildir (deniz bolgesi / yurt disi gibi
    # eski/artik city_features satirlari) ya da maruziyet bileseni hesaplanamaz.
    # Bunlari risk disi birakiyoruz; hangileri oldugunu acikca raporluyoruz.
    no_pop = features[features["population"].isna()]["city"].tolist()
    if no_pop:
        print("Nufus eslesmedi, risk disi birakildi (il degil/maruziyet yok):", no_pop)
        features = features[features["population"].notna()].copy()

    # Fay yakinligi (il-disi artiklar elendikten sonra; uyari yalniz gercek illeri kontrol eder)
    features["fault_zone"] = features["norm"].map(lambda k: fault.get(k, (None, None))[0])
    features["fault_score"] = features["norm"].map(lambda k: fault.get(k, (None, None))[1])
    no_fault = features[features["fault_score"].isna()]["city"].tolist()
    if no_fault:
        print("UYARI: fay verisi eslesmeyen sehir(ler):", no_fault)

    # --- Alt-skorlar ---
    # (a) Aktivite: dort metrigin her birini log1p+minmax edip ortalamak
    activity_cols = [
        "total_earthquakes", "magnitude_over_3_count",
        "magnitude_over_4_count", "max_magnitude",
    ]
    activity_parts = pd.DataFrame(
        {c: log1p_minmax(features[c]) for c in activity_cols}
    )
    features["activity_score"] = activity_parts.mean(axis=1)

    # (b) b-degeri: dusuk b = yuksek tehlike -> TERS cevir
    features["bvalue_score"] = 1.0 - log1p_minmax(features["b_value"])

    # (c) Nufus
    features["population_score"] = log1p_minmax(features["population"])

    # (d) Fay yakinligi: fault_score zaten 0-1 araliginda KATEGORIK bir skor
    # (0/0.5/1.0) oldugu icin log1p/minmax UYGULANMAZ; dogrudan bilesen olarak
    # kullanilir. Eksik veride 0.0 kabul edilir.
    fault_component = features["fault_score"].astype(float).fillna(0.0)

    # Final agirlikli toplam (4 bilesen)
    features["risk_score"] = (
        W_ACTIVITY * features["activity_score"]
        + W_BVALUE * features["bvalue_score"]
        + W_POPULATION * features["population_score"]
        + W_FAULT * fault_component
    )

    features = features.sort_values("risk_score", ascending=False).reset_index(drop=True)

    write_risk_analysis(conn, features)
    conn.close()

    # Opsiyonel CSV ciktisi (diger scriptlerle tutarli; .gitignore *.csv kapsiyor)
    out_cols = [
        "city", "risk_score", "activity_score", "bvalue_score",
        "population_score", "fault_score", "fault_zone", "b_value",
        "b_is_fallback", "population", "total_earthquakes",
    ]
    features[out_cols].to_csv("risk_scores.csv", index=False, encoding="utf-8-sig")

    own_b = int((~features["b_is_fallback"]).sum())
    print(f"\nToplam {len(features)} il islendi "
          f"({own_b} il kendi b-degeri, {len(features) - own_b} il fallback).")
    print("\nEn yuksek 10 risk:")
    print(features[["city", "risk_score", "activity_score", "bvalue_score",
                    "population_score", "fault_score"]].head(10).to_string(index=False))
    print("\nrisk_analysis tablosu guncellendi. risk_scores.csv olusturuldu.")


if __name__ == "__main__":
    main()
