from langchain_core.tools import tool
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

from mongodb_tools import (
    search_tourist_attraction,
    search_yatra_information,
)


# ============================================================
# 1. LOAD ENVIRONMENT
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError("GROQ_API_KEY is missing from .env")


# ============================================================
# 2. DEFINE MONGODB TOOLS
# ============================================================

@tool
def tourism_search(query: str) -> str:
    """
    Search the MongoDB tourism database for verified information
    about tourist attractions in Jammu and Kashmir.
    """

    results = search_tourist_attraction(query)

    if not results:
        return "No matching tourism information was found in MongoDB."

    output = []

    for item in results:
        output.append(
            f"""
Name: {item.get('name')}
Region: {item.get('region')}
Category: {item.get('category')}
Distance: {item.get('distance')}
Timings: {item.get('timings')}
Entry Fee: {item.get('entry_fee')}

Description:
{item.get('description')}

Historical Background:
{item.get('historical_background')}

Route:
{item.get('location_route')}
"""
        )

    return "\n---\n".join(output)


@tool
def yatra_information_search(query: str) -> str:
    """
    Search the MongoDB database for verified Vaishno Devi
    Yatra information such as Aarti timings, registration,
    routes, facilities, packing guidance, and helpline details.
    """

    results = search_yatra_information(query)

    if not results:
        return "No matching Yatra information was found in MongoDB."

    output = []

    for item in results:
        output.append(
            f"""
Topic: {item.get('topic')}
Title: {item.get('title')}
Category: {item.get('category')}

Information:
{item.get('content')}
"""
        )

    return "\n---\n".join(output)


# ============================================================
# 3. CREATE GROQ MODEL
# ============================================================

llm = ChatGroq(
    model="openai/gpt-oss-20b",
    temperature=0.2,
    api_key=GROQ_API_KEY,
)


tools = [
    tourism_search,
    yatra_information_search,
]

tool_map = {
    tool.name: tool
    for tool in tools
}

llm_with_tools = llm.bind_tools(tools)


# ============================================================
# 4. SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Yatra Booking Agent, an AI travel assistant specializing in
Vaishno Devi and tourism in Jammu & Kashmir.

IMPORTANT:

- Use the available MongoDB tools whenever the user asks for
  tourism or Vaishno Devi information.
- Treat MongoDB results as the application's verified knowledge source.
- Do not invent facts that are not present in the retrieved information.
- Do not invent prices, timings, routes, availability, bookings,
  train numbers, hotel information, or other travel details.
- If the database does not contain the requested information,
  clearly say that the information is not available.
- Give concise, useful answers.
"""


# ============================================================
# 5. ACTUAL TOOL-CALLING LOOP
# ============================================================

def ask_agent(user_query):

    print("\n" + "=" * 70)
    print("USER QUERY")
    print("=" * 70)
    print(user_query)

    messages = [
        ("system", SYSTEM_PROMPT),
        ("human", user_query),
    ]

    # First call:
    # Groq decides whether it needs a MongoDB tool.
    response = llm_with_tools.invoke(messages)

    # Add Groq's response to the conversation.
    messages.append(response)

    # --------------------------------------------------------
    # Execute requested tools
    # --------------------------------------------------------

    if response.tool_calls:

        print("\n" + "=" * 70)
        print("TOOL EXECUTION")
        print("=" * 70)

        for tool_call in response.tool_calls:

            tool_name = tool_call["name"]
            tool_args = tool_call["args"]

            print(f"\nTool: {tool_name}")
            print(f"Arguments: {tool_args}")

            selected_tool = tool_map.get(tool_name)

            if selected_tool is None:
                tool_result = "Requested tool was not found."
            else:
                tool_result = selected_tool.invoke(tool_args)

            print("\nMongoDB Result:")
            print(tool_result)

            # Send the database result back to Groq.
            messages.append(
                {
                    "role": "tool",
                    "content": tool_result,
                    "tool_call_id": tool_call["id"],
                }
            )

        # ----------------------------------------------------
        # Second call:
        # Groq generates the final answer using MongoDB data.
        # ----------------------------------------------------

        final_response = llm_with_tools.invoke(messages)

    else:
        final_response = response

    print("\n" + "=" * 70)
    print("FINAL GROUNDED ANSWER")
    print("=" * 70)
    print(final_response.content)

    return final_response.content


# ============================================================
# 6. TEST CASES
# ============================================================

if __name__ == "__main__":

    ask_agent(
        "Tell me about Gulmarg in Kashmir."
    )

    ask_agent(
        "What are the Aarti timings at Vaishno Devi?"
    )

    ask_agent(
        "How do I register for the Vaishno Devi Yatra?"
    )

    ask_agent(
        "Tell me about a place called Atlantis in Jammu."
    )