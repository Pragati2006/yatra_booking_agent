"""
agents/availability_agent.py
Week 7: LangChain Agent-RPA Integration Layer for Maa Vaishno Devi Yatra Booking Agent.

Connects the LLM agent to the existing Playwright availability checking scripts:
1. Exposes check_yatra_availability_tool as a LangChain tool.
2. Supports parameter extraction and binding via ChatGroq (openai/gpt-oss-20b) and mock LLMs.
3. Provides fallback to deterministic parameter parsing and validation when offline or testing.
4. Returns interpreted structured results formatted for pilgrim warmth and accuracy.
"""

import os
import json
import functools
import logging
from typing import Optional, Dict, Any, List

try:
    from langchain_groq import ChatGroq
except ImportError:
    ChatGroq = None

from langchain_core.messages import ToolMessage, AIMessage, HumanMessage, SystemMessage
from agents.tools import check_yatra_availability_tool, check_yatra_availability
from agents import conversation_agent, coordinator
from utils.logger import log_event
from utils.masking import mask_sensitive_data

logger = logging.getLogger(__name__)

AVAILABILITY_TOOLS = [
    check_yatra_availability_tool,
]

AVAILABILITY_TOOL_MAP = {
    "check_yatra_availability_tool": check_yatra_availability_tool,
    "check_yatra_availability": check_yatra_availability_tool,
}

SYSTEM_PROMPT = """
You are the Vaishno Devi Yatra Availability Assistant.
Your responsibility is to check darshan slot availability by invoking the check_yatra_availability_tool.

Guidelines:
1. When a user asks about slot availability, open slots, or seat status:
   - Identify the date and convert it into ISO format (YYYY-MM-DD).
   - Identify the darshan category if mentioned: 'Normal Darshan', 'VIP Darshan', or 'Helicopter Darshan'.
   - Invoke check_yatra_availability_tool with arguments: {"date": "<YYYY-MM-DD>", "category": "<Category or null>"}.
2. If the user does not specify a date (e.g., 'Check availability'):
   - Do NOT invent or fabricate a date.
   - Ask the user to provide their travel date.
3. If the user specifies an unsupported category (e.g., 'Super VIP'):
   - Explain the supported categories: Normal Darshan, VIP Darshan, Helicopter Darshan.
4. For general tourism questions (e.g., 'What is Vaishno Devi?'):
   - Do NOT invoke the availability tool. Answer conversationally.
"""


@functools.lru_cache(maxsize=1)
def get_groq_llm() -> Optional[Any]:
    """Returns ChatGroq instance if GROQ_API_KEY is configured in environment and langchain_groq is available."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key or ChatGroq is None:
        return None
    try:
        return ChatGroq(
            model="openai/gpt-oss-20b",
            temperature=0.2,
            api_key=api_key,
        )
    except Exception as exc:
        logger.warning("Failed to initialize ChatGroq: %s", exc)
        return None


def run_availability_agent(
    user_query: str,
    llm: Optional[Any] = None,
    context: Optional[Dict[str, Any]] = None,
    headless: bool = True,
) -> Dict[str, Any]:
    """
    Executes a turn of the availability agent.
    If an LLM (or mock) with tool-calling capabilities is provided, completes the full tool-calling cycle:
      1. Passes user query and tool definition to LLM via bind_tools.
      2. Validates LLM tool arguments (date and category) before Playwright execution.
      3. Invokes check_yatra_availability_tool.
      4. Passes the structured tool result back to the LLM (ToolMessage) for interpretation.
      5. Returns natural language response.
    Otherwise (or if the LLM/API fails), falls back to deterministic parameter extraction.
    """
    active_llm = llm if llm is not None else get_groq_llm()
    log_event(logger, logging.INFO, "AGENT_OPERATION_STARTED", "Availability agent initiated turn", details={"query_length": len(user_query)})

    # 1. Genuine LLM Tool-Calling Cycle (if LLM with bind_tools is available)
    if active_llm and hasattr(active_llm, "bind_tools"):
        try:
            llm_with_tools = active_llm.bind_tools(AVAILABILITY_TOOLS)
            
            system_content = SYSTEM_PROMPT
            if context:
                ctx_date = context.get("last_availability_date")
                if not ctx_date and isinstance(context.get("requirements"), dict):
                    ctx_date = context["requirements"].get("start_date")
                if ctx_date:
                    system_content += f"\nPrevious context date: {ctx_date}. If the user refers to 'that date' or 'same date', use {ctx_date}."
                ctx_cat = context.get("last_availability_category")
                if ctx_cat:
                    system_content += f"\nPrevious context category: {ctx_cat}."

            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=user_query),
            ]
            response = llm_with_tools.invoke(messages)

            # Check if LLM produced tool calls
            tool_calls = getattr(response, "tool_calls", [])
            if tool_calls:
                call = tool_calls[0]
                tool_name = call.get("name")
                raw_args = dict(call.get("args") or {})
                call_id = call.get("id") or "call_yatra_avail_1"
                log_event(logger, logging.INFO, "AGENT_TOOL_SELECTED", f"Tool selected by agent: {tool_name}", details={"tool_name": tool_name})

                target_tool = AVAILABILITY_TOOL_MAP.get(tool_name)
                if not target_tool:
                    raise ValueError(f"Unrecognized availability tool requested by LLM: {tool_name}")

                # Step 4: Validate generated tool arguments before Playwright execution
                raw_date = raw_args.get("date")
                iso_date, raw_d, is_missing_date, is_invalid_date, invalid_date_reason = conversation_agent.parse_and_validate_yatra_date(
                    raw_date, context=context
                )

                if is_missing_date:
                    logger.info("LLM tool call missing date parameter: %s", raw_args)
                    return {
                        "tool_selected": False,
                        "tool_name": tool_name,
                        "tool_args": raw_args,
                        "tool_result": None,
                        "reply": conversation_agent.format_missing_date_prompt(),
                        "status": "NEEDS_INFO",
                        "execution_mode": "llm_tool_calling",
                        "extracted_params": {
                            "date": None,
                            "missing_date": True,
                            "invalid_date": False,
                            "unsupported_category": False,
                        },
                    }

                if is_invalid_date:
                    logger.info("LLM tool call contains invalid date '%s': %s", raw_date, invalid_date_reason)
                    return {
                        "tool_selected": False,
                        "tool_name": tool_name,
                        "tool_args": raw_args,
                        "tool_result": None,
                        "reply": conversation_agent.format_invalid_date_prompt(raw_date, invalid_date_reason or ""),
                        "status": "INVALID_INPUT",
                        "execution_mode": "llm_tool_calling",
                        "extracted_params": {
                            "date": None,
                            "raw_date": raw_date,
                            "missing_date": False,
                            "invalid_date": True,
                            "invalid_date_reason": invalid_date_reason,
                            "unsupported_category": False,
                        },
                    }

                raw_cat = raw_args.get("category")
                cat, raw_c, unsupp_cat, unsupp_val = conversation_agent.extract_and_validate_category(raw_cat or "")
                if not unsupp_cat:
                    # Pre-execution validation safeguard: check if user query specified an unsupported category that LLM omitted
                    _, _, q_unsupp_cat, q_unsupp_val = conversation_agent.extract_and_validate_category(user_query)
                    if q_unsupp_cat:
                        unsupp_cat = True
                        raw_cat = q_unsupp_val
                        unsupp_val = q_unsupp_val

                if unsupp_cat:
                    logger.info("LLM tool call contains unsupported category: %s", raw_cat)
                    return {
                        "tool_selected": False,
                        "tool_name": tool_name,
                        "tool_args": raw_args,
                        "tool_result": None,
                        "reply": conversation_agent.format_unsupported_category_prompt(raw_cat),
                        "status": "UNSUPPORTED_CATEGORY",
                        "execution_mode": "llm_tool_calling",
                        "extracted_params": {
                            "date": iso_date,
                            "category": None,
                            "unsupported_category": True,
                            "unsupported_category_value": unsupp_val,
                            "missing_date": False,
                            "invalid_date": False,
                        },
                    }

                validated_args = {
                    "date": iso_date,
                    "category": cat,
                    "headless": headless,
                }

                # Step 5: Execute registered LangChain tool (Playwright availability check)
                log_event(
                    logger,
                    logging.INFO,
                    "AGENT_TOOL_EXECUTION_STARTED",
                    f"Executing LangChain tool: {tool_name}",
                    details={"tool_name": tool_name, "sanitized_params": mask_sensitive_data(validated_args)},
                )
                tool_result = target_tool.invoke(validated_args)
                log_event(
                    logger,
                    logging.INFO,
                    "AGENT_TOOL_RESULT",
                    f"Tool returned result category: {tool_result.get('status')}",
                    details={"status": tool_result.get("status"), "total_slots": tool_result.get("total_slots", 0)},
                    final_outcome=tool_result.get("status"),
                )

                # Step 6: Return tool result to the LLM (ToolMessage) for interpretation
                tool_msg = ToolMessage(content=json.dumps(tool_result), tool_call_id=call_id)
                followup_messages = list(messages) + [response, tool_msg]

                final_reply = None
                try:
                    final_llm_response = active_llm.invoke(followup_messages)
                    content = getattr(final_llm_response, "content", None)
                    if isinstance(content, str) and content.strip():
                        final_reply = content.strip()
                    elif isinstance(content, list):
                        text_parts = [part.get("text", "") if isinstance(part, dict) else str(part) for part in content]
                        joined = "".join(text_parts).strip()
                        if joined:
                            final_reply = joined
                except Exception as interp_err:
                    logger.warning("LLM interpretation of tool result encountered error: %s. Using default formatter.", interp_err)

                # Step 7: Fall back to standard structured formatter if LLM text is empty
                if not final_reply:
                    final_reply = conversation_agent.format_availability_reply(
                        result=tool_result,
                        requested_date=iso_date,
                        category=cat,
                    )

                return {
                    "tool_selected": True,
                    "tool_name": tool_name,
                    "tool_args": validated_args,
                    "tool_result": tool_result,
                    "reply": final_reply,
                    "status": "SUCCESS" if tool_result.get("status") == "SUCCESS" else tool_result.get("status"),
                    "execution_mode": "llm_tool_calling",
                    "extracted_params": {
                        "date": iso_date,
                        "category": cat,
                        "missing_date": False,
                        "invalid_date": False,
                        "unsupported_category": False,
                    },
                }

            # If LLM did not generate tool calls (e.g. clarification, invalid parameters, or general chat)
            params = conversation_agent.extract_availability_parameters(user_query, context=context)
            if params["missing_date"]:
                return {
                    "tool_selected": False,
                    "tool_name": None,
                    "tool_args": {},
                    "tool_result": None,
                    "reply": conversation_agent.format_missing_date_prompt(),
                    "status": "NEEDS_INFO",
                    "execution_mode": "llm_tool_calling",
                    "extracted_params": params,
                }
            if params["invalid_date"]:
                return {
                    "tool_selected": False,
                    "tool_name": None,
                    "tool_args": {},
                    "tool_result": None,
                    "reply": conversation_agent.format_invalid_date_prompt(params["raw_date"], params.get("invalid_date_reason") or ""),
                    "status": "INVALID_INPUT",
                    "execution_mode": "llm_tool_calling",
                    "extracted_params": params,
                }
            if params["unsupported_category"]:
                return {
                    "tool_selected": False,
                    "tool_name": None,
                    "tool_args": {},
                    "tool_result": None,
                    "reply": conversation_agent.format_unsupported_category_prompt(params["unsupported_category_value"]),
                    "status": "UNSUPPORTED_CATEGORY",
                    "execution_mode": "llm_tool_calling",
                    "extracted_params": params,
                }

            content = getattr(response, "content", "")
            return {
                "tool_selected": False,
                "tool_name": None,
                "tool_args": {},
                "tool_result": None,
                "reply": content or conversation_agent.format_missing_date_prompt(),
                "status": "NEEDS_INFO" if (not content or "date" in content.lower()) else "SUCCESS",
                "execution_mode": "llm_tool_calling",
                "extracted_params": params,
            }
        except Exception as exc:
            log_event(
                logger,
                logging.WARNING,
                "AGENT_FALLBACK_ACTIVATED",
                f"LLM tool execution encountered an error, falling back to deterministic extraction: {exc}",
                error_category="LLM_FALLBACK",
                exc=exc,
            )

    # 2. Deterministic parameter extraction fallback (ensures 100% offline testability and resilience)
    params = conversation_agent.extract_availability_parameters(user_query, context=context)

    if params["missing_date"]:
        return {
            "tool_selected": False,
            "tool_name": None,
            "tool_args": {},
            "tool_result": None,
            "reply": conversation_agent.format_missing_date_prompt(),
            "status": "NEEDS_INFO",
            "execution_mode": "deterministic_fallback",
            "extracted_params": params,
        }

    if params["invalid_date"]:
        return {
            "tool_selected": False,
            "tool_name": None,
            "tool_args": {},
            "tool_result": None,
            "reply": conversation_agent.format_invalid_date_prompt(params["raw_date"], params.get("invalid_date_reason") or ""),
            "status": "INVALID_INPUT",
            "execution_mode": "deterministic_fallback",
            "extracted_params": params,
        }

    if params["unsupported_category"]:
        return {
            "tool_selected": False,
            "tool_name": None,
            "tool_args": {},
            "tool_result": None,
            "reply": conversation_agent.format_unsupported_category_prompt(params["unsupported_category_value"]),
            "status": "UNSUPPORTED_CATEGORY",
            "execution_mode": "deterministic_fallback",
            "extracted_params": params,
        }

    tool_args = {
        "date": params["date"],
        "category": params["category"],
        "headless": headless,
    }

    tool_result = check_yatra_availability_tool.invoke(tool_args)
    formatted_reply = conversation_agent.format_availability_reply(
        result=tool_result,
        requested_date=params["date"],
        category=params["category"],
    )

    return {
        "tool_selected": True,
        "tool_name": "check_yatra_availability_tool",
        "tool_args": tool_args,
        "tool_result": tool_result,
        "reply": formatted_reply,
        "status": "SUCCESS" if tool_result.get("status") == "SUCCESS" else tool_result.get("status"),
        "extracted_params": params,
        "execution_mode": "deterministic_fallback",
    }
