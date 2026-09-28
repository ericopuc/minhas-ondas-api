import os

# endereço base da Marine API da Open-Meteo (ondas, maré e temperatura da água)
MARINE_API_URL = os.getenv("MARINE_API_URL", "https://marine-api.open-meteo.com/v1/marine")
# endereço base da Forecast API da Open-Meteo (vento; a Marine API não fornece vento)
FORECAST_API_URL = os.getenv("FORECAST_API_URL", "https://api.open-meteo.com/v1/forecast")
# tempo máximo (em segundos) de espera por uma resposta da API externa
API_EXTERNA_TIMEOUT = float(os.getenv("API_EXTERNA_TIMEOUT", "10"))

# fuso horário usado nas consultas e no cálculo dos momentos (hoje, amanhã...)
FUSO_HORARIO = os.getenv("FUSO_HORARIO", "America/Sao_Paulo")
# dias de histórico e de previsão solicitados à API externa
DIAS_PASSADOS = int(os.getenv("DIAS_PASSADOS", "1"))
DIAS_PREVISAO = int(os.getenv("DIAS_PREVISAO", "7"))

# tempo (em minutos) que os dados coletados ficam armazenados antes de nova consulta
CACHE_MINUTOS = int(os.getenv("CACHE_MINUTOS", "60"))

# distância máxima (km) entre o ponto escolhido e a célula de mar usada pela API externa;
# acima disso o local é considerado longe do mar
DISTANCIA_MAXIMA_MAR_KM = float(os.getenv("DISTANCIA_MAXIMA_MAR_KM", "12"))

# elevação máxima (m) do ponto escolhido; no mar ela é ~0 e em terra é maior
# (a Open-Meteo informa a elevação do ponto pedido junto com os dados de ondas)
ELEVACAO_MAXIMA_MAR_M = float(os.getenv("ELEVACAO_MAXIMA_MAR_M", "5"))
