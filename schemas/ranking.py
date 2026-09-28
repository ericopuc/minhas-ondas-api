from pydantic import BaseModel, Field
from typing import Optional, List

from schemas.pico import CondicaoSchema


class RankingBuscaSchema(BaseModel):
    """ Define o momento consultado no ranking: "agora" ou uma hora exata
        (ex.: 2026-09-28T06:00). Se omitido, usa o primeiro momento disponível.
    """
    momento: Optional[str] = Field(None, pattern=r"^(agora|\d{4}-\d{2}-\d{2}T\d{2}:00)$")


class MomentoSchema(BaseModel):
    """ Opção de momento disponível no seletor: sempre relativa aos horários
        de interesse (6h, 10h, 14h e 18h)
    """
    id: str = "2026-09-28T06:00"
    rotulo: str = "Amanhã às 6h"


class RankingItemSchema(BaseModel):
    """ Condição e score de um pico na hora do momento escolhido
    """
    pico_id: int = 1
    nome: str = "Barra da Tijuca Posto 8"
    score: Optional[float] = 7.8
    condicao: Optional[CondicaoSchema] = None


class RankingSchema(BaseModel):
    """ Define como o ranking de picos para um momento será retornado.
        O primeiro item é o melhor pico para ir.
    """
    momento: str = "2026-09-28T06:00"
    rotulo: str = "Amanhã às 6h"
    hora: str = "2026-09-28T06:00"
    opcoes: List[MomentoSchema] = []
    ranking: List[RankingItemSchema] = []
