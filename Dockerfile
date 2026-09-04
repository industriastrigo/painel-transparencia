# Imagem base oficial leve
FROM python:3.11-slim

# Evita buffer de log e geração de bytecode .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# Instala dependências do sistema se necessário
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instala dependências Python primeiro (aproveita cache de build do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação, frontend e referências
COPY src/ ./src/
COPY publico/ ./publico/
COPY referencias/ ./referencias/

# Copia acervo de dados tratados (ignora bruto pelo .dockerignore e .gcloudignore)
COPY dados/ ./dados/


# Porta dinâmica do Cloud Run (padrão 8080)
EXPOSE 8080

# Inicia o servidor ASGI Uvicorn
CMD exec uvicorn src.api.servidor:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips="*"

