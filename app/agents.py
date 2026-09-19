from google.adk.agents import Agent
from .tools import (
    consultar_reservas,
    cancelar_reserva,
    reservar_area,
    consultar_visitantes,
    autorizar_visitante,
    consultar_capitulo_regulamento
)

agente_reservas = Agent(
    name="agente_reservas",
    instructions=(
        "Você é o especialista responsável por reservas e cancelamentos de áreas do condomínio.\n"
        "Quando o morador pedir para reservar ou cancelar uma área, use as ferramentas disponíveis.\n"
        "Sempre avise o morador caso haja cobrança associada e informe que a confirmação está pendente."
    ),
    tools=[consultar_reservas, cancelar_reserva, reservar_area]
)

agente_visitantes = Agent(
    name="agente_visitantes",
    instructions=(
        "Você é o especialista responsável por autorizar visitantes no condomínio.\n"
        "Sempre use a ferramenta de autorização e avise que o sistema solicitou liberação formal."
    ),
    tools=[consultar_visitantes, autorizar_visitante]
)

agente_regulamento = Agent(
    name="agente_regulamento",
    instructions=(
        "Você é o especialista no Regulamento do Residencial Aurora.\n"
        "Você não sabe o regulamento de cor. Sempre use a ferramenta 'consultar_capitulo_regulamento' "
        "pesquisando pela palavra-chave do assunto que o morador perguntou.\n"
        "Responda apenas com base no texto retornado pela ferramenta."
    ),
    tools=[consultar_capitulo_regulamento]
)

agente_principal = Agent(
    name="agente_principal",
    instructions=(
        "Você é o assistente virtual do Residencial Aurora.\n"
        "O morador é do condomínio, mas você nunca deve perguntar de qual apartamento ele é "
        "(isso já é sabido pelo sistema). \n"
        "Seja gentil e delegue o pedido para o especialista correto:\n"
        "- Reservas ou cancelamento de áreas -> agente_reservas\n"
        "- Liberação ou consulta de visitantes -> agente_visitantes\n"
        "- Dúvidas sobre regras, horários ou normas -> agente_regulamento\n"
        "Se o pedido não se encaixar em nenhum deles, responda educadamente que não pode ajudar."
    ),
    tools=[agente_reservas, agente_visitantes, agente_regulamento]
)
