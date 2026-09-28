"""
Algoritmo do score (índice de qualidade do surf, de 0 a 10, com uma casa decimal).

Cada hora recebe quatro notas parciais, de 0 a 1:

- direcao: quão perto a direção da ondulação está da direção preferida;
- tamanho: quão perto a altura da ondulação está da altura preferida;
- periodo: quão perto o período está do preferido (período maior é menos penalizado);
- vento:   combina velocidade e direção do vento (ver nota_vento).

O score final é a média geométrica ponderada das notas parciais: um único fator
muito ruim (mar flat, vento forte maral) derruba o score, como na prática.

Todos os ajustes ficam no dicionário CALIBRACAO abaixo.
"""
import math
from typing import Optional


CALIBRACAO = {
    # peso de cada fator no score final (não precisam somar 1; são normalizados)
    "pesos": {
        "tamanho": 0.35,
        "vento": 0.35,
        "periodo": 0.18,
        "direcao": 0.12,
    },

    # direção da ondulação: desvio (graus) em que a nota cai para ~37%.
    # 45 → desvio de 20° ainda vale ~0.82; desvio de 90° vale ~0.02
    "direcao_tolerancia": 45.0,

    # tamanho: tolerância em escala logarítmica (razão altura/ideal).
    # abaixo do ideal penaliza mais que acima (0.55 → metade do ideal vale ~0.2)
    "tamanho_tolerancia_menor": 0.55,
    "tamanho_tolerancia_maior": 0.7,

    # período: tolerância em segundos abaixo e acima do ideal
    "periodo_tolerancia_menor": 3.5,
    "periodo_tolerancia_maior": 7.0,

    # vento (nós)
    "vento_fraco": 4.0,               # até aqui a direção do vento praticamente não importa
    "vento_forte": 18.0,              # a partir daqui um vento ruim tem efeito máximo
    "vento_curva": 0.7,               # <1 faz o vento ruim pesar já em velocidades médias
    "vento_limite_favoravel": 10.0,   # vento na direção preferida começa a atrapalhar acima disso
    "vento_favoravel_maximo": 25.0,   # velocidade em que o vento favorável atinge a penalidade máxima
    "vento_favoravel_penalidade": 0.5,
    # composição da "direção ruim" do vento:
    "vento_peso_preferencia": 0.6,    # desvio em relação à direção preferida (contrário = pior)
    "vento_peso_ondulacao": 0.4,      # vento entrando junto com a ondulação (maral) ou lateral
    "vento_expoente_lateral": 0.6,    # <1 aproxima o vento lateral do maral (ambos ruins)

    # nota mínima de cada fator, para a média geométrica não zerar por completo
    "nota_minima_fator": 0.03,
}


def diferenca_angular(a: float, b: float) -> float:
    """ Menor diferença entre duas direções, em graus (0 a 180). """
    return abs((a - b + 180) % 360 - 180)


def _limita(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    """ Restringe um valor ao intervalo [minimo, maximo]. """
    return max(minimo, min(maximo, valor))


def nota_direcao(direcao: float, ideal: float) -> float:
    """ Nota da direção da ondulação (curva gaussiana sobre o desvio). """
    desvio = diferenca_angular(direcao, ideal)
    return math.exp(-(desvio / CALIBRACAO["direcao_tolerancia"]) ** 2)


def nota_tamanho(altura: float, ideal: float) -> float:
    """ Nota do tamanho da ondulação (gaussiana sobre o logaritmo da razão). """
    if altura <= 0.05:
        return 0.0
    razao = math.log(altura / ideal)
    tolerancia = (CALIBRACAO["tamanho_tolerancia_menor"] if razao < 0
                  else CALIBRACAO["tamanho_tolerancia_maior"])
    return math.exp(-(razao / tolerancia) ** 2)


def nota_periodo(periodo: float, ideal: float) -> float:
    """ Nota do período da ondulação (gaussiana assimétrica em segundos). """
    diferenca = periodo - ideal
    tolerancia = (CALIBRACAO["periodo_tolerancia_menor"] if diferenca < 0
                  else CALIBRACAO["periodo_tolerancia_maior"])
    return math.exp(-(diferenca / tolerancia) ** 2)


def nota_vento(velocidade: float, direcao: float, direcao_ideal: float,
               direcao_ondulacao: Optional[float]) -> float:
    """ Nota do vento, de 0 a 1.

    - "direção ruim" (0 a 1) combina dois desvios:
        * em relação à direção preferida: 0 na direção preferida, 0.5 lateral, 1 contrário;
        * em relação à ondulação: 1 quando o vento vem junto com a ondulação (maral),
          alto quando lateral e 0 quando sopra contra ela (terral).
    - a "intensidade" cresce de 0 (vento fraco) a 1 (vento forte);
    - nota = 1 - direção ruim × intensidade: vento fraco é sempre bom, contrário
      forte é péssimo;
    - vento favorável muito forte (acima do limite) também perde pontos.
    """
    cal = CALIBRACAO
    ruim_preferencia = (1 - math.cos(math.radians(diferenca_angular(direcao, direcao_ideal)))) / 2

    if direcao_ondulacao is None:
        direcao_ruim = ruim_preferencia
    else:
        desvio_ondulacao = diferenca_angular(direcao, direcao_ondulacao)
        ruim_ondulacao = ((1 + math.cos(math.radians(desvio_ondulacao))) / 2) ** cal["vento_expoente_lateral"]
        direcao_ruim = (cal["vento_peso_preferencia"] * ruim_preferencia +
                        cal["vento_peso_ondulacao"] * ruim_ondulacao)

    intensidade = _limita((velocidade - cal["vento_fraco"]) /
                          (cal["vento_forte"] - cal["vento_fraco"])) ** cal["vento_curva"]

    excesso = _limita((velocidade - cal["vento_limite_favoravel"]) /
                      (cal["vento_favoravel_maximo"] - cal["vento_limite_favoravel"]))
    penalidade_favoravel = cal["vento_favoravel_penalidade"] * excesso * (1 - direcao_ruim)

    return _limita(1 - direcao_ruim * intensidade - penalidade_favoravel)


def _primeiro_valido(*valores):
    """ Devolve o primeiro valor que não é None. """
    return next((v for v in valores if v is not None), None)


def calcula_score(hora: dict, pico) -> dict:
    """ Calcula o score de uma hora para um pico.

    Usa os dados de swell (ondulação); se ausentes, recorre aos dados totais de
    onda. Fatores sem dado são ignorados na média.

    Arguments:
        hora: registro horário coletado (ver services.open_meteo.busca_previsao).
        pico: objeto Pico com as condições preferidas.

    Retorna um dicionário com "score" (0-10 ou None) e "fatores" (notas 0-10).
    """
    altura = _primeiro_valido(hora.get("swell_altura"), hora.get("onda_altura"))
    direcao = _primeiro_valido(hora.get("swell_direcao"), hora.get("onda_direcao"))
    periodo = _primeiro_valido(hora.get("swell_periodo"), hora.get("onda_periodo"))
    vento_vel = hora.get("vento_velocidade")
    vento_dir = hora.get("vento_direcao")

    notas = {}
    if direcao is not None:
        notas["direcao"] = nota_direcao(direcao, pico.swell_direcao_ideal)
    if altura is not None:
        notas["tamanho"] = nota_tamanho(altura, pico.swell_altura_ideal)
    if periodo is not None:
        notas["periodo"] = nota_periodo(periodo, pico.swell_periodo_ideal)
    if vento_vel is not None and vento_dir is not None:
        notas["vento"] = nota_vento(vento_vel, vento_dir, pico.vento_direcao_ideal, direcao)

    if "tamanho" not in notas:
        return {"score": None, "fatores": {k: round(v * 10, 1) for k, v in notas.items()}}

    pesos = CALIBRACAO["pesos"]
    minimo = CALIBRACAO["nota_minima_fator"]
    soma_pesos = sum(pesos[nome] for nome in notas)
    log_medio = sum(pesos[nome] * math.log(max(nota, minimo)) for nome, nota in notas.items())
    score = math.exp(log_medio / soma_pesos)

    return {
        "score": round(score * 10, 1),
        "fatores": {nome: round(nota * 10, 1) for nome, nota in notas.items()},
    }
