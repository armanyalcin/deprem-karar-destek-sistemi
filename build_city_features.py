import pandas as pd

from config import get_connection

VALID_CITIES = {
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Amasya", "Ankara", "Antalya",
    "Artvin", "Aydın", "Balıkesir", "Bilecik", "Bingöl", "Bitlis", "Bolu",
    "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", "Denizli", "Diyarbakır",
    "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", "Gaziantep", "Giresun",
    "Gümüşhane", "Hakkâri", "Hatay", "Isparta", "Mersin", "İstanbul", "İzmir",
    "Kars", "Kastamonu", "Kayseri", "Kırklareli", "Kırşehir", "Kocaeli", "Konya",
    "Kütahya", "Malatya", "Manisa", "Kahramanmaraş", "Mardin", "Muğla", "Muş",
    "Nevşehir", "Niğde", "Ordu", "Rize", "Sakarya", "Samsun", "Siirt", "Sinop",
    "Sivas", "Tekirdağ", "Tokat", "Trabzon", "Tunceli", "Şanlıurfa", "Uşak",
    "Van", "Yozgat", "Zonguldak", "Aksaray", "Bayburt", "Karaman", "Kırıkkale",
    "Batman", "Şırnak", "Bartın", "Ardahan", "Iğdır", "Yalova", "Karabük",
    "Kilis", "Osmaniye", "Düzce"
}

def fetch_city_features():
    conn = get_connection()

    query = """
    SELECT
        city,
        COUNT(*) AS total_earthquakes,
        ROUND(AVG(magnitude)::numeric, 2) AS avg_magnitude,
        MAX(magnitude) AS max_magnitude,
        ROUND(AVG(depth_km)::numeric, 2) AS avg_depth,
        COUNT(*) FILTER (
            WHERE event_date >= CURRENT_DATE - INTERVAL '7 days'
        ) AS recent_7d_count,
        COUNT(*) FILTER (
            WHERE event_date >= CURRENT_DATE - INTERVAL '30 days'
        ) AS recent_30d_count,
        COUNT(*) FILTER (
            WHERE magnitude >= 3.0
        ) AS magnitude_over_3_count,
        COUNT(*) FILTER (
            WHERE magnitude >= 4.0
        ) AS magnitude_over_4_count
    FROM earthquakes
    WHERE city IS NOT NULL
      AND TRIM(city) <> ''
    GROUP BY city
    ORDER BY total_earthquakes DESC;
    """

    df = pd.read_sql(query, conn)
    conn.close()

    df["city"] = df["city"].astype(str).str.strip()
    df = df[df["city"].isin(VALID_CITIES)].copy()

    return df

def save_to_csv(df: pd.DataFrame):
    df.to_csv("city_features.csv", index=False, encoding="utf-8-sig")
    print("city_features.csv oluşturuldu.")

def save_to_postgres(df: pd.DataFrame):
    conn = get_connection()
    cur = conn.cursor()

    for _, row in df.iterrows():
        cur.execute("""
            INSERT INTO city_features (
                city,
                total_earthquakes,
                avg_magnitude,
                max_magnitude,
                avg_depth,
                recent_7d_count,
                recent_30d_count,
                magnitude_over_3_count,
                magnitude_over_4_count,
                last_calculated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (city)
            DO UPDATE SET
                total_earthquakes = EXCLUDED.total_earthquakes,
                avg_magnitude = EXCLUDED.avg_magnitude,
                max_magnitude = EXCLUDED.max_magnitude,
                avg_depth = EXCLUDED.avg_depth,
                recent_7d_count = EXCLUDED.recent_7d_count,
                recent_30d_count = EXCLUDED.recent_30d_count,
                magnitude_over_3_count = EXCLUDED.magnitude_over_3_count,
                magnitude_over_4_count = EXCLUDED.magnitude_over_4_count,
                last_calculated_at = CURRENT_TIMESTAMP;
        """, (
            row["city"],
            int(row["total_earthquakes"]),
            float(row["avg_magnitude"]) if pd.notna(row["avg_magnitude"]) else None,
            float(row["max_magnitude"]) if pd.notna(row["max_magnitude"]) else None,
            float(row["avg_depth"]) if pd.notna(row["avg_depth"]) else None,
            int(row["recent_7d_count"]),
            int(row["recent_30d_count"]),
            int(row["magnitude_over_3_count"]),
            int(row["magnitude_over_4_count"]),
        ))

    conn.commit()
    cur.close()
    conn.close()
    print("city_features tablosu güncellendi.")

def main():
    print("Şehir bazlı özellikler hesaplanıyor...")
    df = fetch_city_features()

    print("\nİlk 10 satır:")
    print(df.head(10))

    save_to_csv(df)
    save_to_postgres(df)

    print("\nToplam şehir sayısı:", len(df))
    print("İşlem tamamlandı.")

if __name__ == "__main__":
    main()