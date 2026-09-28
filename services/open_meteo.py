import math
import requests

from config import (MARINE_API_URL, FORECAST_API_URL, API_EXTERNA_TIMEOUT, FUSO_HORARIO,
                    DIAS_PASSADOS, DIAS_PREVISAO, DISTANCIA_MAXIMA_MAR_KM,
                    ELEVACAO_MAXIMA_MAR_M)
from logger import logger


# variáveis horárias pedidas à Marine API e o nome usado internamente para cada uma
VARIAVEIS_MARINE = {
    "wave_height": "onda_altura",
    "wave_direction": "onda_direcao",
    "wave_period": "onda_periodo",
    "swell_wave_height": "swell_altura",
    "swell_wave_direction": "swell_direcao",
    "swell_wave_period": "swell_periodo",
    "sea_level_height_msl": "mare",
    "sea_surface_temperature": "temperatura_agua",
}

# variáveis horárias pedidas à Forecast API (vento em nós)
VARIAVEIS_VENTO = {
    "wind_speed_10m": "vento_velocidade",
    "wind_direction_10m": "vento_direcao",
    "wind_gusts_10m": "vento_rajada",
}


class ServicoExternoError(Exception):
    """ Falha ao consultar a API externa (indisponível, lenta ou resposta inválida). """

    def __init__(self, mensagem: str, codigo: int = 502):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.codigo = codigo


class LocalForaDoMarError(ServicoExternoError):
    """ O ponto informado não tem dados de mar (em terra ou longe da costa). """

    def __init__(self, mensagem: str):
        super().__init__(mensagem, 400)


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """ Distância aproximada (fórmula de haversine) entre dois pontos, em km. """
    raio_terra = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return 2 * raio_terra * math.asin(math.sqrt(a))


def _consulta(url: str, params: dict) -> dict:
    """ Faz um GET na API externa e devolve o JSON, convertendo falhas em
        ServicoExternoError.

    Arguments:
        url: endereço da API externa.
        params: parâmetros da query string.
    """
    logger.info(f"Consultando API externa: {url} ({params['latitude']}, {params['longitude']})")
    try:
        resposta = requests.get(url, params=params, timeout=API_EXTERNA_TIMEOUT)
        dados = resposta.json()
    except requests.Timeout:
        raise ServicoExternoError("A API externa (Open-Meteo) não respondeu a tempo :/", 504)
    except (requests.RequestException, ValueError):
        raise ServicoExternoError("Não foi possível consultar a API externa (Open-Meteo) :/")

    if resposta.status_code != 200 or dados.get("error"):
        motivo = dados.get("reason", f"HTTP {resposta.status_code}")
        raise ServicoExternoError(f"A API externa (Open-Meteo) recusou a consulta: {motivo}")
    return dados


def busca_previsao(latitude: float, longitude: float) -> dict:
    """ Coleta as condições horárias de mar (Marine API) e de vento (Forecast API)
        para um ponto e as combina em uma única lista de horas.

    Levanta LocalForaDoMarError quando o ponto não tem dados de ondas (a Marine
    API devolve apenas valores nulos para pontos longe da costa), quando o ponto
    está em terra (elevação acima do limite) ou quando a célula de mar usada pela
    API está longe demais do ponto escolhido.

    Arguments:
        latitude: latitude do ponto, em graus decimais.
        longitude: longitude do ponto, em graus decimais.
    """
    params_base = {
        "latitude": latitude,
        "longitude": longitude,
        "timezone": FUSO_HORARIO,
        "past_days": DIAS_PASSADOS,
        "forecast_days": DIAS_PREVISAO,
    }

    marine = _consulta(MARINE_API_URL, {**params_base, "hourly": ",".join(VARIAVEIS_MARINE)})
    horario_marine = marine.get("hourly", {})

    alturas = horario_marine.get("wave_height") or []
    if not any(valor is not None for valor in alturas):
        raise LocalForaDoMarError(
            "Não há dados de ondas para este local: ele parece estar em terra ou longe do mar. "
            "Escolha um ponto na água, próximo à arrebentação.")

    # perto da costa a API usa a célula de mar mais próxima, mesmo para pontos em
    # terra; a elevação do ponto pedido (≈0 no mar) identifica esses casos
    elevacao = marine.get("elevation")
    if elevacao is not None and elevacao > ELEVACAO_MAXIMA_MAR_M:
        raise LocalForaDoMarError(
            f"O ponto escolhido está em terra ({elevacao:.0f} m de altitude). "
            "Escolha um ponto na água, próximo à arrebentação.")

    distancia = distancia_km(latitude, longitude, marine["latitude"], marine["longitude"])
    if distancia > DISTANCIA_MAXIMA_MAR_KM:
        raise LocalForaDoMarError(
            f"O ponto de mar mais próximo com dados está a {distancia:.0f} km do local escolhido. "
            "Escolha um ponto na água, próximo à arrebentação.")

    vento = _consulta(FORECAST_API_URL, {**params_base, "hourly": ",".join(VARIAVEIS_VENTO),
                                         "wind_speed_unit": "kn"})
    horario_vento = vento.get("hourly", {})
    # indexa o vento pela hora, para combinar com as horas da Marine API
    indice_vento = {hora: i for i, hora in enumerate(horario_vento.get("time", []))}

    horas = []
    for i, hora in enumerate(horario_marine.get("time", [])):
        registro = {"hora": hora}
        for nome_api, nome in VARIAVEIS_MARINE.items():
            registro[nome] = (horario_marine.get(nome_api) or [None] * (i + 1))[i]
        j = indice_vento.get(hora)
        for nome_api, nome in VARIAVEIS_VENTO.items():
            valores = horario_vento.get(nome_api) or []
            registro[nome] = valores[j] if j is not None and j < len(valores) else None
        horas.append(registro)

    return {
        "latitude_grade": marine["latitude"],
        "longitude_grade": marine["longitude"],
        "distancia_grade_km": round(distancia, 1),
        "horas": horas,
    }
