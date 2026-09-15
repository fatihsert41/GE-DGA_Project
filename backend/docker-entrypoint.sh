#!/bin/sh
# Python servisinin container giriş noktası.
#
# Veritabanı YOKSA demo filo yüklenir (ilk kurulum). Varsa DOKUNULMAZ:
# container yeniden başlatıldığında girilen ölçümler silinmemeli.
# Demo verisini bilerek sıfırlamak için: scripts/reset-demo.ps1
set -e

mkdir -p "$(dirname "$TRANSFORMERAI_DB_PATH")"

if [ ! -f "$TRANSFORMERAI_DB_PATH" ]; then
    echo "[ilk kurulum] demo filo yukleniyor -> $TRANSFORMERAI_DB_PATH"
    python -m app.ml.seed
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
