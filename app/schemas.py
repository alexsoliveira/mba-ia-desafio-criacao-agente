from pydantic import BaseModel
from typing import List, Dict, Any

class SessaoCreate(BaseModel):
    apartamento: str

class SessaoResponse(BaseModel):
    session_id: str

class ConfirmacaoRequest(BaseModel):
    id: str
    confirmado: bool

class PendenciaItem(BaseModel):
    id: str
    acao: str
    detalhes: Dict[str, Any]

class MensagemRequest(BaseModel):
    texto: str

class MensagemResponse(BaseModel):
    resposta: str
    confirmacoes_pendentes: List[PendenciaItem]
