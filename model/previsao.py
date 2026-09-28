import json
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from datetime import datetime, timedelta

from model import Base
from config import CACHE_MINUTOS
from momento import agora_local


class Previsao(Base):
    __tablename__ = 'previsao'

    id = Column("pk_previsao", Integer, primary_key=True)
    pico_id = Column(Integer, ForeignKey("pico.pk_pico"), unique=True, nullable=False)
    # dados horários já combinados (ondas + maré + vento), serializados em JSON
    dados = Column(Text, nullable=False)
    data_coleta = Column(DateTime, nullable=False)

    def __init__(self, dados: dict):
        """
        Cria o registro de uma coleta de dados da API externa

        Arguments:
            dados: dicionário com as horas coletadas (ver services.open_meteo).
        """
        self.atualiza(dados)

    def atualiza(self, dados: dict):
        """ Substitui os dados armazenados por uma nova coleta. """
        self.dados = json.dumps(dados)
        # hora local do fuso configurado (o container Docker roda em UTC)
        self.data_coleta = agora_local()

    def expirada(self) -> bool:
        """ Indica se os dados armazenados já passaram do tempo de cache.
            Uma coleta registrada "no futuro" (gravada em outro fuso) também
            é considerada expirada. """
        agora = agora_local()
        return (self.data_coleta > agora or
                agora - self.data_coleta >= timedelta(minutes=CACHE_MINUTOS))

    def expira_em(self) -> datetime:
        """ Momento em que os dados armazenados deixam de ser usados. """
        return self.data_coleta + timedelta(minutes=CACHE_MINUTOS)

    def carrega(self) -> dict:
        """ Devolve os dados armazenados como dicionário. """
        return json.loads(self.dados)
