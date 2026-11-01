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


import mongodb_tools


def answer_mongodb_query(user_query: str) -> dict:
    """
    Answer a tourism/Yatra information query using LangChain
    tool-calling backed by MongoDB.
    """
    q_norm = user_query.strip().lower()

    if q_norm in _MONGODB_AGENT_CACHE:
        return _MONGODB_AGENT_CACHE[q_norm]

    token = mongodb_tools.start_retrieval_tracking()
    try:
        llm = _get_llm()

        # Bind the available MongoDB tools.
        llm_with_tools = llm.bind_tools(TOOLS)

        messages = [
            ("system", SYSTEM_PROMPT),
            ("human", user_query),
        ]

        # Iterative tool-calling loop (up to 3 turns) to allow model to gather data and generate answer
        response = llm_with_tools.invoke(messages)
        tool_results = []
        iteration = 0
        max_iterations = 3

        while response.tool_calls and iteration < max_iterations:
            iteration += 1
            messages.append(response)

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

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": str(result),
                    }
                )

            # Re-invoke model with tool execution messages
            response = llm_with_tools.invoke(messages)

        final_answer = response.content or ""

        tracked_sources = mongodb_tools.get_tracked_sources()
        if "atlas" in tracked_sources:
            knowledge_source = "atlas"
        elif "local_fallback" in tracked_sources:
            knowledge_source = "local_fallback"
        else:
            knowledge_source = "local_fallback"

        out = {
            "answer": final_answer,
            "tool_results": tool_results,
            "status": "success" if (tool_results and final_answer) else ("no_tool_call" if final_answer else "fallback"),
            "source": "mongodb_llm",
            "response_source": "mongodb_llm",
            "knowledge_source": knowledge_source,
        }

        if final_answer:
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
                "source": "local_fallback",
                "response_source": "conversation_agent",
                "knowledge_source": "local_fallback",
                "error": str(exc),
                "tool_error": str(tool_exc),
            }

            _MONGODB_AGENT_CACHE[q_norm] = out
            return out

        # We successfully retrieved data directly from MongoDB,
        # even though the LLM tool-calling step failed.
        if tool_results:
            tracked_sources = mongodb_tools.get_tracked_sources()
            ks = "atlas" if "atlas" in tracked_sources else "local_fallback"
            out = {
                "answer": "",
                "tool_results": tool_results,
                "status": "direct_tool_fallback",
                "source": "mongodb_llm",
                "response_source": "mongodb_agent",
                "knowledge_source": ks,
                "error": str(exc),
            }

            _MONGODB_AGENT_CACHE[q_norm] = out
            return out

        out = {
            "answer": "",
            "tool_results": [],
            "status": "fallback",
            "source": "local_fallback",
            "response_source": "conversation_agent",
            "knowledge_source": "local_fallback",
            "error": str(exc),
        }

        _MONGODB_AGENT_CACHE[q_norm] = out
        return out
    finally:
        mongodb_tools.clear_retrieval_tracking(token)

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