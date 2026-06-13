import pandas as pd
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans

print("Script başladı...")

def main():
    print("city_features.csv okunuyor...")
    df = pd.read_csv("city_features.csv")

    print("\nİlk 5 satır:")
    print(df.head())

    feature_cols = [
        "total_earthquakes",
        "avg_magnitude",
        "max_magnitude",
        "avg_depth",
        "recent_7d_count",
        "recent_30d_count",
        "magnitude_over_3_count",
        "magnitude_over_4_count"
    ]

    X = df[feature_cols].copy()
    X = X.fillna(0)

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    df["cluster"] = kmeans.fit_predict(X_scaled)

    print("\nŞehirler ve cluster etiketleri:")
    print(df[["city", "cluster"]].sort_values(by="cluster"))

    cluster_summary = df.groupby("cluster")[feature_cols].mean().round(2)
    print("\nCluster özetleri:")
    print(cluster_summary)

    df.to_csv("city_clusters.csv", index=False, encoding="utf-8-sig")
    cluster_summary.to_csv("cluster_summary.csv", encoding="utf-8-sig")

    print("\ncity_clusters.csv oluşturuldu.")
    print("cluster_summary.csv oluşturuldu.")

if __name__ == "__main__":
    main()