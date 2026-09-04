FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip wheel
RUN pip install --no-cache-dir "setuptools<70.0.0" packaging typing-extensions==4.12.2

# PyTorch 2.5.1 sürümü
RUN pip install --no-cache-dir torch==2.5.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cpu

# Gerekli diğer kütüphaneler ve python-multipart (Form/Dosya yükleme desteği için)
RUN pip install --no-cache-dir fastapi uvicorn pydantic pypdf pydub python-multipart
RUN pip install --no-cache-dir "transformers<4.40.0"
RUN pip install --no-cache-dir TTS

COPY ./app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
