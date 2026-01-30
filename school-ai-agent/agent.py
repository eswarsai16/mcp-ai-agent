from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from tools import fetch_all_students, add_student, remove_student

llm = ChatOllama(model="qwen2.5:3b", temperature=0)

tools = [fetch_all_students, add_student, remove_student]
tool_map = {t.name: t for t in tools}

llm_with_tools = llm.bind_tools(tools)

system_prompt = SystemMessage(
    content="You are a school database assistant. You can manage students using tools."
)

print("🤖 School AI Agent started. Type 'exit' to quit.")

while True:
    user_input = input("\nAsk: ")
    if user_input.lower() == "exit":
        break

    messages = [system_prompt, HumanMessage(content=user_input)]

    response = llm_with_tools.invoke(messages)
    messages.append(response)

    if response.tool_calls:
        for call in response.tool_calls:
            tool_name = call["name"]
            tool_args = call["args"]

            tool = tool_map[tool_name]
            result = tool.invoke(tool_args)

            messages.append(
                ToolMessage(content=str(result), tool_call_id=call["id"])
            )

        final_response = llm.invoke(messages)
        print("\n✅ Answer:", final_response.content)

    else:
        print("\n✅ Answer:", response.content)
