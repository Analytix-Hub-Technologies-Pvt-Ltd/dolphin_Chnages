"""Generate a Word handover document summarizing the Marine Tutor AI backend."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Tuple
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_NAME = "MarineTutorAI_Handover.docx"
OUTPUT_PATH = REPO_ROOT / OUTPUT_NAME
DEFAULT_ROOT_DIRS = [
    "graph",
    "services",
    "retrieval",
    "models",
    "ui",
    "api",
    "scripts",
    "tests",
    "config.py",
    "README.md",
    "main.py",
]


# Helper to create paragraph XML
def paragraph(text: str, style: str | None = None) -> str:
    text = escape(text)
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
    return f"<w:p>{ppr}<w:r><w:t xml:space=\"preserve\">{text}</w:t></w:r></w:p>"


def generate_folder_tree(root_dirs: Iterable[Path]) -> List[str]:
    lines: List[str] = []
    for root_dir in root_dirs:
        if not root_dir.exists():
            continue

        relative = root_dir.relative_to(REPO_ROOT)
        if root_dir.is_file():
            lines.append(f"/{relative.as_posix()}")
            lines.append("")
            continue

        lines.append(f"/{relative.as_posix()}")
        for entry in sorted(root_dir.iterdir()):
            prefix = "  "
            if entry.is_dir():
                lines.append(f"{prefix}{entry.name}/")
                for sub in sorted(entry.iterdir()):
                    indent = f"{prefix}    "
                    lines.append(f"{indent}{sub.name}/" if sub.is_dir() else f"{indent}{sub.name}")
            else:
                lines.append(f"{prefix}{entry.name}")
        lines.append("")
    return lines


def build_paragraphs(folder_tree_lines: List[str]) -> List[Tuple[str, str | None]]:
    generated_at = datetime.now(timezone.utc).isoformat()
    paras: List[Tuple[str, str | None]] = []

    paras.append(("Marine Tutor AI - Backend Handover", "Title"))
    paras.append((OUTPUT_NAME, None))
    paras.append((f"Generated on {generated_at} UTC", None))
    paras.append(("", None))

    paras.append(("Table of Contents", "Heading1"))
    contents = [
        "1. Project Overview",
        "2. Folder Structure Explanation",
        "3. LangGraph Architecture Explanation",
        "4. Checkpointer Implementation",
        "5. OpenAI Configuration",
        "6. Vector Store (FAISS) Details",
        "7. Node Logic Explanation",
        "8. Environment Variables",
        "9. Request/Response Data Flow",
        "10. Testing & Run Instructions",
        "11. Appendix",
    ]
    for line in contents:
        paras.append((line, None))
    paras.append(("", None))

    paras.append(("1. Project Overview", "Heading1"))
    paras.append(
        (
            "High-level explanation: Marine Tutor AI is a FastAPI-based chatbot backend that routes user intents through a LangGraph workflow to answer marine training questions, generate quizzes, and summarize prior interactions.",
            None,
        )
    )
    paras.append(
        (
            "Purpose: provide marine-specific tutoring with retrieval-augmented responses, quizzes, and historical summaries for bridge resource management and related topics.",
            None,
        )
    )
    paras.append(
        (
            "Technologies: FastAPI, LangGraph, OpenAI GPT models, FAISS vector search, PostgreSQL, async IO, loguru for logging, HTML/CSS/JS UI.",
            None,
        )
    )
    paras.append(("Data Flow Diagram:", None))
    paras.append(("User → Router → Retrieval → Node → OpenAI → Response", None))
    paras.append(("", None))

    paras.append(("2. Folder Structure Explanation", "Heading1"))
    paras.append(("Actual repository tree:", None))
    for line in folder_tree_lines:
        paras.append((line, None))
    paras.append(("Each folder and file:", None))
    paras.append(("/graph: LangGraph nodes and graph wiring.", None))
    paras.append(
        (
            "  base_node.py: abstract node utilities, response builders, normalization helpers.",
            None,
        )
    )
    paras.append(
        (
            "  build_graph.py: constructs StateGraph with router, retrieval, query, quiz, summary, greeting, fallback nodes and conditional edges ending at END.",
            None,
        )
    )
    paras.append(
        (
            "  router_node.py: uses EnhancedQueryAnalyzer to classify user query into node_type and returns router_decision.",
            None,
        )
    )
    paras.append(
        (
            "  retrieval_node.py: runs FAISS search via vector_store adapter, normalizes chunks, prepares video suggestions, resolves quiz topics, and passes retrieval_chunks plus metadata forward. Skips FAISS when node_type is summary to reuse existing chunks.",
            None,
        )
    )
    paras.append(
        (
            "  query_node.py: builds marine query prompt, always consumes retrieval_chunks, calls OpenAIService.chat once, extracts answer and follow-up questions, merges video suggestions, records history and LangGraph checkpointer fields.",
            None,
        )
    )
    paras.append(
        (
            "  quiz_node.py: generates 5-question MCQ quiz JSON from chunks, handles parsing fallbacks, records checkpointer fields for quiz context.",
            None,
        )
    )
    paras.append(
        (
            "  summary_node.py: constructs 50–60 line summary from previous_successful_chunks/questions, never calls FAISS, derives video suggestions from stored chunks only, updates history.",
            None,
        )
    )
    paras.append(("  greeting_node.py: lightweight node for salutations (delegated to suggestion service).", None))
    paras.append(("  fallback_node.py: safe response when routing fails or query incomplete.", None))
    paras.append(("  history_utils.py: extracts clean chat history for prompts.", None))
    paras.append(
        (
            "  state.py: GraphState pydantic model capturing messages, current_query, retrieval data, and checkpointer fields (previous_successful_questions/chunks, last_query_chunks, last_quiz_chunks, last_user_query, last_user_category, topic_history, router_decision, node_response).",
            None,
        )
    )
    paras.append(("/services: orchestration and external integrations.", None))
    paras.append(
        (
            "  chat_service.py: orchestrates ChatService; builds LangGraph via build_graph; wraps FAISS with VectorStoreAdapter embedding flow; defines checkpointer fields; cleans session messages; runs graph with inputs and aggregates outputs.",
            None,
        )
    )
    paras.append(
        (
            "  openai_service.py: AsyncOpenAI wrapper for chat completions and embeddings; configures model, temperature, max_tokens; logs prompts and responses; records interactions to database.",
            None,
        )
    )
    paras.append(
        (
            "  embedding_service.py & embedding_config.py: embed queries using OpenAI embeddings with EMBEDDING_DIM=3072 and model text-embedding-3-large.",
            None,
        )
    )
    paras.append(
        (
            "  query_analyzer.py: EnhancedQueryAnalyzer for routing classification (greeting/quiz/summary/query/fallback), standalone query generation, short topic extraction.",
            None,
        )
    )
    paras.append(("  suggestion_service.py: follow-up suggestion generation helper.", None))
    paras.append(("  session_service.py and auth_service.py: manage sessions/auth tokens for API routers.", None))
    paras.append(("/retrieval: FAISS storage and data prep.", None))
    paras.append(
        (
            "  faiss_store.py: FAISSStore wrapper with index/metadata persistence, L2 search, DEFAULT_TOP_K=3, index paths in retrieval/faiss_index.bin and .meta.json.",
            None,
        )
    )
    paras.append(("  chunker.py: text chunking pipeline (splits tutor content for embeddings).", None))
    paras.append(("  postgres_loader.py: loads tutor_content rows for indexing.", None))
    paras.append(
        (
            "  refresh_chunks.py: rebuilds FAISS index using OpenAI embeddings, schedules nightly rebuild at 03:00 via APScheduler.",
            None,
        )
    )
    paras.append(("/models: pydantic models and DB helpers.", None))
    paras.append(("  database.py: asyncpg pool management (get_pool/close_pool).", None))
    paras.append(("  node_response.py: NodeResponse and VideoSuggestion models for node outputs.", None))
    paras.append(
        (
            "  quiz_models.py, router_decision.py, user_models.py: schemas for quiz items, routing, and user/session records.",
            None,
        )
    )
    paras.append(("/ui: static HTML/CSS/JS chat frontend with login and quiz pages; includes loader logic and markdown sanitization in JS assets.", None))
    paras.append(("/api: FastAPI routers for chat, login, logout, quiz, session endpoints.", None))
    paras.append(("/config.py: Pydantic settings (OpenAI keys/models, DB config, FAISS index path, debug flags, scheduler timezone).", None))
    paras.append(("/scripts: operational scripts (e.g., seeding, migrations).", None))
    paras.append(("/tests: unit/integration placeholders for API and services.", None))
    paras.append(("/main.py & README.md: application entrypoint and project documentation.", None))
    paras.append(("", None))

    paras.append(("3. LangGraph Architecture Explanation", "Heading1"))
    paras.append(("LangGraph provides a declarative stateful graph where each node is an async callable that mutates GraphState. Used to enforce deterministic routing between conversation states.", None))
    paras.append(("Node flow: entry router → conditional edges to retrieval/query/quiz/summary/greeting/fallback. Retrieval feeds query/quiz; summary can be targeted directly. Edges to END finalize execution.", None))
    paras.append(("Conditional edges: router picks node_type from EnhancedQueryAnalyzer decision; query node can redirect to summary/quiz/greeting/fallback depending on router_decision preserved in state.", None))
    paras.append(("Router control: analyzer derives node_type, short_topic, reason, user_name, category, standalone_query; stored in router_decision shared across nodes.", None))
    paras.append(("Retrieval → Node → END: retrieval gathers chunks and suggestions then downstream node produces response and END is reached based on graph edges.", None))
    paras.append(("Checkpointer integration: ChatService compiles graph with MemorySaver checkpointer preserving selected fields for continuity (see Section 4).", None))
    paras.append(("Architecture diagram:", None))
    paras.append(("[Router]\n   \n[Retrieval] → [Query / Quiz]\n   \n[Summary / Greeting / Fallback]\n   \n[END]", None))
    paras.append(("", None))

    paras.append(("4. Checkpointer Implementation", "Heading1"))
    paras.append(("Configured in services/chat_service.py using langgraph.checkpoint.memory.MemorySaver (fallback shim if unavailable). GLOBAL_CHECKPOINTER is passed to graph.compile().", None))
    paras.append(("Stored fields (GraphState + CHECKPOINTER_FIELDS): previous_successful_questions, previous_successful_chunks, last_query_chunks, last_quiz_chunks, last_user_query, last_user_category, topic_history. Meaningful_messages/history kept in state for context reuse.", None))
    paras.append(("QueryNode writes: appends standalone_query to previous_successful_questions, chunks to previous_successful_chunks, sets last_query_chunks, last_user_query, last_user_category='QUERY', updates topic_history and meaningful history entries.", None))
    paras.append(("QuizNode writes: appends resolved_topic and chunks into previous_successful_* lists, sets last_quiz_chunks, last_user_query, last_user_category='QUIZ', updates topic_history and history logs.", None))
    paras.append(("SummaryNode reads: pulls previous_successful_questions/chunks/topic_history, merges last up to 5 contexts, never triggers FAISS retrieval; only reuses stored chunks for summary and video suggestions.", None))
    paras.append(("SummaryNode never calls FAISS because retrieval_node short-circuits when node_type=='summary' and summary builds from checkpointer history exclusively.", None))
    paras.append(("", None))

    paras.append(("5. OpenAI Configuration", "Heading1"))
    paras.append(("Model used: settings.openai_model defaults to gpt-4-turbo for chat; embedding model text-embedding-3-large with EMBEDDING_DIM=3072.", None))
    paras.append(("Max tokens: settings.openai_max_tokens (default 3000) passed to AsyncOpenAI chat completions; temperature default 0.7 (can be overridden per call such as temperature=0 for summary).", None))
    paras.append(("Model names configured in services/openai_service.py; embedding service uses same AsyncOpenAI client for embed_query with retry-less but guarded error handling.", None))
    paras.append(("Retry logic: errors are logged and safe fallback message returned; embeddings fallback to zero vector on exceptions; prompts logged to database via _log_llm_call.", None))
    paras.append(("System prompts: query, quiz, and summary nodes each craft structured prompts with [ANSWER SECTION]/[SUGGESTIONS SECTION] markers, quiz JSON schema, and 50–60 line summary constraints.", None))
    paras.append(("", None))

    paras.append(("6. Vector Store (FAISS) Details", "Heading1"))
    paras.append(("FAISS index stored under retrieval/faiss_index.bin with metadata sidecar retrieval/faiss_index.meta.json. FAISS_INDEX_PATH setting defaults to ./storage/faiss_index but store uses retrieval-local paths unless overridden.", None))
    paras.append(("Metadata saved per tutor_content row: id, title, section, topic, content, videourl, video_id, keywords; FAISSStore attaches _rank and _score on search results.", None))
    paras.append(("faiss_index optional: RetrievalNode guards vector_store existence; fallback content provided if missing. store.load() tolerates missing files.", None))
    paras.append(("KNN retrieval: VectorStoreAdapter embeds query with OpenAI embeddings then calls FAISSStore.search (L2) with DEFAULT_TOP_K=3; k normalized to index size.", None))
    paras.append(("Limitations: no deduplication beyond simple normalization; relies on embedding availability; retrieval_node logs errors and uses fallback chunk when embedding/search fails.", None))
    paras.append(("Max chunk size/strategy: chunker.py prepares chunks from tutor_content; refresh_chunks concatenates title/section/content_text before embedding; chunk size implicitly bounded by embedding model input (truncated to 8000 chars in OpenAIService.embed).", None))
    paras.append(("Scheduler: refresh_chunks.schedule_daily_rebuild sets 03:00 rebuild with APScheduler; rebuild_faiss_index uses EmbeddingService to regenerate vectors from PostgreSQL tutor_content.", None))
    paras.append(("", None))

    paras.append(("7. Node Logic Explanation", "Heading1"))
    paras.append(("RouterNode: Input GraphState messages/current_query/previous_questions → Output router_decision dict (node_type, short_topic, reason, user_name, category, standalone_query) and empty node_response.", None))
    paras.append(("RetrievalNode: Input router_decision/current_query + checkpointer history; resolves quiz topic; if node_type=='summary', returns existing retrieval_chunks and videos without FAISS. Otherwise embeds standalone_query and calls FAISS; normalizes chunks, builds up to 3 video suggestions, returns retrieval_chunks, video_suggestions, meaningful history snapshot.", None))
    paras.append(("QueryNode: Purpose answer marine queries. Input retrieval_chunks, video_suggestions, router_decision, chat history; always runs FAISS upstream. Builds prompt with chunks and history, calls OpenAI once, splits answer/suggestions, merges video suggestions, updates meaningful_messages/history and checkpointer fields; Output node_response dict with content, video_suggestions (max 3), question_suggestions, metadata.", None))
    paras.append(("QuizNode: Generates MCQ quiz. Input retrieval_chunks/videos/router_decision/current_query/resolved_quiz_topic; builds JSON quiz prompt from chunks; parses or falls back to default question; returns content payload with quiz_items; stores previous_successful_questions/chunks, last_quiz_chunks, topic_history, history entries.", None))
    paras.append(("SummaryNode: Produces 50–60 line summary. Input checkpointer fields (previous_successful_questions/chunks/topic_history), current_query, router_decision; builds topics from stored contexts, crafts SUMMARY_PROMPT; calls OpenAI once with temperature 0; extracts answer/suggestions; video suggestions derived only from merged stored chunks (max 3); updates meaningful history; does NOT call FAISS.", None))
    paras.append(("GreetingNode/FallbackNode: Lightweight responses for salutations or incomplete/unsupported queries via suggestion service defaults.", None))
    paras.append(("", None))

    paras.append(("8. Environment Variables", "Heading1"))
    paras.append(("APP_ENV (app_env): runtime environment flag used for logging context.", None))
    paras.append(("LOG_LEVEL (log_level): controls log verbosity via loguru configuration.", None))
    paras.append(("DB_HOST/DB_PORT/DB_NAME/DB_USER/DB_PASSWORD: PostgreSQL connection for asyncpg pool.", None))
    paras.append(("OPENAI_API_KEY: required for AsyncOpenAI client.", None))
    paras.append(("OPENAI_MODEL (openai_model): chat completion model name (default gpt-4-turbo).", None))
    paras.append(("OPENAI_TEMPERATURE (openai_temperature): default sampling temperature for chats.", None))
    paras.append(("OPENAI_MAX_TOKENS (openai_max_tokens): limits tokens per chat completion (default 3000).", None))
    paras.append(("FAISS_INDEX_PATH (faiss_index_path): path to persisted FAISS index files; defaults to ./storage/faiss_index but FAISSStore currently reads retrieval/faiss_index.bin unless overridden at init.", None))
    paras.append(("DEBUG_MODE: toggles debug behaviors in codepaths.", None))
    paras.append(("SCHEDULER_TIMEZONE: timezone used by APScheduler for nightly FAISS rebuild.", None))
    paras.append(("Additional expected vars (not in config.py but referenced in docs): EMBEDDING_MODEL/text-embedding-3-large and EMBEDDING_DIM=3072 constants in services/embedding_config.py.", None))
    paras.append(("TOKEN_LIMIT / MAX_CHUNK_SIZE / DATABASE_URL not explicitly defined; defaults come from openai_max_tokens and embedding input truncation; set via deployment environment if required.", None))
    paras.append(("", None))

    paras.append(("9. Request/Response Data Flow", "Heading1"))
    paras.append(("Pipeline: User → FastAPI (api/chat_router etc.) → ChatService.predict (runs LangGraph) → RouterNode → RetrievalNode → downstream Node (Query/Quiz/Summary/Greeting/Fallback) → OpenAIService → NodeResponse → UI renders markdown + suggestions/videos.", None))
    paras.append(("ChatService normalizes session messages, embeds query for FAISS, executes compiled graph with initial GraphState containing messages, user_id, current_query, previous_questions, and prior checkpointer fields from GLOBAL_CHECKPOINTER.", None))
    paras.append(("Outputs returned to API include node_response content, routing metadata, suggestions, and updated history for persistence.", None))
    paras.append(("", None))

    paras.append(("10. Testing & Run Instructions", "Heading1"))
    paras.append(("Run backend: uvicorn main:app --reload", None))
    paras.append(("FAISS rebuild: during startup lifespan rebuild_faiss_index(store) runs; manual trigger by invoking retrieval.refresh_chunks.rebuild_faiss_index with FAISSStore instance; nightly job scheduled at 03:00 via APScheduler when app running.", None))
    paras.append(("Testing nodes: call ChatService with crafted GraphState or use FastAPI endpoints (api/chat_router for queries, api/quiz_router for quizzes); inspect loguru debug lines for retrieval chunks and video suggestions.", None))
    paras.append(("Sample debug logs show FAISS search hits with rank/score/title and Query/Summary video merge counts for troubleshooting.", None))
    paras.append(("Database init: lifespan creates PostgreSQL pool; ensure DB credentials configured; open_ai_log table used for logging prompts/responses.", None))
    paras.append(("", None))

    paras.append(("11. Appendix", "Heading1"))
    paras.append(("Common errors:", None))
    paras.append(("- FAISS index missing: RetrievalNode logs 'Vector store is None' or FAISSStore.load warning; fallback chunk returned.", None))
    paras.append(("- Embedding failure: OpenAIService.embed logs error and returns zero vector causing poor retrieval quality.", None))
    paras.append(("- Proxy/credential issues: OpenAI API key missing results in chat/embedding errors and user-facing apology message.", None))
    paras.append(("Why FAISS sometimes repeats chunks: index search may return near-duplicate tutor_content entries because L2 distance close; retrieval_node normalizes but does not dedupe aggressively.", None))
    paras.append(("Why summary reuses previous chunks: summary_node intentionally avoids new FAISS calls and only uses previous_successful_chunks from checkpointer to ensure deterministic recap.", None))
    paras.append(("Developer checklist: verify environment variables (.env), ensure PostgreSQL reachable, run startup FAISS rebuild, confirm UI mounted at /ui, monitor logs for router decisions and retrieval counts, update prompts carefully to maintain [ANSWER SECTION]/[SUGGESTIONS SECTION] markers.", None))

    return paras


def build_document_xml(paragraphs: List[Tuple[str, str | None]]) -> str:
    body_xml = "".join(paragraph(text, style) for text, style in paragraphs)
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<w:document xmlns:wpc=\"http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas\" xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" xmlns:o=\"urn:schemas-microsoft-com:office:office\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\" xmlns:m=\"http://schemas.openxmlformats.org/officeDocument/2006/math\" xmlns:v=\"urn:schemas-microsoft-com:vml\" xmlns:wp14=\"http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing\" xmlns:wp=\"http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing\" xmlns:w10=\"urn:schemas-microsoft-com:office:word\" xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" xmlns:wpg=\"http://schemas.microsoft.com/office/word/2010/wordprocessingGroup\" xmlns:wpi=\"http://schemas.microsoft.com/office/word/2010/wordprocessingInk\" xmlns:wne=\"http://schemas.microsoft.com/office/2006/wordml\" xmlns:wps=\"http://schemas.microsoft.com/office/word/2010/wordprocessingShape\" mc:Ignorable=\"w14 wp14\">
  <w:body>
    {body_xml}
    <w:sectPr>
      <w:pgSz w:w=\"12240\" w:h=\"15840\"/>
      <w:pgMar w:top=\"1440\" w:right=\"1440\" w:bottom=\"1440\" w:left=\"1440\" w:header=\"708\" w:footer=\"708\" w:gutter=\"0\"/>
      <w:cols w:space=\"708\"/>
      <w:docGrid w:linePitch=\"360\"/>
    </w:sectPr>
  </w:body>
</w:document>"""


STYLES_XML = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<w:styles xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\" xmlns:w14=\"http://schemas.microsoft.com/office/word/2010/wordml\" xmlns:mc=\"http://schemas.openxmlformats.org/markup-compatibility/2006\" mc:Ignorable=\"w14\">
  <w:style w:type=\"paragraph\" w:default=\"1\" w:styleId=\"Normal\">
    <w:name w:val=\"Normal\"/>
    <w:rsid w:val=\"00000000\"/>
    <w:pPr/>
    <w:rPr/>
  </w:style>
  <w:style w:type=\"paragraph\" w:styleId=\"Heading1\">
    <w:name w:val=\"heading 1\"/>
    <w:basedOn w:val=\"Normal\"/>
    <w:next w:val=\"Normal\"/>
    <w:uiPriority w:val=\"9\"/>
    <w:qFormat/>
    <w:pPr>
      <w:keepNext/>
      <w:keepLines/>
      <w:spacing w:before=\"480\" w:after=\"240\"/>
      <w:outlineLvl w:val=\"0\"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val=\"28\"/>
    </w:rPr>
  </w:style>
  <w:style w:type=\"paragraph\" w:styleId=\"Title\">
    <w:name w:val=\"Title\"/>
    <w:basedOn w:val=\"Normal\"/>
    <w:next w:val=\"Normal\"/>
    <w:uiPriority w:val=\"10\"/>
    <w:qFormat/>
    <w:pPr>
      <w:jc w:val=\"center\"/>
      <w:spacing w:after=\"240\"/>
    </w:pPr>
    <w:rPr>
      <w:b/>
      <w:sz w:val=\"36\"/>
    </w:rPr>
  </w:style>
</w:styles>"""

CONTENT_TYPES = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
  <Override PartName=\"/word/styles.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml\"/>
  <Override PartName=\"/docProps/core.xml\" ContentType=\"application/vnd.openxmlformats-package.core-properties+xml\"/>
  <Override PartName=\"/docProps/app.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.extended-properties+xml\"/>
</Types>"""

RELS = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties\" Target=\"docProps/core.xml\"/>
  <Relationship Id=\"rId3\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties\" Target=\"docProps/app.xml\"/>
</Relationships>"""

DOC_RELS = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles\" Target=\"styles.xml\"/>
</Relationships>"""


def _core_properties(timestamp: str) -> str:
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<cp:coreProperties xmlns:cp=\"http://schemas.openxmlformats.org/package/2006/metadata/core-properties\" xmlns:dc=\"http://purl.org/dc/elements/1.1/\" xmlns:dcterms=\"http://purl.org/dc/terms/\" xmlns:dcmitype=\"http://purl.org/dc/dcmitype/\" xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\">
  <dc:title>Marine Tutor AI Handover</dc:title>
  <dc:creator>Automated Generator</dc:creator>
  <cp:lastModifiedBy>Automated Generator</cp:lastModifiedBy>
  <dcterms:created xsi:type=\"dcterms:W3CDTF\">{timestamp}</dcterms:created>
  <dcterms:modified xsi:type=\"dcterms:W3CDTF\">{timestamp}</dcterms:modified>
</cp:coreProperties>"""


APP = """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Properties xmlns=\"http://schemas.openxmlformats.org/officeDocument/2006/extended-properties\" xmlns:vt=\"http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes\">
  <Application>Marine Tutor AI Handover Generator</Application>
  <DocSecurity>0</DocSecurity>
  <ScaleCrop>false</ScaleCrop>
  <LinksUpToDate>false</LinksUpToDate>
  <SharedDoc>false</SharedDoc>
  <HyperlinksChanged>false</HyperlinksChanged>
  <AppVersion>1.0</AppVersion>
</Properties>"""


def write_docx(paragraphs: List[Tuple[str, str | None]], output_path: Path) -> None:
    timestamp = datetime.now(timezone.utc).isoformat() + "Z"
    document_xml = build_document_xml(paragraphs)
    core_xml = _core_properties(timestamp)

    with ZipFile(output_path, "w", ZIP_DEFLATED) as docx:
        docx.writestr("[Content_Types].xml", CONTENT_TYPES)
        docx.writestr("_rels/.rels", RELS)
        docx.writestr("docProps/core.xml", core_xml)
        docx.writestr("docProps/app.xml", APP)
        docx.writestr("word/document.xml", document_xml)
        docx.writestr("word/styles.xml", STYLES_XML)
        docx.writestr("word/_rels/document.xml.rels", DOC_RELS)



def main() -> None:
    folder_tree_lines = generate_folder_tree((REPO_ROOT / d for d in DEFAULT_ROOT_DIRS))
    paragraphs = build_paragraphs(folder_tree_lines)
    write_docx(paragraphs, OUTPUT_PATH)
    print(f"Generated {OUTPUT_PATH.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()