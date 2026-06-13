@echo off
cd /d C:\Users\Windows11\deprem_projesi

echo ==========================================
echo Deprem Projesi baslatiliyor...
echo Once AFAD verileri guncellenecek.
echo ==========================================

C:\Users\Windows11\AppData\Local\Programs\Python\Python314\python.exe run_pipeline.py

echo ==========================================
echo Veri guncelleme tamamlandi.
echo Web uygulamasi baslatiliyor...
echo ==========================================

C:\Users\Windows11\AppData\Local\Programs\Python\Python314\python.exe app.py

pause