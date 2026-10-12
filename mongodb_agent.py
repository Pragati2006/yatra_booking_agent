import os

from langchain_groq import ChatGroq

from langchain_tools import (
    tourism_search,
    yatra_information_search,
)


TOOLS = [
    tourism_search,
    yatra_information_search,
]

TOOL_MAP = {
    tourism_search.name: tourism_search,
    yatra_information_search.name: yatra_information_search,
}


SYSTEM_PROMPT = """
You are the MongoDB-grounded tourism assistant for the Vaishno Devi
Yatra Booking Agent.

Your job is to answer tourism and Yatra-information questions using
ONLY information retrieved from the available MongoDB tools.

Available information includes:
- Jammu and Kashmir tourist attractions
- Destination descriptions and history
- Distances and timings stored in the tourism database
- Vaishno Devi Aarti timings
- Yatra registration information
- Yatra routes
- Yatra facilities
- Packing guidance
- Helpline information

Rules:
1. Use the appropriate MongoDB tool before answering factual questions.
2. Never invent tourism or Yatra information.
3. If the tool returns no matching information, clearly say that the
   requested information is not available in the current database.
4. Do not invent prices, timings, routes, hotels, train numbers,
   flight numbers, or booking details.
5. Keep answers concise and useful.
6. If the retrieved information is sufficient, answer directly.
7. Do not mention internal tool names, MongoDB, or implementation
   details unless specifically asked.
"""


import functools


@functools.lru_cache(maxsize=1)
def _get_llm():
    api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Add it to the .env file."
        )

    return ChatGroq(
        model="openai/gpt-oss-20b",
        temperature=0.2,
        api_key=api_key,
    )


_MONGODB_AGENT_CACHE = {}


def answer_mongodb_query(user_query: str) -> dict:
    """
    Answer a tourism/Yatra information query using LangChain
    tool-calling backed by MongoDB.
    """
    q_norm = user_query.strip().lower()

    if q_norm in _MONGODB_AGENT_CACHE:
        return _MONGODB_AGENT_CACHE[q_norm]

    try:
        llm = _get_llm()

        # Bind the available MongoDB tools.
        llm_with_tools = llm.bind_tools(TOOLS)

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_query),
        ]

        # First model call: decide whether a MongoDB tool is required.
        response = llm_with_tools.invoke(messages)

        tool_results = []

        # Execute every tool requested by the model.
        for tool_call in response.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})

            tool = TOOL_MAP.get(tool_name)

            if not tool:
                continue

            result = tool.invoke(tool_args)

            tool_results.append(
                {
                    "tool": tool_name,
                    "arguments": tool_args,
                    "result": result,
                }
            )

            messages.append(response)

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": str(result),
                }
            )

        # No tool was requested.
        if not tool_results:
            out = {
                "answer": response.content,
                "tool_results": [],
                "status": "no_tool_call",
            }

            _MONGODB_AGENT_CACHE[q_norm] = out
            return out

        # Generate the final answer using the retrieved MongoDB data.
        final_response = llm_with_tools.invoke(messages)

        out = {
            "answer": final_response.content,
            "tool_results": tool_results,
            "status": "success",
        }

        _MONGODB_AGENT_CACHE[q_norm] = out
        return out

    except Exception as exc:
        # If model tool-calling fails, directly query the
        # MongoDB tools instead of returning an empty fallback.

        tool_results = []

        try:
            from mongodb_tools import (
                search_tourist_attraction,
                search_yatra_information,
            )

            # Tourism query first.
            tourism_result = search_tourist_attraction(user_query)

            if tourism_result:
                tool_results.append(
                    {
                        "tool": "tourism_search",
                        "arguments": {
                            "query": user_query
                        },
                        "result": str(tourism_result),
                    }
                )

            else:
                # If no tourism result exists, try Yatra information.
                yatra_result = search_yatra_information(user_query)

                if yatra_result:
                    tool_results.append(
                        {
                            "tool": "yatra_information_search",
                            "arguments": {
                                "query": user_query
                            },
                            "result": str(yatra_result),
                        }
                    )

        except Exception as tool_exc:
            out = {
                "answer": "",
                "tool_results": [],
                "status": "error",
                "error": str(exc),
                "tool_error": str(tool_exc),
            }

            _MONGODB_AGENT_CACHE[q_norm] = out
            return out

        # We successfully retrieved data directly from MongoDB,
        # even though the LLM tool-calling step failed.
        if tool_results:
            out = {
                "answer": "",
                "tool_results": tool_results,
                "status": "direct_tool_fallback",
                "error": str(exc),
            }

            _MONGODB_AGENT_CACHE[q_norm] = out
            return out

        out = {
            "answer": "",
            "tool_results": [],
            "status": "fallback",
            "error": str(exc),
        }

        _MONGODB_AGENT_CACHE[q_norm] = out
        return out

if __name__ == "__main__":
    queries = [
        "Tell me about Gulmarg in Kashmir.",
        "What are the Aarti timings at Vaishno Devi?",
        "How do I register for the Vaishno Devi Yatra?",
        "Tell me about Atlantis in Jammu.",
    ]

    for query in queries:
        print("\n" + "=" * 70)
        print("QUERY:", query)
        print("=" * 70)

        result = answer_mongodb_query(query)

        print("\nANSWER:")
        print(result["answer"])

        print("\nTOOLS USED:")
        for tool_result in result["tool_results"]:
            print(
                tool_result["tool"],
                tool_result["arguments"],
            )