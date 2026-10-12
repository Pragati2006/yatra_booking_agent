from langchain_core.tools import tool

from mongodb_tools import (
    search_tourist_attraction,
    search_yatra_information,
)


@tool
def tourism_search(query: str) -> str:
    """
    Search the MongoDB tourism database for information about
    tourist attractions and destinations in Jammu and Kashmir.

    Use this tool when the user asks about a specific place,
    destination, sightseeing location, attraction, history,
    timings, entry fees, distance, or tourism information.
    """

    results = search_tourist_attraction(query)

    if not results:
        return (
            f"No matching tourism information was found in the "
            f"MongoDB database for '{query}'."
        )

    output = []

    for item in results:
        output.append(
            f"""
Name: {item.get('name', 'N/A')}
Region: {item.get('region', 'N/A')}
Category: {item.get('category', 'N/A')}
Distance: {item.get('distance', 'N/A')}
Timings: {item.get('timings', 'N/A')}
Entry Fee: {item.get('entry_fee', 'N/A')}

Description:
{item.get('description', 'N/A')}

Historical Background:
{item.get('historical_background', 'N/A')}
""".strip()
        )

    return "\n\n---\n\n".join(output)


@tool
def yatra_information_search(query: str) -> str:
    """
    Search the MongoDB Yatra information database for verified
    information about the Vaishno Devi Yatra.

    Use this tool for questions about Aarti timings, registration,
    Yatra slips, routes, facilities, packing, helpline information,
    and other Yatra essentials.
    """

    results = search_yatra_information(query)

    if not results:
        return (
            f"No matching Yatra information was found in the "
            f"MongoDB database for '{query}'."
        )

    output = []

    for item in results:
        output.append(
            f"""
Topic: {item.get('topic', 'N/A')}
Title: {item.get('title', 'N/A')}
Category: {item.get('category', 'N/A')}

Information:
{item.get('content', 'N/A')}
""".strip()
        )

    return "\n\n---\n\n".join(output)


# List of tools available to the LangChain agent
MONGODB_TOOLS = [
    tourism_search,
    yatra_information_search,
]


if __name__ == "__main__":
    print("Available LangChain MongoDB tools:")

    for tool in MONGODB_TOOLS:
        print(f"- {tool.name}")