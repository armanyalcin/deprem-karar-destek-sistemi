import pandas as pd

from config import get_connection

df = pd.read_csv("afad_clean.csv")

conn = get_connection()

cur = conn.cursor()

insert_query = """
INSERT INTO earthquakes
(source_id, event_date, event_time, latitude, longitude, depth_km, magnitude, location_text, city, district)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

for _, row in df.iterrows():
    cur.execute(insert_query, (
        int(row["source_id"]),
        str(row["event_date"]),
        str(row["event_time"]),
        float(row["latitude"]),
        float(row["longitude"]),
        float(row["depth_km"]),
        float(row["magnitude"]),
        str(row["location_text"]),
        None if pd.isna(row["city"]) else str(row["city"]),
        None if pd.isna(row["district"]) else str(row["district"])
    ))

conn.commit()
cur.close()
conn.close()

print("Veriler earthquakes tablosuna aktarıldı.")