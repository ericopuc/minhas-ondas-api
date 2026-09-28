from pydantic import BaseModel, Field
from typing import Optional, List, Literal

from model.pico import Pico


class PicoSchema(BaseModel):
    """ Define como um novo pico a ser inserido deve ser representado.
        Direções em graus (0-360) de onde a ondulação/o vento VEM.
    """
    nome: str = Field("Barra da Tijuca Posto 8", min_length=2, max_length=140)
    latitude: float = Field(-23.0125, ge=-90, le=90)
    longitude: float = Field(-43.3560, ge=-180, le=180)
    swell_direcao_ideal: float = Field(180, ge=0, le=360)
    swell_altura_ideal: float = Field(1.5, gt=0, le=10)
    swell_periodo_ideal: float = Field(12, ge=3, le=25)
    vento_direcao_ideal: float = Field(0, ge=0, le=360)


class PicoAtualizaSchema(BaseModel):
    """ Define os campos que podem ser alterados em um pico (todos opcionais).
        Ao mudar latitude/longitude, os dados da API externa são coletados de novo.
    """
    nome: Optional[str] = Field(None, min_length=2, max_length=140)
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    swell_direcao_ideal: Optional[float] = Field(None, ge=0, le=360)
    swell_altura_ideal: Optional[float] = Field(None, gt=0, le=10)
    swell_periodo_ideal: Optional[float] = Field(None, ge=3, le=25)
    vento_direcao_ideal: Optional[float] = Field(None, ge=0, le=360)


class PicoBuscaSchema(BaseModel):
    """ Define a estrutura de busca de um pico, feita com base no seu id
    """
    id: int = 1


class FatoresSchema(BaseModel):
    """ Notas parciais (0-10) que compõem o score de uma hora
    """
    direcao: Optional[float] = 8.0
    tamanho: Optional[float] = 9.0
    periodo: Optional[float] = 7.5
    vento: Optional[float] = 9.5


class CondicaoSchema(BaseModel):
    """ Condições de uma hora: dados coletados da API externa + score calculado.
        Alturas em metros, períodos em segundos, direções em graus (de onde vem),
        vento em nós, maré em metros (nível do mar) e temperatura em °C.
    """
    hora: str = "2026-09-27T09:00"
    onda_altura: Optional[float] = 1.2
    onda_direcao: Optional[float] = 170
    onda_periodo: Optional[float] = 9.5
    swell_altura: Optional[float] = 1.0
    swell_direcao: Optional[float] = 175
    swell_periodo: Optional[float] = 11.2
    mare: Optional[float] = 0.35
    temperatura_agua: Optional[float] = 22.4
    vento_velocidade: Optional[float] = 6.0
    vento_direcao: Optional[float] = 20
    vento_rajada: Optional[float] = 11.0
    score: Optional[float] = 7.8
    fatores: FatoresSchema = FatoresSchema()


class PontoTendenciaSchema(BaseModel):
    """ Score de uma hora no gráfico de tendência
    """
    hora: str = "2026-09-28T06:00"
    score: Optional[float] = 6.2


class TendenciaSchema(BaseModel):
    """ Tendência do score a partir do momento padrão: pontos das próximas horas
        e a variação até o próximo horário de interesse
    """
    pontos: List[PontoTendenciaSchema] = []
    proximo_horario: str = "2026-09-28T10:00"
    rotulo_proximo: str = "Amanhã às 10h"
    variacao: float = 0.9
    direcao: Literal["melhora", "piora", "estavel"] = "melhora"


class PicoViewSchema(BaseModel):
    """ Define como um pico será retornado: preferências + condição atual
    """
    id: int = 1
    nome: str = "Barra da Tijuca Posto 8"
    latitude: float = -23.0125
    longitude: float = -43.3560
    swell_direcao_ideal: float = 180
    swell_altura_ideal: float = 1.5
    swell_periodo_ideal: float = 12
    vento_direcao_ideal: float = 0
    condicao_atual: Optional[CondicaoSchema] = None
    erro_previsao: Optional[str] = None


class PicoListagemSchema(PicoViewSchema):
    """ Pico na listagem: inclui a condição no momento padrão (o primeiro do
        seletor: "agora" ou o próximo horário de interesse) e a tendência
    """
    condicao_momento: Optional[CondicaoSchema] = None
    tendencia: Optional[TendenciaSchema] = None


class ListagemPicosSchema(BaseModel):
    """ Define como uma listagem de picos será retornada
    """
    momento: str = "2026-09-28T06:00"
    rotulo_momento: str = "Amanhã às 6h"
    picos: List[PicoListagemSchema]


class PicoDetalheSchema(PicoViewSchema):
    """ Define como o detalhe de um pico será retornado: inclui todas as horas
        coletadas (histórico + previsão) com o score de cada uma
    """
    coletado_em: Optional[str] = "2026-09-27T09:12:00"
    expira_em: Optional[str] = "2026-09-27T10:12:00"
    distancia_grade_km: Optional[float] = 4.9
    horas: List[CondicaoSchema] = []


class PicoDelSchema(BaseModel):
    """ Define como deve ser a estrutura do dado retornado após uma remoção.
    """
    mensagem: str
    id: int


def apresenta_pico(pico: Pico, condicao_atual: Optional[dict] = None,
                   erro_previsao: Optional[str] = None):
    """ Retorna uma representação do pico seguindo o schema definido em
        PicoViewSchema.
    """
    return {
        "id": pico.id,
        "nome": pico.nome,
        "latitude": pico.latitude,
        "longitude": pico.longitude,
        "swell_direcao_ideal": pico.swell_direcao_ideal,
        "swell_altura_ideal": pico.swell_altura_ideal,
        "swell_periodo_ideal": pico.swell_periodo_ideal,
        "vento_direcao_ideal": pico.vento_direcao_ideal,
        "condicao_atual": condicao_atual,
        "erro_previsao": erro_previsao,
    }


def apresenta_pico_detalhe(pico: Pico, horas: List[dict], condicao_atual: Optional[dict],
                           dados: dict):
    """ Retorna uma representação detalhada do pico seguindo o schema definido
        em PicoDetalheSchema.
    """
    detalhe = apresenta_pico(pico, condicao_atual)
    detalhe.update({
        "coletado_em": pico.previsao.data_coleta.isoformat(timespec="seconds"),
        "expira_em": pico.previsao.expira_em().isoformat(timespec="seconds"),
        "distancia_grade_km": dados.get("distancia_grade_km"),
        "horas": horas,
    })
    return detalhe
