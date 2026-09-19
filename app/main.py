from fastapi import FastAPI, HTTPException
from typing import List, Dict, Any
from dotenv import load_dotenv
load_dotenv()
from contextlib import asynccontextmanager
from google.adk.sessions import DatabaseSessionService
from google.adk.runners import Runner
from google.genai.types import InteractionStatus
from .database import init_db, DB_PATH, set_tenant, add_pending_conf, get_and_remove_pending_conf
from .schemas import *
from .agents import agente_principal
import uuid
import aiosqlite
import inspect

db_url = f"sqlite+aiosqlite:///{DB_PATH}"
session_service = DatabaseSessionService(db_url=db_url)

@asynccontextmanager
async def lifespan(app: FastAPI):
    if inspect.iscoroutinefunction(session_service.prepare_tables):
        await session_service.prepare_tables()
    else:
        session_service.prepare_tables()
    await init_db()
    yield

app = FastAPI(lifespan=lifespan)
runner = Runner(app_name="aurora", agent=agente_principal, session_service=session_service)

@app.post("/sessoes", response_model=SessaoResponse, status_code=201)
async def criar_sessao(req: SessaoCreate):
    session_id = f"sess-{uuid.uuid4().hex}"
    
    # Cria sessao no ADK
    adk_session = await session_service.create_session(session_id=session_id, app_name="aurora", user_id="sys")
    
    # Vincula o apartamento ao tenant
    await set_tenant(session_id, req.apartamento)
    return SessaoResponse(session_id=session_id)

async def _process_runner(session_id: str, invocation_id=None, texto=None, state_delta=None):
    resposta_text = ""
    confirmacoes = []
    
    kwargs = {
        "user_id": "sys",
        "session_id": session_id,
    }
    if invocation_id:
        kwargs["invocation_id"] = invocation_id
    if texto:
        from google.genai.types import Content, Part
        kwargs["new_message"] = Content(role="user", parts=[Part.from_text(text=texto)])
    if state_delta:
        kwargs["state_delta"] = state_delta

    async for event in runner.run_async(**kwargs):
        if event.content and event.content.parts:
            for p in event.content.parts:
                if p.text:
                    resposta_text += p.text
                    
        # Verifica confirmacoes pendentes
        if event.actions and event.actions.requested_tool_confirmations:
            for cid, conf in event.actions.requested_tool_confirmations.items():
                confirmacoes.append(PendenciaItem(
                    id=cid,
                    acao=conf.hint or "Confirmar Ação",
                    detalhes=conf.payload or {}
                ))
                # Salva no DB local para garantir idempotencia / erro 409 se repetido
                await add_pending_conf(cid, session_id, event.invocation_id)
                
    return MensagemResponse(resposta=resposta_text.strip(), confirmacoes_pendentes=confirmacoes)

@app.post("/sessoes/{session_id}/mensagens", response_model=MensagemResponse)
async def enviar_mensagem(session_id: str, req: MensagemRequest):
    sess = await session_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return await _process_runner(session_id, texto=req.texto)

@app.post("/sessoes/{session_id}/confirmacoes", response_model=MensagemResponse)
async def confirmar_mensagem(session_id: str, req: ConfirmacaoRequest):
    sess = await session_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
        
    invoc_id = await get_and_remove_pending_conf(req.id, session_id)
            
    if not invoc_id:
        raise HTTPException(status_code=409, detail="Confirmação pendente não encontrada para esse ID.")
        
    delta = {
        "tool_confirmations": {
            req.id: {
                "confirmed": req.confirmado,
                "payload": {"confirmado": req.confirmado}
            }
        }
    }
    
    # Retoma
    return await _process_runner(session_id, invocation_id=invoc_id, state_delta=delta)

@app.get("/sessoes/{session_id}/eventos")
async def listar_eventos(session_id: str):
    sess = await session_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return [e.model_dump() for e in sess.events]

@app.get("/apartamentos/{id}/reservas")
async def ver_reservas(id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT codigo, area, data FROM reservas WHERE apartamento = ?", (id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"codigo": r[0], "area": r[1], "data": r[2]} for r in rows]

@app.get("/apartamentos/{id}/visitantes")
async def ver_visitantes(id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT nome, data FROM visitantes WHERE apartamento = ?", (id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"nome": r[0], "data": r[1]} for r in rows]
