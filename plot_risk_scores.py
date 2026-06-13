import pandas as pd
import matplotlib.pyplot as plt

from config import get_connection

conn = get_connection()

query = """
SELECT city, risk_score
FROM risk_analysis
ORDER BY risk_score DESC
LIMIT 10;
"""

df = pd.read_sql(query, conn)
conn.close()

plt.figure(figsize=(11, 6))
plt.barh(df["city"], df["risk_score"])
plt.xlabel("Risk Skoru")
plt.ylabel("İl")
plt.title("İllere Göre Risk Skorları (İlk 10)")
plt.gca().invert_yaxis()
plt.tight_layout()
plt.savefig("risk_scores_final.png", dpi=300, bbox_inches="tight")
plt.close()