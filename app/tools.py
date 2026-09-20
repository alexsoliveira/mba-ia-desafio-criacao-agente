import re
import uuid
import asyncio
from sqlite3 import IntegrityError
import aiosqlite
from google.adk.tools import ToolContext
from .database import DB_PATH

async def get_apto(session_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT apartamento FROM tenant_sessoes WHERE session_id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
    return None

async def consultar_reservas(tool_context: ToolContext) -> str:
    """Consulta as reservas ativas do morador atual."""
    apto = await get_apto(tool_context.session.id)
    if not apto:
        return "Erro: Apartamento não identificado na sessão."
        
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT codigo, area, data FROM reservas WHERE apartamento = ?", (apto,)) as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        return f"Não há reservas ativas para o apartamento {apto}."
    
    linhas = [f"Reserva {r[0]} - Área: {r[1]} - Data: {r[2]}" for r in rows]
    return f"Reservas do apartamento {apto}:\n" + "\n".join(linhas)

async def cancelar_reserva(tool_context: ToolContext, codigo: str = None, area: str = None, data: str = None) -> str:
    """Cancela uma reserva do morador atual. Forneça o 'codigo' da reserva, ou a 'area' e 'data'."""
    apto = await get_apto(tool_context.session.id)
    
    async with aiosqlite.connect(DB_PATH) as db:
        if codigo:
            async with db.execute("SELECT apartamento FROM reservas WHERE codigo = ?", (codigo,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return f"Erro: Reserva {codigo} não encontrada."
                if row[0] != apto:
                    return f"Erro: A reserva {codigo} não pertence ao seu apartamento ({apto})."
            await db.execute("DELETE FROM reservas WHERE codigo = ?", (codigo,))
            await db.commit()
            return f"Reserva {codigo} cancelada com sucesso."
        elif area and data:
            async with db.execute("SELECT codigo, apartamento FROM reservas WHERE area = ? AND data = ?", (area, data)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return f"Erro: Não há reserva para a área {area} na data {data}."
                if row[1] != apto:
                    return f"Erro: A reserva para {area} em {data} pertence a outro apartamento."
            await db.execute("DELETE FROM reservas WHERE area = ? AND data = ? AND apartamento = ?", (area, data, apto))
            await db.commit()
            return f"Reserva de {area} em {data} cancelada com sucesso."
        else:
            return "Erro: Forneça o código da reserva, ou a área e a data para cancelar."

async def reservar_area(area: str, data: str, tool_context: ToolContext) -> str:
    """Reserva uma área comum. Requer área (ID da área) e data (YYYY-MM-DD)."""
    apto = await get_apto(tool_context.session.id)
    print(f"DEBUG reservar_area: apto={apto}, area={area}, data={data}, conf={tool_context.tool_confirmation}")
    
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT taxa FROM areas WHERE id = ?", (area,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                print(f"DEBUG reservar_area: area {area} nao existe")
                return f"Erro: Área '{area}' não existe."
            taxa = row[0]
            
    # Garantia 1: Cobrança gera confirmação
    if taxa > 0 and tool_context.tool_confirmation is None:
        tool_context.request_confirmation(
            hint="Aprovar taxa de reserva",
            payload={"area": area, "data": data, "taxa": taxa}
        )
        print(f"DEBUG reservar_area: requesting confirmation")
        return "Confirmação de cobrança solicitada."
        
    # Se o usuário rejeitou a confirmação
    if tool_context.tool_confirmation and not tool_context.tool_confirmation.payload.get("confirmado"):
        print(f"DEBUG reservar_area: confirmation rejected")
        return "Reserva cancelada pois a cobrança não foi aprovada."

    codigo = f"RSV-{uuid.uuid4().hex[:6].upper()}"
    print(f"DEBUG reservar_area: inserting {codigo}")
    
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO reservas (codigo, apartamento, area, data) VALUES (?, ?, ?, ?)",
                (codigo, apto, area, data)
            )
            await db.commit()
            print(f"DEBUG reservar_area: inserted successfully")
    except aiosqlite.IntegrityError:
        # Garantia 5: Dois moradores, uma reserva
        print(f"DEBUG reservar_area: IntegrityError")
        return "Erro: Esta área já foi reservada por outro morador para esta mesma data."

    return f"Reserva concluída com sucesso! O código da sua reserva é {codigo}."

async def consultar_visitantes(tool_context: ToolContext) -> str:
    """Consulta os visitantes autorizados pelo morador."""
    apto = await get_apto(tool_context.session.id)
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT nome, data FROM visitantes WHERE apartamento = ?", (apto,)) as cursor:
            rows = await cursor.fetchall()
            
    if not rows:
        return "Não há visitantes autorizados."
        
    linhas = [f"Visitante: {r[0]} - Data: {r[1]}" for r in rows]
    return "\n".join(linhas)

async def autorizar_visitante(nome: str, data: str, tool_context: ToolContext) -> str:
    """Autoriza um novo visitante. Requer nome completo e data (YYYY-MM-DD)."""
    apto = await get_apto(tool_context.session.id)
    
    # Garantia 1: Autorizar visitante sempre pede confirmação
    if tool_context.tool_confirmation is None:
        tool_context.request_confirmation(
            hint="Aprovar liberação de acesso",
            payload={"nome": nome, "data": data}
        )
        return "Confirmação de acesso solicitada."
        
    if not tool_context.tool_confirmation.payload.get("confirmado"):
        return "Autorização de visitante cancelada."
        
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
            (apto, nome, data)
        )
        await db.commit()
        
    return f"Visitante {nome} autorizado para o dia {data} com sucesso."

def consultar_capitulo_regulamento(palavra_chave: str) -> str:
    """Pesquisa o regulamento e retorna apenas o capítulo correspondente à palavra chave."""
    try:
        with open("dados/regulamento.md", "r", encoding="utf-8") as f:
            content = f.read()
            
        # Divide o markdown por capítulos (assumindo "## Capítulo")
        capitulos = re.split(r'(?=## Capítulo)', content)
        
        for cap in capitulos:
            if palavra_chave.lower() in cap.lower():
                return cap.strip()
                
        return "Nenhum capítulo encontrado sobre este assunto no regulamento."
    except Exception as e:
        return f"Erro ao ler o regulamento: {str(e)}"
