import warnings

warnings.filterwarnings(
    "ignore",
    message="Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater.",
)

from graph.build_graph import build_graph

app = build_graph()

state = {
    "user_input": "",
    "intent": None,
    "result": None,
    "response": None,
    "history": [],
    "last_list_result": None,
}


def push(role, content):
    state["history"].append({"role": role, "content": content})
    state["history"] = state["history"][-6:]


while True:
    user_input = input("Ask: ").strip()
    if user_input.lower() == "exit":
        break

    state["user_input"] = user_input
    state["response"] = None
    state["result"] = None

    push("user", user_input)

    result = app.invoke(state)

    reply = result.get("response", "(no response)")
    print("\nOK:", reply)

    push("assistant", reply)
    state.update(result)
