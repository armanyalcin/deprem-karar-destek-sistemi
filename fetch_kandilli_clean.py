print("Kandilli script başladı")
import re
from typing import Optional, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup

LIST_URL = "https://www.koeri.boun.edu.tr/scripts/lst3.asp"
PAGE_URL = "https://www.koeri.boun.edu.tr/scripts/sondepremler.asp"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def fetch_html(url: str) -> str:
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text

def extract_pre_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    pre = soup.find("pre")
    if pre:
        return pre.get_text("\n", strip=False)
    return soup.get_text("\n", strip=False)

def find_data_lines(text: str) -> list[str]:
    lines = [line.rstrip() for line in text.splitlines()]
    cleaned = [line for line in lines if line.strip()]
    data_lines = [line for line in cleaned if re.match(r"^\d{4}\.\d{2}\.\d{2}", line)]
    return data_lines

def parse_location(location_text: str) -> Tuple[Optional[str], Optional[str]]:
    if not location_text:
        return None, None

    text = str(location_text).strip()
    if not text:
        return None, None

    m = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", text)
    if m:
        district = m.group(1).strip() or None
        city = m.group(2).strip() or None
        return city, district

    return text, None

def split_data_line(line: str) -> dict:
    pattern = re.compile(
        r"""
        ^
        (?P<date>\d{4}\.\d{2}\.\d{2})\s+
        (?P<time>\d{2}:\d{2}:\d{2})\s+
        (?P<latitude>-?\d+(?:\.\d+)?)\s+
        (?P<longitude>-?\d+(?:\.\d+)?)\s+
        (?P<depth_km>-?\d+(?:\.\d+)?)\s+
        (?P<md>-?\d+(?:\.\d+)?|-\.-)\s+
        (?P<ml>-?\d+(?:\.\d+)?|-\.-)\s+
        (?P<mw>-?\d+(?:\.\d+)?|-\.-)\s+
        (?P<location_text>.+?)\s*$
        """,
        re.VERBOSE | re.IGNORECASE
    )

    m = pattern.match(line)
    if not m:
        raise ValueError(f"Satır ayrıştırılamadı: {line}")

    row = m.groupdict()

    def parse_mag(value: str):
        if value in ("-.-", "", None):
            return None
        return float(value)

    md = parse_mag(row["md"])
    ml = parse_mag(row["ml"])
    mw = parse_mag(row["mw"])

    magnitude = ml if ml is not None else (md if md is not None else mw)
    city, district = parse_location(row["location_text"])

    return {
        "source_id": 2,
        "event_date": row["date"].replace(".", "-"),
        "event_time": row["time"],
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "depth_km": float(row["depth_km"]),
        "magnitude": magnitude,
        "location_text": row["location_text"].strip(),
        "city": city,
        "district": district,
        "magnitude_md": md,
        "magnitude_ml": ml,
        "magnitude_mw": mw,
    }

def build_dataframe(lines: list[str]) -> pd.DataFrame:
    rows = []
    failed = []

    for line in lines:
        try:
            rows.append(split_data_line(line))
        except Exception:
            failed.append(line)

    df = pd.DataFrame(rows)

    if not df.empty:
        df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
        df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
        df["depth_km"] = pd.to_numeric(df["depth_km"], errors="coerce")
        df["magnitude"] = pd.to_numeric(df["magnitude"], errors="coerce")

        df = df.dropna(subset=[
            "event_date",
            "event_time",
            "latitude",
            "longitude",
            "magnitude"
        ])

    print(f"Başarılı ayrıştırılan kayıt sayısı: {len(rows)}")
    print(f"Ayrıştırılamayan satır sayısı: {len(failed)}")

    if failed:
        print("\nİlk 5 başarısız satır örneği:")
        for item in failed[:5]:
            print(item)

    return df

def main():
    try:
        html = fetch_html(LIST_URL)
        used_url = LIST_URL
    except Exception:
        html = fetch_html(PAGE_URL)
        used_url = PAGE_URL

    print("Veri alınan URL:", used_url)

    text = extract_pre_text(html)
    data_lines = find_data_lines(text)

    if not data_lines:
        raise RuntimeError("Kandilli veri satırları bulunamadı.")

    df = build_dataframe(data_lines)

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
        "district",
        "magnitude_md",
        "magnitude_ml",
        "magnitude_mw",
    ]

    clean_df = df[selected_cols].copy()
    clean_df.to_csv("kandilli_clean.csv", index=False, encoding="utf-8-sig")

    print("\nİlk 5 kayıt:")
    print(clean_df.head())

    print("\nkandilli_clean.csv oluşturuldu.")

if __name__ == "__main__":
    main()