import asyncio
import json
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from models.schemas import ChatRequest
from services import groq_service, rag_service, memory_service, ticket_service

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(req: ChatRequest):
    customer = memory_service.get_or_create_customer(
        req.customer_external_id, req.customer_name, req.channel
    )
    conversation = memory_service.get_or_create_conversation(
        req.conversation_id, customer["id"], req.channel
    )
    conversation_id = conversation["id"]
    customer_id = customer["id"]

    history = memory_service.get_recent_history(conversation_id)
    history_text = memory_service.build_history_text(history)

    async def event_generator():
        # 1) Live analysis first — right-side dashboard panel updates immediately
        analysis = groq_service.analyze_message(req.message, history_text)
        yield {
            "event": "analysis",
            "data": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "customer_id": customer_id,
                    **analysis,
                }
            ),
        }

        memory_service.save_message(
            conversation_id,
            "user",
            req.message,
            intent=analysis["intent"],
            sentiment=analysis["sentiment"],
            sentiment_score=analysis["sentiment_score"],
            language=analysis["language"],
        )

        # 2) RAG context (property listings + general knowledge base) + personalization
        # Both run fastembed (CPU-bound, synchronous) — push to worker threads so
        # they never block the event loop for other requests
        property_context = await asyncio.to_thread(rag_service.retrieve_context, req.message)
        kb_context = await asyncio.to_thread(rag_service.retrieve_kb_context, req.message)
        rag_context = "\n\n".join(c for c in [property_context, kb_context] if c)
        customer_context = memory_service.get_customer_context(customer_id)

        # 3) Stream the actual reply, token by token (Claude-style)
        full_reply = ""
        for token in groq_service.stream_chat_response(
            req.message, history, rag_context, customer_context, analysis["language"]
        ):
            full_reply += token
            yield {"event": "token", "data": json.dumps({"content": token})}

        memory_service.save_message(conversation_id, "assistant", full_reply)

        # 4) Lead/ticket capture + escalation handling
        # Not just escalations — a "hot" lead should also land in the tickets
        # table so the sales team can follow up, even if no human is needed yet.
        ticket_info = None
        if analysis["should_escalate"] or analysis.get("lead_temperature") == "hot":
            updated_history = memory_service.get_recent_history(conversation_id, limit=30)
            convo_text = memory_service.build_history_text(updated_history)
            ticket_info = ticket_service.create_or_update_ticket(
                conversation_id,
                customer_id,
                convo_text,
                escalated=analysis["should_escalate"],
                escalated_reason=analysis.get("escalate_reason"),
            )

        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "conversation_id": conversation_id,
                    "ticket": ticket_info,
                }
            ),
        }

    return EventSourceResponse(event_generator())


@router.get("/conversations/{external_id}")
async def get_conversations(external_id: str):
    from services.memory_service import get_conversations_by_external_id
    return get_conversations_by_external_id(external_id)
