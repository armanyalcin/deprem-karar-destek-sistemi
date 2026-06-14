from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import subprocess
import sys
import os

from config import get_connection

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_cluster_label_map():
    """
    K-Means cluster numaraları sabit anlam taşımaz.
    Bu yüzden cluster'ları ortalama toplam deprem sayısına göre yorumluyoruz.
    En düşük ortalamalı cluster: Düşük Aktivite
    Ortadaki cluster: Orta Aktivite
    En yüksek ortalamalı cluster: Yüksek Aktivite
    """
    try:
        cluster_summary_df = pd.read_csv("cluster_summary.csv")

        if "cluster" not in cluster_summary_df.columns:
            cluster_summary_df.rename(columns={cluster_summary_df.columns[0]: "cluster"}, inplace=True)

        cluster_summary_df["cluster"] = cluster_summary_df["cluster"].astype(int)

        ordered_clusters = (
            cluster_summary_df
            .sort_values("total_earthquakes")["cluster"]
            .tolist()
        )

        cluster_label_map = {}

        if len(ordered_clusters) >= 1:
            cluster_label_map[ordered_clusters[0]] = "Düşük Aktivite Grubu"

        if len(ordered_clusters) >= 2:
            cluster_label_map[ordered_clusters[1]] = "Orta Aktivite Grubu"

        if len(ordered_clusters) >= 3:
            cluster_label_map[ordered_clusters[2]] = "Yüksek Aktivite Grubu"

        return cluster_label_map

    except FileNotFoundError:
        return {}
    except Exception:
        return {}

@app.route("/")
def home():
    selected_city = request.args.get("city", "").strip()
    update_status = request.args.get("update_status", "").strip()

    selected_city_cluster = None
    selected_city_cluster_label = None

    conn = get_connection()
    cur = conn.cursor()

    # Toplam deprem kaydı
    cur.execute("SELECT COUNT(*) FROM earthquakes;")
    total_earthquakes = cur.fetchone()[0]
    
    # Son güncelleme zamanı
    cur.execute("""
    SELECT event_date, event_time
    FROM earthquakes
    ORDER BY event_date DESC, event_time DESC
    LIMIT 1;
    """)
    last_update_row = cur.fetchone()

    last_update_time = None 
    if last_update_row:
       last_update_time = f"{last_update_row[0]} {last_update_row[1]}"

    # Şehir listesi
    cur.execute("""
        SELECT DISTINCT city
        FROM earthquakes
        WHERE city IS NOT NULL AND city <> ''
        ORDER BY city;
    """)
    city_list = [row[0] for row in cur.fetchall()]

    # En çok deprem görülen şehirler
    cur.execute("""
        SELECT city, COUNT(*) AS toplam
        FROM earthquakes
        WHERE city IS NOT NULL AND city <> ''
        GROUP BY city
        ORDER BY toplam DESC
        LIMIT 10;
    """)
    top_cities = cur.fetchall()

    # En yüksek risk skorları
    cur.execute("""
        SELECT city, risk_score
        FROM risk_analysis
        ORDER BY risk_score DESC
        LIMIT 10;
    """)
    top_risks = cur.fetchall()

    # Seçilen şehrin risk skoru
    selected_city_risk = None
    if selected_city:
        cur.execute("""
            SELECT city, risk_score,
                   activity_score, bvalue_score, population_score, fault_score
            FROM risk_analysis
            WHERE city = %s
            LIMIT 1;
        """, (selected_city,))
        selected_city_risk = cur.fetchone()

    # Seçilen şehrin temel istatistikleri
    selected_city_stats = None
    if selected_city:
        cur.execute("""
            SELECT
                COUNT(*) AS total_count,
                ROUND(AVG(magnitude)::numeric, 2) AS avg_magnitude,
                MAX(magnitude) AS max_magnitude,
                ROUND(AVG(depth_km)::numeric, 2) AS avg_depth
            FROM earthquakes
            WHERE city = %s;
        """, (selected_city,))
        selected_city_stats = cur.fetchone()

    # Son 10 deprem
    if selected_city:
        cur.execute("""
            SELECT event_date, event_time, city, district, magnitude, depth_km, latitude, longitude
            FROM earthquakes
            WHERE city = %s
            ORDER BY event_date DESC, event_time DESC
            LIMIT 10;
        """, (selected_city,))
    else:
        cur.execute("""
            SELECT event_date, event_time, city, district, magnitude, depth_km, latitude, longitude
            FROM earthquakes
            ORDER BY event_date DESC, event_time DESC
            LIMIT 10;
        """)

    latest_earthquakes = cur.fetchall()

    # Harita verisi
    map_data = []
    for event_date, event_time, city, district, magnitude, depth_km, latitude, longitude in latest_earthquakes:
        map_data.append({
            "date": str(event_date),
            "time": str(event_time),
            "city": city,
            "district": district if district else "-",
            "magnitude": float(magnitude) if magnitude is not None else None,
            "depth": float(depth_km) if depth_km is not None else None,
            "lat": float(latitude) if latitude is not None else None,
            "lon": float(longitude) if longitude is not None else None
        })

    cur.close()
    conn.close()

    # Cluster bilgisi
    if selected_city:
        try:
            city_clusters_df = pd.read_csv("city_clusters.csv")
            city_clusters_df["city"] = city_clusters_df["city"].astype(str).str.strip()

            cluster_label_map = get_cluster_label_map()

            cluster_row = city_clusters_df[city_clusters_df["city"] == selected_city]

            if not cluster_row.empty:
                selected_city_cluster = int(cluster_row.iloc[0]["cluster"])
                selected_city_cluster_label = cluster_label_map.get(
                    selected_city_cluster,
                    f"Cluster {selected_city_cluster}"
                )

        except FileNotFoundError:
            selected_city_cluster = None
            selected_city_cluster_label = None

    return render_template(
        "index.html",
        total_earthquakes=total_earthquakes,
        update_status=update_status,
        last_update_time=last_update_time,
        top_cities=top_cities,
        top_risks=top_risks,
        latest_earthquakes=latest_earthquakes,
        city_list=city_list,
        selected_city=selected_city,
        selected_city_risk=selected_city_risk,
        selected_city_stats=selected_city_stats,
        map_data=map_data,
        selected_city_cluster=selected_city_cluster,
        selected_city_cluster_label=selected_city_cluster_label
    )

@app.route("/update-data", methods=["POST"])
def update_data():
    selected_city = request.form.get("city", "").strip()

    try:
        result = subprocess.run(
            [sys.executable, "run_pipeline.py"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180
        )

        if result.returncode == 0:
            return redirect(url_for("home", city=selected_city, update_status="success"))
        else:
            print("Pipeline hata verdi:")
            print(result.stdout)
            print(result.stderr)
            return redirect(url_for("home", city=selected_city, update_status="error"))

    except Exception as e:
        print("Guncelleme sirasinda hata:", e)
        return redirect(url_for("home", city=selected_city, update_status="error"))

if __name__ == "__main__":
    app.run(debug=True)