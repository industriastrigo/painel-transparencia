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

# Cria diretório e gera o acervo do Lakehouse durante o build da imagem
RUN mkdir -p dados && \
    python -c "from src.coletores.semeador import semear_se_vazio; semear_se_vazio()"

# Porta dinâmica do Cloud Run (padrão 8080)
EXPOSE 8080

# Inicia o servidor ASGI Uvicorn expandindo ${PORT} com fallback para 8080
CMD ["sh", "-c", "exec uvicorn src.api.servidor:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]

