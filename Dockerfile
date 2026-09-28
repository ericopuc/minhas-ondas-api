# imagem oficial e enxuta, com versão fixada
FROM python:3.12-slim

# evita arquivos .pyc e garante logs imediatos no stdout
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# dependências primeiro, para aproveitar o cache das camadas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# código da aplicação
COPY . .

EXPOSE 5000

CMD ["flask", "run", "--host", "0.0.0.0", "--port", "5000"]
