import os
import json
import time
import subprocess
from datetime import datetime
from dotenv import load_dotenv
from src.services.retriever import setup_retriever
from src.core.config import load_config
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.memory import ConversationBufferMemory
from langchain_community.chat_message_histories import FileChatMessageHistory
from langsmith import traceable
from langchain_community.callbacks.manager import get_openai_callback
from langchain_core.messages import HumanMessage, AIMessage
from src.utils.chat_utils import compress_chat_history, is_greeting_or_compliment, random_greeting_response, check_faq
from src.core.llm_factory import build_llm

load_dotenv()
config = load_config()
chuncking_profile = config["chuncking_profile"]

retriever = setup_retriever()

use_query_contextuale = False
used_context = False

if chuncking_profile:
    prompt_file = "src/data/prompts/AIprompts_profile.json"
else:
    prompt_file = "src/data/prompts/AIprompts.json"

with open(prompt_file, "r", encoding="utf-8") as file:
    data = json.load(file)
    contextualize_system_prompt = data["contextualize_system_prompt"]
    system_prompt = data["system_prompt"]

llm = build_llm()

if use_query_contextuale:
    contextualize_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}")
    ])
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_prompt
    )

my_prompt = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    MessagesPlaceholder("chat_history"),
    ("human", "{input}")
])

document_prompt = ChatPromptTemplate.from_template(
    "Source: {source}\n"
    "Chunk: {chunk_index}\n"
    "Content:\n{page_content}\n"
    "-----"
)

question_answer_chain = create_stuff_documents_chain(
    llm,
    my_prompt,
    document_prompt=document_prompt
)

os.makedirs("chat_logs", exist_ok=True)
chat_memory = FileChatMessageHistory("chat_logs/session1.json")
memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True,
    chat_memory=chat_memory
)


def retrieve_docs_safe(retriever, query: str):
    """Universal retriever call working for any LangChain version."""
    try:
        return retriever.invoke(query)
    except AttributeError:
        return retriever.get_relevant_documents(query)
    except TypeError:
        return retriever.invoke({"query": query})


def chat_with_model(history, retriever, new_message, chat_history):
    trimmed_history = compress_chat_history(chat_history, max_turns=5, max_length=300)

    if is_greeting_or_compliment(new_message):
        result = random_greeting_response()
        history.append((new_message, result))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=result)
        ])
        return history, ""

    print(f"\n{'='*60}")
    print(f"🔍 Checking FAQ for: '{new_message}'")
    print(f"{'='*60}")

    faq_result = None

    if faq_result:
        bot_reply = faq_result["answer"]
        confidence = faq_result["score"]
        matched_q = faq_result["matched_question"]

        print(f"✅ FAQ HIT!")
        print(f"   User asked: '{new_message}'")
        print(f"   Matched: '{matched_q}'")
        print(f"   Confidence: {confidence:.2%}")
        print(f"   Answer: {bot_reply[:150]}...")

        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=bot_reply)
        ])
        history.append((new_message, bot_reply))

        log_faq_usage(new_message, matched_q, confidence, bot_reply)

        return history, ""
    else:
        confidence = faq_result["score"] if faq_result else 0.0
        print(f"❌ No FAQ match (best score: {confidence:.2%})")
        print(f"   Routing to RAG/LLM system...")
        modified_query = new_message

        if use_query_contextuale:
            print("Using context-aware query reformulation...")
            retrieved_docs = history_aware_retriever.invoke({
                "input": new_message,
                "chat_history": trimmed_history
            })
            used_context = True
        else:
            retrieved_docs = retrieve_docs_safe(retriever, modified_query)

        with get_openai_callback() as cb:
            result = question_answer_chain.invoke({
                "input": new_message,
                "chat_history": trimmed_history,
                "context": retrieved_docs
            })

            token_usage = {
                "total_tokens": cb.total_tokens,
                "prompt_tokens": cb.prompt_tokens,
                "completion_tokens": cb.completion_tokens
            }

        payload_debug = {
            "input": new_message,
            "contextualized_query": modified_query,
            "used_contextualized": "True",
            "chat_history": [msg.content for msg in trimmed_history],
            "top_k_docs": [doc.page_content[:300] for doc in retrieved_docs],
            "final_llm_output": result,
            "token_usage": token_usage
        }

        print("\n📤 Full Debug Trace (LLM Payload):")
        print(json.dumps(payload_debug, indent=2, ensure_ascii=False))

        os.makedirs("logs", exist_ok=True)
        with open("logs/debug_trace.txt", "a", encoding="utf-8") as log_file:
            log_file.write(json.dumps(payload_debug, indent=2, ensure_ascii=False) + "\n\n")

        bot_reply = result

        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=bot_reply)
        ])
        history.append((new_message, bot_reply))

        return history, ""


def log_faq_usage(user_question, matched_question, confidence, answer):
    """Log FAQ hits for analytics"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "user_question": user_question,
        "matched_faq": matched_question,
        "confidence": confidence,
        "answer_preview": answer[:200],
        "source": "FAQ"
    }

    os.makedirs("logs", exist_ok=True)
    with open("logs/faq_usage.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


def chat_with_model_stream(history, retriever, new_message, chat_history):
    """Stream tokens for the RAG path, yield full response for greeting/FAQ."""
    trimmed_history = compress_chat_history(chat_history, max_turns=5, max_length=300)

    if is_greeting_or_compliment(new_message):
        result = random_greeting_response()
        history.append((new_message, result))
        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=result)
        ])
        yield result
        return

    print(f"\n{'='*60}")
    print(f"🔍 Checking FAQ for: '{new_message}'")
    faq_result = check_faq(new_message, threshold=0.65)

    if faq_result:
        bot_reply = faq_result["answer"]
        confidence = faq_result["score"]
        matched_q = faq_result["matched_question"]

        print(f"✅ FAQ HIT! Matched: '{matched_q}' | Confidence: {confidence:.2%}")

        chat_history.extend([
            HumanMessage(content=new_message),
            AIMessage(content=bot_reply)
        ])
        history.append((new_message, bot_reply))
        log_faq_usage(new_message, matched_q, confidence, bot_reply)

        yield bot_reply
        return

    print(f"❌ No FAQ match — routing to RAG/LLM streaming...")

    if use_query_contextuale:
        retrieved_docs = history_aware_retriever.invoke({
            "input": new_message,
            "chat_history": trimmed_history
        })
    else:
        retrieved_docs = retrieve_docs_safe(retriever, new_message)

    full_response = ""

    for chunk in question_answer_chain.stream({
        "input": new_message,
        "chat_history": trimmed_history,
        "context": retrieved_docs
    }):
        token = chunk.content if hasattr(chunk, "content") else str(chunk)
        full_response += token
        yield token

    chat_history.extend([
        HumanMessage(content=new_message),
        AIMessage(content=full_response)
    ])
    history.append((new_message, full_response))

    payload_debug = {
        "input": new_message,
        "top_k_docs": [doc.page_content[:300] for doc in retrieved_docs],
        "final_llm_output": full_response
    }
    os.makedirs("logs", exist_ok=True)
    with open("logs/debug_trace.txt", "a", encoding="utf-8") as f:
        f.write(json.dumps(payload_debug, indent=2, ensure_ascii=False) + "\n\n")


@traceable(name="chat_rag_session_stream")
def chat_with_model_gradio_stream(history, new_message, chat_history):
    """Drop-in streaming version of chat_with_model_gradio."""
    for token in chat_with_model_stream(history, retriever, new_message, chat_history):
        yield token


@traceable(name="chat_rag_session")
def chat_with_model_gradio(history, new_message, chat_history):
    new_history, cleared_input = chat_with_model(history, retriever, new_message, chat_history)
    return new_history, cleared_input, chat_history
