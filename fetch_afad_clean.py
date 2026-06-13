import pandas as pd
import re

url = "https://deprem.afad.gov.tr/"

tables = pd.read_html(url)

if not tables:
    raise ValueError("AFAD sayfasından tablo okunamadı.")

df = tables[0].copy()

print("Gelen sütunlar:")
print(df.columns.tolist())

rename_map = {
    "Tarih(TS)": "event_datetime",
    "Enlem": "latitude",
    "Boylam": "longitude",
    "Derinlik(Km)": "depth_km",
    "Büyüklük": "magnitude",
    "Yer": "location_text"
}

df.rename(columns=rename_map, inplace=True)

df["event_datetime"] = pd.to_datetime(df["event_datetime"], errors="coerce")
df["event_date"] = df["event_datetime"].dt.date
df["event_time"] = df["event_datetime"].dt.time

df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
df["depth_km"] = pd.to_numeric(df["depth_km"], errors="coerce")
df["magnitude"] = pd.to_numeric(df["magnitude"], errors="coerce")

def parse_location(location_text):
    if pd.isna(location_text):
        return None, None

    text = str(location_text).strip()

    if not text:
        return None, None

    match = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", text)
    if match:
        district = match.group(1).strip()
        city = match.group(2).strip()

        district = district if district else None
        city = city if city else None

        return city, district

    return text, None

parsed_locations = df["location_text"].apply(parse_location)
df["city"] = parsed_locations.apply(lambda x: x[0])
df["district"] = parsed_locations.apply(lambda x: x[1])

df["source_id"] = 1

selected_cols = [
    "source_id",
    "event_date",
    "event_time",
    "latitude",
    "longitude",
    "depth_km",
    "magnitude",
    "location_text",
    "city",
    "district"
]

clean_df = df[selected_cols].copy()

clean_df = clean_df.dropna(subset=[
    "event_date",
    "event_time",
    "latitude",
    "longitude",
    "magnitude",
    "location_text"
])

clean_df["city"] = clean_df["city"].replace("", pd.NA)
clean_df["district"] = clean_df["district"].replace("", pd.NA)

print("\nAyrıştırılmış örnek veri:")
print(clean_df[["location_text", "city", "district"]].head(10))

print("\nŞehri boş kalan kayıt sayısı:", clean_df["city"].isna().sum())

clean_df.to_csv("afad_clean.csv", index=False, encoding="utf-8-sig")

print("\nafad_clean.csv oluşturuldu.")
print("Toplam temiz kayıt sayısı:", len(clean_df))