import json
import os
import aiosqlite

DB_PATH = "condominio.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tenant_sessoes (
                session_id TEXT PRIMARY KEY,
                apartamento TEXT NOT NULL
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS pending_conf (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                invocation_id TEXT
            )
        """)
        
        await db.execute("""
            CREATE TABLE IF NOT EXISTS apartamentos (
                numero TEXT PRIMARY KEY,
                morador TEXT
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS areas (
                id TEXT PRIMARY KEY,
                nome TEXT,
                taxa REAL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS reservas (
                codigo TEXT PRIMARY KEY,
                apartamento TEXT,
                area TEXT,
                data TEXT,
                UNIQUE(area, data)
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS visitantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                apartamento TEXT,
                nome TEXT,
                data TEXT
            )
        """)
        await db.commit()
        
        async with db.execute("SELECT count(*) FROM apartamentos") as cursor:
            count = (await cursor.fetchone())[0]
            if count == 0:
                await restaurar_dados(db)

async def restaurar_dados(db=None):
    close_db = False
    if db is None:
        db = await aiosqlite.connect(DB_PATH)
        close_db = True

    try:
        await db.execute("DELETE FROM visitantes")
        await db.execute("DELETE FROM reservas")
        await db.execute("DELETE FROM areas")
        await db.execute("DELETE FROM apartamentos")

        base_path = "dados"
        
        if os.path.exists(f"{base_path}/apartamentos.json"):
            with open(f"{base_path}/apartamentos.json", "r", encoding="utf-8") as f:
                apts = json.load(f)
                for apt in apts:
                    await db.execute(
                        "INSERT INTO apartamentos (numero, morador) VALUES (?, ?)",
                        (apt["numero"], apt["morador"])
                    )

        if os.path.exists(f"{base_path}/areas.json"):
            with open(f"{base_path}/areas.json", "r", encoding="utf-8") as f:
                areas = json.load(f)
                for area in areas:
                    await db.execute(
                        "INSERT INTO areas (id, nome, taxa) VALUES (?, ?, ?)",
                        (area["id"], area["nome"], area["taxa"])
                    )

        if os.path.exists(f"{base_path}/reservas.json"):
            with open(f"{base_path}/reservas.json", "r", encoding="utf-8") as f:
                reservas = json.load(f)
                for r in reservas:
                    await db.execute(
                        "INSERT INTO reservas (codigo, apartamento, area, data) VALUES (?, ?, ?, ?)",
                        (r["codigo"], r["apartamento"], r["area"], r["data"])
                    )

        if os.path.exists(f"{base_path}/visitantes.json"):
            with open(f"{base_path}/visitantes.json", "r", encoding="utf-8") as f:
                visitantes = json.load(f)
                for v in visitantes:
                    await db.execute(
                        "INSERT INTO visitantes (apartamento, nome, data) VALUES (?, ?, ?)",
                        (v["apartamento"], v["nome"], v["data"])
                    )

        await db.commit()
    finally:
        if close_db:
            await db.close()

async def get_tenant(session_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT apartamento FROM tenant_sessoes WHERE session_id = ?", (session_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
    return None

async def set_tenant(session_id: str, apartamento: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO tenant_sessoes (session_id, apartamento) VALUES (?, ?)",
            (session_id, apartamento)
        )
        await db.commit()

async def add_pending_conf(conf_id: str, session_id: str, invocation_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO pending_conf (id, session_id, invocation_id) VALUES (?, ?, ?)",
            (conf_id, session_id, invocation_id)
        )
        await db.commit()

async def get_and_remove_pending_conf(conf_id: str, session_id: str) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT invocation_id FROM pending_conf WHERE id = ? AND session_id = ?", (conf_id, session_id)) as cursor:
            row = await cursor.fetchone()
            if row:
                await db.execute("DELETE FROM pending_conf WHERE id = ?", (conf_id,))
                await db.commit()
                return row[0]
    return None
