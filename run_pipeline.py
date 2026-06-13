import subprocess
import sys
from datetime import datetime

# Windows'ta stdout/stderr varsayilan olarak UTF-8 olmadigindan, Flask
# subprocess olarak calistirinca 'charmap' codec hatasi veriyor. UTF-8'e
# gecip encode edilemeyen karakterleri replace ediyoruz. Eski Python
# surumlerinde reconfigure metodu olmayabilir, o yuzden AttributeError'i yakaliyoruz.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

PYTHON_EXE = sys.executable

def write_log(message):
    with open("pipeline_log.txt", "a", encoding="utf-8") as log:
        log.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")

def run_step(script_name, step_name):
    print(f"\n--- {step_name} basliyor ---")
    write_log(f"{step_name} basladi")

    result = subprocess.run(
        [PYTHON_EXE, script_name],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    print(result.stdout)

    if result.stderr:
        print("HATA / UYARI:")
        print(result.stderr)

    if result.returncode != 0:
        write_log(f"{step_name} basarisiz oldu")
        raise RuntimeError(f"{step_name} basarisiz oldu.")

    write_log(f"{step_name} tamamlandi")
    print(f"--- {step_name} tamamlandi ---")

def main():
    write_log("Pipeline basladi")

    try:
        run_step("update_afad_to_postgres.py", "AFAD API veri guncelleme")
        run_step("build_city_features.py", "Sehir bazli ozellik uretme")
        run_step("train_clustering_model.py", "Clustering modeli calistirma")

        write_log("Pipeline basariyla tamamlandi")
        print("\nPipeline basariyla tamamlandi.")

    except Exception as e:
        write_log(f"HATA: {e}")
        print("\nPipeline hata verdi:")
        print(e)

if __name__ == "__main__":
    main()