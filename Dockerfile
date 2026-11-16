FROM python:3.11-slim

WORKDIR /app

# Copiar archivos
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt || true

COPY . .

# Puerto por defecto (Koyeb inyecta PORT automáticamente)
ENV PORT=8000
EXPOSE 8000

CMD ["python", "server.py"]
