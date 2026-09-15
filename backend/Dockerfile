# TransformerAI — Python / ML servisi (Zayıf yanlar 4/4)
#
# Model imaj OLUŞTURULURKEN eğitilir: model.joblib git'e girmediği için
# her kurulumda üretilmesi gerekiyordu (iki bilgisayar arasında elle
# yapılan adım). --field-like ŞART (Faz 6.8).

FROM python:3.12-slim

# xgboost Linux'ta OpenMP çalışma zamanı ister; slim imajda yok.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Önce yalnızca bağımlılık listesi: kod değişince bu katman önbellekten gelir,
# paketler her seferinde yeniden inmez.
COPY requirements.txt .
# --retries / --timeout: numpy, xgboost, shap büyük paketler. İlk derleme
# denemesinde 27 dakika sonra "Connection broken: Broken pipe" ile koptu
# (aynı anda başka bir container da aynı paketleri indiriyordu). Kopan
# bağlantıda pip varsayılan olarak az dener; yavaş ağda derleme boşa gider.
RUN pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

COPY app ./app
RUN mkdir -p artifacts && python -m app.ml.train --field-like

# Kalıcı veri (dga.db) imajın içinde DEĞİL, birimde (/data): container
# silinip yeniden kurulsa da ölçümler kalır.
ENV TRANSFORMERAI_DB_PATH=/data/dga.db \
    TRANSFORMERAI_ENV=production \
    PYTHONUNBUFFERED=1

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["docker-entrypoint.sh"]
