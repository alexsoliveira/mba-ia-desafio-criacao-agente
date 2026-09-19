# Assistente Residencial Aurora

API em FastAPI com Google ADK para gestão do Residencial Aurora.

## Arquitetura

O sistema utiliza a arquitetura de **Agente Roteador / Delegador**:
- **Agente Principal (`agente_principal`)**: Atua como o contato inicial. Ele processa a intenção do morador e delega as tarefas. Ele não possui acesso a nenhuma regra de negócio nem de banco de dados diretamente, e não recebe o arquivo de regulamento no seu prompt, reduzindo o custo e mitigando alucinações genéricas.
- **Especialista de Reservas (`agente_reservas`)**: Possui as ferramentas `reservar_area`, `cancelar_reserva` e `consultar_reservas`. É o único que interage com as tabelas de áreas e reservas no banco SQLite.
- **Especialista de Visitantes (`agente_visitantes`)**: Possui as ferramentas para liberar e consultar acesso.
- **Especialista do Regulamento (`agente_regulamento`)**: Responde a dúvidas, utilizando uma ferramenta que lê apenas o capítulo necessário do markdown, garantindo a redução do contexto.

## Garantias

1. **Cobrança ou acesso só com confirmação**: 
   Em `app/tools.py` na ferramenta `reservar_area`:
   ```python
   if taxa > 0 and tool_context.tool_confirmation is None:
       tool_context.request_confirmation(
           hint="Aprovar taxa de reserva",
           payload={"area": area, "data": data, "taxa": taxa}
       )
       return "Confirmação de cobrança solicitada."
   ```
   Apenas se o morador aprovar "fora de banda" via endpoint `/confirmacoes` o ADK re-executa a tool com o payload confirmado.

2. **Cada sessão pertence a um apartamento**: 
   A API injeta o relacionamento no SQLite em `app/main.py`. Na ferramenta `reservar_area` em `app/tools.py`:
   ```python
   apto = await get_apto(tool_context.session.id)
   ```
   Como o apartamento não é aceito como argumento textual do LLM, é impossível um ataque de Prompt Injection fazer o agente agir em nome do apto 302 se o `session_id` pertence ao apto 101.

3. **Nada se perde no reinício**: 
   Usamos a sessão persistida oficial do ecossistema ADK (`DatabaseSessionService`) apontando para nosso SQLite.
   Em `app/main.py`:
   ```python
   db_url = f"sqlite+aiosqlite:///{DB_PATH}"
   session_service = DatabaseSessionService(db_url=db_url)
   ```

4. **O regulamento é consultado, não carregado**: 
   A ferramenta `consultar_capitulo_regulamento` em `app/tools.py` recorta apenas o capítulo pedido em tempo de execução e não envia as 500 linhas para o ADK.
   ```python
   capitulos = re.split(r'(?=## Capítulo)', content)
   for cap in capitulos:
       if palavra_chave.lower() in cap.lower():
           return cap.strip()
   ```

5. **Dois moradores, uma reserva**: 
   No momento de criação das tabelas em `app/database.py`:
   ```python
   CREATE TABLE IF NOT EXISTS reservas (
       ...
       UNIQUE(area, data)
   )
   ```
   Se a rota da API for atingida concorrentemente, o SQLite lançará `IntegrityError` que é pego pelo `try/except` na nossa ferramenta, evitando colisão de agenda sem bloquear a API ou crachar.

## Como Rodar

**Pré-requisitos**:
- Python 3.12+
- Gerenciador de pacotes `uv` instalado.

1. **Instalar Dependências**:
   ```bash
   uv sync
   ```
2. **Configuração (.env)**:
   Copie `.env.example` para `.env` e adicione sua chave de API do Gemini (`GEMINI_API_KEY`).
   
3. **Comando para Restaurar os Dados Iniciais**:
   Volta as tabelas do SQLite (visitantes e reservas) para o estado contido nos arquivos `.json` de `dados/`:
   ```bash
   uv run python -c "import asyncio; from app.database import restaurar_dados; asyncio.run(restaurar_dados())"
   ```

4. **Comando para Subir a API**:
   Inicia o servidor na porta 8000.
   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```