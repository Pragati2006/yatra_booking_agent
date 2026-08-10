"""
agents/
Multi-agent package for the Yatra Booking Agent:

  coordinator.py          - orchestrates all agents for the conversation flow
  conversation_agent.py   - multilingual NLU + devotional reply phrasing
  itinerary_agent.py      - builds the day-wise pilgrimage itinerary
  content_agent.py        - historical background + video links per place

Transport, darshan, and hotel search logic lives in the existing,
tested agent.py and db.py at the project root - the coordinator calls
into those directly rather than duplicating that logic here.
"""
