from io import StringIO
import re
import time
from datetime import datetime, date, timedelta
from typing import Optional, Tuple

import pandas as pd
import requests

from config import get_connection

AFAD_API_URL = "https://servisnet.afad.gov.tr/apigateway/deprem/apiv2/event/filter"
AFAD_HTML_URL = "https://deprem.afad.gov.tr/last-earthquakes.html"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "text/html,application/json",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache"
}

def parse_location(location_text: str) -> Tuple[Optional[str], Optional[str]]:
    if pd.isna(location_text):
        return None, None

    text = str(location_text).strip()
    if not text:
        return None, None

    m = re.search(r"([^()]+)\(([^)]+)\)\s*$", text)
    if m:
        district = m.group(1).strip()
        city = m.group(2).strip()
        return city, district

    return text, None

def first_existing(row, possible_names):
    for name in possible_names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return None

def fetch_afad_api() -> pd.DataFrame:
    today = date.today()

    # Sadece bugünü değil, son 2 günü çekiyoruz.
    # Böylece saat/gecikme farklarında veri kaçırma ihtimali azalır.
    start_date = today - timedelta(days=1)

    params = {
        "start": f"{start_date}T00:00:00",
        "end": f"{today}T23:59:59",
        "orderby": "timedesc",
        "limit": 500
    }

    response = requests.get(
        AFAD_API_URL,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    print("API istek URL:", response.url)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, dict):
        if "data" in data:
            records = data["data"]
        elif "result" in data:
            records = data["result"]
        else:
            records = [data]
    else:
        records = data

    df_raw = pd.DataFrame(records)

    if df_raw.empty:
        print("AFAD API bos veri dondurdu.")
        return pd.DataFrame()

    rows = []

    for _, row in df_raw.iterrows():
        event_datetime = first_existing(row, [
            "date", "time", "eventDate", "event_date", "event_datetime", "eventTime"
        ])

        latitude = first_existing(row, ["latitude", "lat", "enlem"])
        longitude = first_existing(row, ["longitude", "lon", "lng", "boylam"])
        depth_km = first_existing(row, ["depth", "depth_km", "derinlik"])
        magnitude = first_existing(row, ["magnitude", "mag", "buyukluk"])
        magnitude_type = first_existing(row, ["type", "magnitudeType", "magType"])

        location_text = first_existing(row, [
            "location", "place", "yer", "locationText"
        ])

        province = first_existing(row, ["province"])
        district = first_existing(row, ["district"])

        if province:
            city = str(province).strip()
            district_value = None if pd.isna(district) else str(district).strip()
        else:
            city, district_value = parse_location(location_text)

        event_id = first_existing(row, ["eventID", "eventId", "id", "event_id"])

        rows.append({
            "event_datetime": event_datetime,
            "latitude": latitude,
            "longitude": longitude,
            "depth_km": depth_km,
            "magnitude": magnitude,
            "magnitude_type": magnitude_type,
            "location_text": location_text,
            "city": city,
            "district": district_value,
            "afad_event_id": event_id,
            "data_source_type": "API"
        })

    df = pd.DataFrame(rows)

    df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
    df["event_date"] = df["event_datetime"].dt.date
    df["event_time"] = df["event_datetime"].dt.time

    for col in ["latitude", "longitude", "depth_km", "magnitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["source_id"] = 1

    df = df.dropna(subset=[
        "event_date", "event_time", "latitude", "longitude", "magnitude"
    ])

    return df

def fetch_afad_html() -> pd.DataFrame:
    # Cache kırmak için URL sonuna zaman damgası ekliyoruz
    params = {
        "_": int(time.time())
    }

    response = requests.get(
        AFAD_HTML_URL,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    print("HTML istek URL:", response.url)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"

    html = response.text

    try:
        tables = pd.read_html(StringIO(html))
    except Exception as e:
        print("HTML tablo okunamadi:", e)
        return pd.DataFrame()

    if not tables:
        print("HTML kaynakta tablo bulunamadi.")
        return pd.DataFrame()

    df = tables[0].copy()

    rename_map = {
        "Tarih(TS)": "event_datetime",
        "Enlem": "latitude",
        "Boylam": "longitude",
        "Derinlik(Km)": "depth_km",
        "Büyüklük": "magnitude",
        "Yer": "location_text",
        "Tip": "magnitude_type",
        "Deprem Id": "afad_event_id",
    }

    df.rename(columns=rename_map, inplace=True)

    if "event_datetime" not in df.columns:
        print("HTML beklenen sutunlari dondurmedi:", list(df.columns))
        return pd.DataFrame()

    df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
    df["event_date"] = df["event_datetime"].dt.date
    df["event_time"] = df["event_datetime"].dt.time

    for col in ["latitude", "longitude", "depth_km", "magnitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    parsed = df["location_text"].apply(parse_location)
    df["city"] = parsed.apply(lambda x: x[0])
    df["district"] = parsed.apply(lambda x: x[1])

    df["source_id"] = 1
    df["data_source_type"] = "HTML"

    df = df.dropna(subset=[
        "event_date", "event_time", "latitude", "longitude", "magnitude"
    ])

    return df

def fetch_afad_combined() -> pd.DataFrame:
    print("AFAD API verisi cekiliyor...")
    api_df = fetch_afad_api()

    print("AFAD Son Depremler HTML verisi cekiliyor...")
    html_df = fetch_afad_html()

    if not api_df.empty:
        print("API kayit sayisi:", len(api_df))
        print("API en guncel tarih-saat:", api_df["event_datetime"].max())
    else:
        print("API veri getirmedi.")

    if not html_df.empty:
        print("HTML kayit sayisi:", len(html_df))
        print("HTML en guncel tarih-saat:", html_df["event_datetime"].max())
    else:
        print("HTML veri getirmedi.")

    combined = pd.concat([api_df, html_df], ignore_index=True)

    if combined.empty:
        raise RuntimeError("AFAD API ve HTML kaynaklarindan veri alinamadi.")

    combined = combined.drop_duplicates(
        subset=["event_date", "event_time", "latitude", "longitude", "magnitude"],
        keep="first"
    )

    combined = combined.sort_values(
        by=["event_date", "event_time"],
        ascending=[False, False]
    )

    return combined

def ensure_source_exists(cur):
    cur.execute("""
        INSERT INTO data_sources (source_name, source_url, description)
        VALUES ('AFAD', 'https://deprem.afad.gov.tr/', 'AFAD resmi deprem verisi')
        ON CONFLICT (source_name) DO NOTHING;
    """)

def import_to_postgres(df: pd.DataFrame):
    conn = get_connection()
    cur = conn.cursor()

    ensure_source_exists(cur)

    cur.execute("SELECT COUNT(*) FROM earthquakes;")
    before_count = cur.fetchone()[0]

    insert_query = """
    INSERT INTO earthquakes
    (source_id, event_date, event_time, latitude, longitude, depth_km, magnitude, location_text, city, district)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (source_id, event_date, event_time, latitude, longitude, magnitude)
    DO NOTHING
    """

    for _, row in df.iterrows():
        cur.execute(insert_query, (
            int(row["source_id"]),
            str(row["event_date"]),
            str(row["event_time"]),
            float(row["latitude"]),
            float(row["longitude"]),
            float(row["depth_km"]) if pd.notna(row["depth_km"]) else None,
            float(row["magnitude"]),
            str(row["location_text"]),
            None if pd.isna(row["city"]) else str(row["city"]),
            None if pd.isna(row["district"]) else str(row["district"]),
        ))

    conn.commit()

    cur.execute("SELECT COUNT(*) FROM earthquakes;")
    after_count = cur.fetchone()[0]

    print("Veritabani kayit sayisi once:", before_count)
    print("Veritabani kayit sayisi sonra:", after_count)
    print("Yeni eklenen kayit sayisi:", after_count - before_count)

    cur.close()
    conn.close()

def main():
    print("AFAD hibrit veri guncelleme basladi.")
    print("API URL:", AFAD_API_URL)
    print("HTML URL:", AFAD_HTML_URL)

    df = fetch_afad_combined()

    latest_datetime = df["event_datetime"].max()
    latest_date = df["event_date"].max()

    print("Birlesik kayit sayisi:", len(df))
    print("Birlesik veride en guncel tarih-saat:", latest_datetime)

    print("\nIlk 10 kayit:")
    print(df[["event_date", "event_time", "city", "magnitude", "data_source_type"]].head(10))

    today = date.today()
    if (today - latest_date).days > 3:
        print("UYARI: AFAD verisi guncel gorunmuyor. Import durduruldu.")
        with open("afad_update_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Veri eski geldi, import durduruldu\n")
        return

    df.to_csv("afad_latest_snapshot.csv", index=False, encoding="utf-8-sig")
    print("afad_latest_snapshot.csv olusturuldu.")

    print("PostgreSQL'e aktariliyor...")
    import_to_postgres(df)
    print("Guncelleme tamamlandi.")

    with open("afad_update_log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Guncelleme tamamlandi\n")

if __name__ == "__main__":
    main()