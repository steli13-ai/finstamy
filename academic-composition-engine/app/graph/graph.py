from datetime import datetime, timezone
from time import perf_counter

from langgraph.graph import StateGraph, END
from langgraph.types import Command
from app.graph.state import ProjectState
from app.graph.nodes import (
    intake_parser,
    outline_planner,
    human_review_gate,
    source_ingest,
    source_chunker,
    source_indexer,
    query_generator,
    retrieval_runner,
    rerank_runner,
    evidence_builder,
    claim_planner,
    section_writer,
    devils_advocate,
    citation_resolver,
    evidence_validator,
    final_language_qa,
    export_docx,
)
from app.services.checkpointer import get_checkpointer


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _instrument_node(node_name: str, fn):
    llm_nodes = {"intake_parser", "claim_planner", "section_writer"}

    def wrapped(state: ProjectState):
        started_at = _utc_now()
        t0 = perf_counter()
        output = fn(state) or {}
        node_meta = output.pop("__node_meta__", {}) if isinstance(output, dict) else {}

        ended_at = _utc_now()
        duration_ms = int((perf_counter() - t0) * 1000)

        model = node_meta.get("model")
        if not model and state.get("use_ollama", False) and node_name in llm_nodes:
            model = state.get("ollama_model")

        trace = {
            "node_name": node_name,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "model": model,
            "prompt_hash": node_meta.get("prompt_hash"),
            "fallback_used": bool(node_meta.get("fallback_used", False)),
            "input_refs": node_meta.get("input_refs", []),
            "output_refs": node_meta.get("output_refs", []),
            "error": node_meta.get("error"),
            "retry_count": int(node_meta.get("retry_count", 0)),
        }

        traces = list(state.get("node_traces", []))
        traces.append(trace)

        if isinstance(output, Command):
            base_update = output.update if isinstance(output.update, dict) else {}
            merged_update = {**base_update, "node_traces": traces}
            return Command(
                graph=output.graph,
                update=merged_update,
                resume=output.resume,
                goto=output.goto,
            )

        output["node_traces"] = traces
        return output

    return wrapped


def build_graph():
    g = StateGraph(ProjectState)

    g.add_node("intake_parser", _instrument_node("intake_parser", intake_parser.run))
    g.add_node("outline_planner", _instrument_node("outline_planner", outline_planner.run))
    g.add_node("review_after_outline", _instrument_node("review_after_outline", human_review_gate.review_after_outline))
    g.add_node("source_ingest", _instrument_node("source_ingest", source_ingest.run))
    g.add_node("source_chunker", _instrument_node("source_chunker", source_chunker.run))
    g.add_node("source_indexer", _instrument_node("source_indexer", source_indexer.run))
    g.add_node("query_generator", _instrument_node("query_generator", query_generator.run))
    g.add_node("retrieval_runner", _instrument_node("retrieval_runner", retrieval_runner.run))
    g.add_node("rerank_runner", _instrument_node("rerank_runner", rerank_runner.run))
    g.add_node("evidence_builder", _instrument_node("evidence_builder", evidence_builder.run))
    g.add_node("devils_advocate_evidence", _instrument_node("devils_advocate_evidence", devils_advocate.run))
    g.add_node("review_after_evidence", _instrument_node("review_after_evidence", human_review_gate.review_after_evidence))
    g.add_node("claim_planner", _instrument_node("claim_planner", claim_planner.run))
    g.add_node("section_writer", _instrument_node("section_writer", section_writer.run))
    g.add_node("citation_resolver", _instrument_node("citation_resolver", citation_resolver.run))
    g.add_node("evidence_validator", _instrument_node("evidence_validator", evidence_validator.run))
    g.add_node("review_pre_export", _instrument_node("review_pre_export", human_review_gate.review_pre_export))
    g.add_node("final_language_qa", _instrument_node("final_language_qa", final_language_qa.run))
    g.add_node("export_docx", _instrument_node("export_docx", export_docx.run))

    g.set_entry_point("intake_parser")
    g.add_edge("intake_parser", "outline_planner")
    g.add_edge("outline_planner", "review_after_outline")
    g.add_edge("review_after_outline", "source_ingest")
    g.add_edge("source_ingest", "source_chunker")
    g.add_edge("source_chunker", "source_indexer")
    g.add_edge("source_indexer", "query_generator")
    g.add_edge("query_generator", "retrieval_runner")
    g.add_edge("retrieval_runner", "rerank_runner")
    g.add_edge("rerank_runner", "evidence_builder")
    g.add_edge("evidence_builder", "devils_advocate_evidence")
    g.add_edge("devils_advocate_evidence", "review_after_evidence")
    g.add_edge("review_after_evidence", "claim_planner")
    g.add_edge("claim_planner", "section_writer")
    g.add_edge("section_writer", "citation_resolver")
    g.add_edge("citation_resolver", "evidence_validator")
    g.add_edge("evidence_validator", "review_pre_export")
    g.add_edge("review_pre_export", "final_language_qa")
    g.add_edge("final_language_qa", "export_docx")
    g.add_edge("export_docx", END)

    return g.compile(checkpointer=get_checkpointer())