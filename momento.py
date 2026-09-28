"""
Momentos disponíveis para o resumo "melhor pico para ir".

O ranking é sempre relativo aos horários de interesse (6h, 10h, 14h e 18h):

- antes das 6h: os horários de hoje (6h, 10h, 14h e 18h);
- das 6h às 16h: o horário atual ("agora") e os próximos horários de interesse;
- depois das 16h: os horários de amanhã, a partir das 6h.

Depois dessas opções vêm os horários extras (HORARIOS_EXTRAS), contados a partir
do dia da primeira opção: manhã e tarde do dia seguinte e a manhã do outro dia.
Ex.: à noite de domingo → amanhã 6h, 10h, 14h e 18h; terça 6h e 14h; quarta 6h.

Cada momento é uma hora exata; o ranking usa o score dos picos nessa hora.
"""
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from config import FUSO_HORARIO


# horários de interesse para surfar
HORARIOS_INTERESSE = (6, 10, 14, 18)

# a partir desta hora as opções passam a ser as de amanhã
HORA_LIMITE_HOJE = 16

# quantidade de opções principais oferecidas no seletor
TOTAL_OPCOES = 4

# horários extras, por dias depois do dia da primeira opção: (dias, (horas, ...))
HORARIOS_EXTRAS = (
    (1, (6, 14)),  # dia seguinte: manhã e tarde
    (2, (6,)),     # o outro dia: manhã
)

# nomes dos dias da semana (segunda = 0, como em datetime.weekday())
DIAS_SEMANA = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")

# identificador do momento "agora" (os demais são horas no formato ISO)
AGORA = "agora"

# formato das horas usado pela API externa e no identificador dos momentos
FORMATO_HORA = "%Y-%m-%dT%H:00"

# horas exibidas no gráfico de tendência, a partir do momento padrão
TENDENCIA_HORAS = 12

# variação mínima de score (na escala 0-10) para considerar que vai melhorar ou piorar
TENDENCIA_LIMIAR = 0.5


def agora_local() -> datetime:
    """ Data e hora atuais no fuso configurado, sem informação de fuso
        (no mesmo formato das horas devolvidas pela API externa). """
    return datetime.now(ZoneInfo(FUSO_HORARIO)).replace(tzinfo=None)


def _proximos_horarios(inicio: datetime, quantidade: int) -> list:
    """ Próximos horários de interesse a partir de `inicio` (inclusive). """
    horarios = []
    dia = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    while len(horarios) < quantidade:
        for hora in HORARIOS_INTERESSE:
            horario = dia.replace(hour=hora)
            if horario >= inicio and len(horarios) < quantidade:
                horarios.append(horario)
        dia += timedelta(days=1)
    return horarios


def rotulo_horario(horario: datetime, agora: datetime) -> str:
    """ Rótulo do horário relativo ao dia atual: "Hoje às 14h", "Amanhã às 6h",
        "Terça às 6h" (dias seguintes pelo nome do dia da semana). """
    dias = (horario.date() - agora.date()).days
    dia = {0: "Hoje", 1: "Amanhã"}.get(dias, DIAS_SEMANA[horario.weekday()])
    return f"{dia} às {horario.hour}h"


def _opcao(horario: datetime, agora: datetime) -> dict:
    """ Monta uma opção de momento para um horário. """
    return {"id": horario.strftime(FORMATO_HORA), "rotulo": rotulo_horario(horario, agora),
            "hora": horario}


def opcoes(agora: Optional[datetime] = None) -> list:
    """ Lista de momentos oferecidos no seletor, do mais próximo ao mais distante.
        O primeiro é o momento padrão.

    Retorna uma lista de dicionários com "id", "rotulo" e "hora" (datetime).
    """
    agora = agora or agora_local()
    hora_cheia = agora.replace(minute=0, second=0, microsecond=0)
    hoje = hora_cheia.replace(hour=0)

    if agora.hour < HORARIOS_INTERESSE[0]:
        dia_base = hoje
        lista = [_opcao(h, agora) for h in _proximos_horarios(hoje, TOTAL_OPCOES)]
    elif agora.hour >= HORA_LIMITE_HOJE:
        dia_base = hoje + timedelta(days=1)
        lista = [_opcao(h, agora) for h in _proximos_horarios(dia_base, TOTAL_OPCOES)]
    else:
        dia_base = hoje
        lista = [{"id": AGORA, "rotulo": f"Agora ({agora.hour}h)", "hora": hora_cheia}]
        lista += [_opcao(h, agora)
                  for h in _proximos_horarios(hora_cheia + timedelta(hours=1), TOTAL_OPCOES - 1)]

    # horários extras dos dias seguintes, sem repetir os que já estão na lista
    existentes = {opcao["hora"] for opcao in lista}
    for dias, horas in HORARIOS_EXTRAS:
        for hora in horas:
            horario = (dia_base + timedelta(days=dias)).replace(hour=hora)
            if horario > hora_cheia and horario not in existentes:
                lista.append(_opcao(horario, agora))
                existentes.add(horario)
    return lista


def resolve(momento: Optional[str], agora: Optional[datetime] = None) -> dict:
    """ Converte o identificador de um momento em {"id", "rotulo", "hora"}.
        Sem momento, devolve o padrão (primeira opção).

    Arguments:
        momento: "agora", uma hora no formato ISO (ex.: 2026-09-28T06:00) ou None.
        agora: referência de horário (padrão: hora local atual).
    """
    agora = agora or agora_local()
    disponiveis = opcoes(agora)
    if not momento:
        return disponiveis[0]
    for opcao in disponiveis:
        if opcao["id"] == momento:
            return opcao
    if momento == AGORA:
        hora_cheia = agora.replace(minute=0, second=0, microsecond=0)
        return {"id": AGORA, "rotulo": f"Agora ({agora.hour}h)", "hora": hora_cheia}
    # hora fora da lista atual (ex.: seletor aberto há muito tempo): aceita mesmo assim
    hora = datetime.strptime(momento, FORMATO_HORA)
    return {"id": momento, "rotulo": rotulo_horario(hora, agora), "hora": hora}


def tendencia(horas: list, inicio: datetime, agora: Optional[datetime] = None) -> Optional[dict]:
    """ Tendência do score a partir de `inicio`: pontos das próximas horas e a
        variação até o próximo horário de interesse (melhora, piora ou estável).

    Arguments:
        horas: registros horários já com o score calculado.
        inicio: hora do momento de referência (em geral, o momento padrão).
        agora: referência de horário para os rótulos (padrão: hora local atual).
    """
    agora = agora or agora_local()
    inicio_txt = inicio.strftime(FORMATO_HORA)
    fim_txt = (inicio + timedelta(hours=TENDENCIA_HORAS)).strftime(FORMATO_HORA)
    proximo = _proximos_horarios(inicio + timedelta(hours=1), 1)[0]
    proximo_txt = proximo.strftime(FORMATO_HORA)

    pontos = [{"hora": h["hora"], "score": h["score"]} for h in horas
              if inicio_txt <= h["hora"] <= fim_txt]
    score_inicio = next((p["score"] for p in pontos if p["hora"] == inicio_txt), None)
    score_proximo = next((h["score"] for h in horas if h["hora"] == proximo_txt), None)
    if not pontos or score_inicio is None or score_proximo is None:
        return None

    variacao = round(score_proximo - score_inicio, 1)
    if variacao >= TENDENCIA_LIMIAR:
        direcao = "melhora"
    elif variacao <= -TENDENCIA_LIMIAR:
        direcao = "piora"
    else:
        direcao = "estavel"

    return {
        "pontos": pontos,
        "proximo_horario": proximo_txt,
        "rotulo_proximo": rotulo_horario(proximo, agora),
        "variacao": variacao,
        "direcao": direcao,
    }


def hora_atual_index(horas: list, agora: Optional[datetime] = None) -> Optional[int]:
    """ Índice do registro horário correspondente à hora atual. """
    referencia = (agora or agora_local()).strftime(FORMATO_HORA)
    for i, registro in enumerate(horas):
        if registro["hora"] == referencia:
            return i
    return None
