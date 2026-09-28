from pydantic import BaseModel
from typing import List


class ErrorSchema(BaseModel):
    """ Define como uma mensagem de erro será representada
    """
    mensagem: str


class ValidacaoErrorSchema(BaseModel):
    """ Erro de validação de entrada (dados malformados na requisição)
    """
    mensagem: str = "Erro de validação dos dados de entrada"
    detalhes: List = []
