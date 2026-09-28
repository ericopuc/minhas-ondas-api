import json

from flask_openapi3 import OpenAPI, Info, Tag
from flask import redirect, make_response, jsonify
from flask_cors import CORS
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from model import Session, Pico, Previsao
from schemas import *
from services import busca_previsao, ServicoExternoError
from score import calcula_score
from momento import opcoes as opcoes_momento, resolve as resolve_momento, \
    hora_atual_index, tendencia, FORMATO_HORA
from logger import logger


def callback_validacao(e: ValidationError):
    """ Padroniza a resposta de erro de validação (422) como um objeto único,
        no formato do ValidacaoErrorSchema, em vez da lista padrão do framework.
    """
    corpo = {
        "mensagem": "Erro de validação dos dados de entrada",
        "detalhes": json.loads(e.json()),
    }
    response = make_response(jsonify(corpo))
    response.status_code = 422
    return response


info = Info(title="Minhas Ondas API", version="1.0.0",
            description="Picos de surf favoritos com condições da Open-Meteo e score de qualidade.")
app = OpenAPI(__name__, info=info,
              validation_error_model=ValidacaoErrorSchema,
              validation_error_callback=callback_validacao)
CORS(app)

# definindo tags
home_tag = Tag(name="Documentação", description="Seleção de documentação: Swagger")
pico_tag = Tag(name="Pico", description="Adição, visualização, edição e remoção de picos de surf")
ranking_tag = Tag(name="Ranking", description="Melhor pico para ir em um momento, segundo o score")

# resposta de erro de validação (422); declarada em todas as rotas para que o
# framework documente o objeto único em vez de injetar a lista padrão
VALIDACAO_RESPONSE = {"422": ValidacaoErrorSchema}

# respostas de falha da API externa (Open-Meteo)
EXTERNA_RESPONSES = {"502": ErrorSchema, "504": ErrorSchema}


def erro(mensagem: str, codigo: int, contexto: str = ""):
    """ Registra o aviso de erro e devolve a resposta padrão (ErrorSchema).

    Arguments:
        mensagem: mensagem devolvida ao cliente.
        codigo: código HTTP da resposta.
        contexto: prefixo opcional usado apenas no log para identificar a origem.
    """
    logger.warning(f"{contexto} {mensagem}".strip())
    return {"mensagem": mensagem}, codigo


def carrega_dados(session, pico: Pico) -> dict:
    """ Devolve os dados coletados da API externa para o pico, usando o cache
        de 1 hora. Se o cache expirou, consulta a Open-Meteo de novo; se a
        consulta falhar e houver dados antigos, eles são reaproveitados.
    """
    if pico.previsao and not pico.previsao.expirada():
        return pico.previsao.carrega()

    try:
        dados = busca_previsao(pico.latitude, pico.longitude)
    except ServicoExternoError as e:
        if pico.previsao:
            logger.warning(f"Usando dados antigos do pico #{pico.id}: {e.mensagem}")
            return pico.previsao.carrega()
        raise

    if pico.previsao:
        pico.previsao.atualiza(dados)
    else:
        pico.previsao = Previsao(dados)
    session.commit()
    logger.debug(f"Dados do pico #{pico.id} atualizados")
    return dados


def horas_com_score(dados: dict, pico: Pico) -> list:
    """ Acrescenta o score e as notas parciais a cada hora coletada. """
    return [{**hora, **calcula_score(hora, pico)} for hora in dados["horas"]]


def condicao_atual(horas: list):
    """ Registro da hora atual (ou None, se fora do intervalo coletado). """
    indice = hora_atual_index(horas)
    return horas[indice] if indice is not None else None


@app.get('/', tags=[home_tag])
def home():
    """Redireciona para /openapi, tela que permite a escolha do estilo de documentação.
    """
    return redirect('/openapi')


# ---------------------------------------------------------------------------
# Picos
# ---------------------------------------------------------------------------

@app.get('/picos', tags=[pico_tag],
         responses={"200": ListagemPicosSchema, **VALIDACAO_RESPONSE})
def get_picos():
    """Lista todos os picos cadastrados com a condição atual, a condição no
    momento padrão e a tendência do score

    O momento padrão é o primeiro do seletor do ranking ("agora" entre 6h e 16h;
    fora disso, o próximo horário de interesse). A tendência traz o score das
    próximas 12 horas e se ele melhora ou piora até o próximo horário de interesse.
    Os dados da Open-Meteo ficam armazenados por 1 hora. Se a API externa
    falhar para um pico sem dados armazenados, ele é listado com erro_previsao.
    """
    logger.debug("Coletando picos")
    momento = resolve_momento(None)
    hora_txt = momento["hora"].strftime(FORMATO_HORA)
    session = Session()
    picos = session.query(Pico).order_by(Pico.nome).all()

    resultado = []
    for pico in picos:
        try:
            horas = horas_com_score(carrega_dados(session, pico), pico)
        except ServicoExternoError as e:
            logger.warning(f"Sem dados para o pico #{pico.id}: {e.mensagem}")
            resultado.append(apresenta_pico(pico, erro_previsao=e.mensagem))
            continue

        item = apresenta_pico(pico, condicao_atual(horas))
        item["condicao_momento"] = next((h for h in horas if h["hora"] == hora_txt), None)
        item["tendencia"] = tendencia(horas, momento["hora"])
        resultado.append(item)

    logger.debug(f"{len(resultado)} picos encontrados")
    return {"momento": momento["id"], "rotulo_momento": momento["rotulo"],
            "picos": resultado}, 200


@app.get('/pico', tags=[pico_tag],
         responses={"200": PicoDetalheSchema, "404": ErrorSchema, **EXTERNA_RESPONSES,
                    **VALIDACAO_RESPONSE})
def get_pico(query: PicoBuscaSchema):
    """Busca um pico pelo id com todas as horas coletadas e o score de cada uma

    Inclui o dia anterior (histórico) e os próximos 7 dias (previsão): ondas,
    ondulação (swell), vento, maré e temperatura da água.
    """
    pico_id = query.id
    logger.debug(f"Coletando dados sobre pico #{pico_id}")
    session = Session()
    pico = session.query(Pico).filter(Pico.id == pico_id).first()

    if not pico:
        return erro("Pico não encontrado na base :/", 404, f"Erro ao buscar pico #{pico_id}:")

    try:
        dados = carrega_dados(session, pico)
    except ServicoExternoError as e:
        return erro(e.mensagem, e.codigo, f"Erro ao buscar dados do pico #{pico_id}:")

    horas = horas_com_score(dados, pico)
    return apresenta_pico_detalhe(pico, horas, condicao_atual(horas), dados), 200


@app.post('/pico', tags=[pico_tag],
          responses={"200": PicoViewSchema, "400": ErrorSchema, "409": ErrorSchema,
                     **EXTERNA_RESPONSES, **VALIDACAO_RESPONSE})
def add_pico(form: PicoSchema):
    """Adiciona um novo pico de surf à base

    Antes de salvar, consulta a Open-Meteo: se o local estiver em terra ou longe
    do mar (sem dados de ondas), o pico não é salvo e a resposta é 400.
    """
    nome = form.nome.strip()
    logger.debug(f"Adicionando pico '{nome}'")
    session = Session()

    if session.query(Pico).filter(Pico.nome == nome).first():
        return erro("Já existe um pico com esse nome :/", 409, f"Erro ao adicionar pico '{nome}':")

    try:
        dados = busca_previsao(form.latitude, form.longitude)
    except ServicoExternoError as e:
        return erro(e.mensagem, e.codigo, f"Erro ao adicionar pico '{nome}':")

    pico = Pico(
        nome=nome,
        latitude=form.latitude,
        longitude=form.longitude,
        swell_direcao_ideal=form.swell_direcao_ideal,
        swell_altura_ideal=form.swell_altura_ideal,
        swell_periodo_ideal=form.swell_periodo_ideal,
        vento_direcao_ideal=form.vento_direcao_ideal)
    pico.previsao = Previsao(dados)

    try:
        session.add(pico)
        session.commit()
        logger.debug(f"Adicionado pico '{nome}'")
        return apresenta_pico(pico, condicao_atual(horas_com_score(dados, pico))), 200

    except IntegrityError:
        return erro("Já existe um pico com esse nome :/", 409, f"Erro ao adicionar pico '{nome}':")
    except Exception:
        return erro("Não foi possível salvar o pico :/", 400, f"Erro ao adicionar pico '{nome}':")


@app.put('/pico', tags=[pico_tag],
         responses={"200": PicoViewSchema, "400": ErrorSchema, "404": ErrorSchema,
                    "409": ErrorSchema, **EXTERNA_RESPONSES, **VALIDACAO_RESPONSE})
def upd_pico(query: PicoBuscaSchema, form: PicoAtualizaSchema):
    """Atualiza os dados de um pico identificado pelo id

    Apenas os campos informados são alterados. Se a posição mudar, os dados da
    Open-Meteo são coletados de novo e o local é validado (precisa estar no mar).
    """
    pico_id = query.id
    logger.debug(f"Atualizando pico #{pico_id}")
    session = Session()
    pico = session.query(Pico).filter(Pico.id == pico_id).first()

    if not pico:
        return erro("Pico não encontrado na base :/", 404, f"Erro ao atualizar pico #{pico_id}:")

    latitude = form.latitude if form.latitude is not None else pico.latitude
    longitude = form.longitude if form.longitude is not None else pico.longitude
    dados = None
    if (latitude, longitude) != (pico.latitude, pico.longitude):
        try:
            dados = busca_previsao(latitude, longitude)
        except ServicoExternoError as e:
            return erro(e.mensagem, e.codigo, f"Erro ao atualizar pico #{pico_id}:")

    try:
        if form.nome is not None:
            pico.nome = form.nome.strip()
        for campo in ("swell_direcao_ideal", "swell_altura_ideal",
                      "swell_periodo_ideal", "vento_direcao_ideal"):
            valor = getattr(form, campo)
            if valor is not None:
                setattr(pico, campo, valor)
        if dados is not None:
            pico.latitude, pico.longitude = latitude, longitude
            if pico.previsao:
                pico.previsao.atualiza(dados)
            else:
                pico.previsao = Previsao(dados)
        session.commit()
        logger.debug(f"Atualizado pico #{pico_id}")

    except IntegrityError:
        session.rollback()
        return erro("Já existe um pico com esse nome :/", 409, f"Erro ao atualizar pico #{pico_id}:")
    except Exception:
        session.rollback()
        return erro("Não foi possível atualizar o pico :/", 400, f"Erro ao atualizar pico #{pico_id}:")

    try:
        horas = horas_com_score(carrega_dados(session, pico), pico)
        return apresenta_pico(pico, condicao_atual(horas)), 200
    except ServicoExternoError as e:
        return apresenta_pico(pico, erro_previsao=e.mensagem), 200


@app.delete('/pico', tags=[pico_tag],
            responses={"200": PicoDelSchema, "404": ErrorSchema, **VALIDACAO_RESPONSE})
def del_pico(query: PicoBuscaSchema):
    """Remove um pico (e os dados armazenados dele) a partir do id

    Retorna uma mensagem de confirmação da remoção.
    """
    pico_id = query.id
    logger.debug(f"Removendo pico #{pico_id}")
    session = Session()
    pico = session.query(Pico).filter(Pico.id == pico_id).first()

    if not pico:
        return erro("Pico não encontrado na base :/", 404, f"Erro ao remover pico #{pico_id}:")

    session.delete(pico)
    session.commit()
    logger.debug(f"Removido pico #{pico_id}")
    return {"mensagem": "Pico removido", "id": pico_id}, 200


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

@app.get('/ranking', tags=[ranking_tag],
         responses={"200": RankingSchema, **VALIDACAO_RESPONSE})
def get_ranking(query: RankingBuscaSchema):
    """Ordena os picos pelo score em um momento (horário de interesse)

    Os momentos são relativos aos horários de interesse (6h, 10h, 14h e 18h):
    antes das 6h, os horários de hoje; das 6h às 16h, "agora" e os próximos
    horários; depois das 16h, os horários de amanhã a partir das 6h.
    Sem momento informado, usa a primeira opção disponível.
    """
    momento = resolve_momento(query.momento)
    hora_txt = momento["hora"].strftime(FORMATO_HORA)
    logger.debug(f"Montando ranking para '{momento['id']}' ({hora_txt})")

    session = Session()
    ranking = []
    for pico in session.query(Pico).all():
        try:
            horas = horas_com_score(carrega_dados(session, pico), pico)
        except ServicoExternoError as e:
            logger.warning(f"Pico #{pico.id} fora do ranking: {e.mensagem}")
            continue

        condicao = next((h for h in horas if h["hora"] == hora_txt), None)
        ranking.append({
            "pico_id": pico.id,
            "nome": pico.nome,
            "score": condicao["score"] if condicao else None,
            "condicao": condicao,
        })

    ranking.sort(key=lambda item: item["score"] if item["score"] is not None else -1,
                 reverse=True)
    return {
        "momento": momento["id"],
        "rotulo": momento["rotulo"],
        "hora": hora_txt,
        "opcoes": [{"id": o["id"], "rotulo": o["rotulo"]} for o in opcoes_momento()],
        "ranking": ranking,
    }, 200
