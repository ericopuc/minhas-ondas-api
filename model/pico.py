from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy.orm import relationship
from typing import Union

from model import Base
from momento import agora_local


class Pico(Base):
    __tablename__ = 'pico'

    id = Column("pk_pico", Integer, primary_key=True)
    nome = Column(String(140), unique=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)

    # condições preferidas pelo usuário para este pico. As direções seguem a
    # convenção meteorológica: graus (0-360) de onde a ondulação/o vento VEM.
    swell_direcao_ideal = Column(Float, nullable=False)
    swell_altura_ideal = Column(Float, nullable=False)
    swell_periodo_ideal = Column(Float, nullable=False)
    vento_direcao_ideal = Column(Float, nullable=False)

    data_insercao = Column(DateTime, default=agora_local)

    # Relacionamento 1:1 entre o pico e os dados coletados da API externa (cache).
    # Ao remover o pico, a previsão armazenada é removida junto.
    previsao = relationship("Previsao", uselist=False, cascade="all, delete-orphan")

    def __init__(self, nome: str, latitude: float, longitude: float,
                 swell_direcao_ideal: float, swell_altura_ideal: float,
                 swell_periodo_ideal: float, vento_direcao_ideal: float,
                 data_insercao: Union[DateTime, None] = None):
        """
        Cria um Pico de surf

        Arguments:
            nome: nome do pico (ex.: Barra da Tijuca Posto 8).
            latitude: latitude do pico, em graus decimais.
            longitude: longitude do pico, em graus decimais.
            swell_direcao_ideal: direção (graus) de onde vem a ondulação preferida.
            swell_altura_ideal: altura (m) preferida da ondulação.
            swell_periodo_ideal: período (s) preferido da ondulação.
            vento_direcao_ideal: direção (graus) de onde vem o vento preferido.
            data_insercao: data de quando o pico foi inserido à base.
        """
        self.nome = nome
        self.latitude = latitude
        self.longitude = longitude
        self.swell_direcao_ideal = swell_direcao_ideal
        self.swell_altura_ideal = swell_altura_ideal
        self.swell_periodo_ideal = swell_periodo_ideal
        self.vento_direcao_ideal = vento_direcao_ideal

        # se não for informada, será a data exata da inserção no banco
        if data_insercao:
            self.data_insercao = data_insercao
