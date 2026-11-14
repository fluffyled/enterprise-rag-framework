"""Normalize the legacy and G2 paths into one grounded answer."""
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Literal

from answering.v2 import AnswerInputV1, generate_v2
from answering.v2.pipeline import Settings

from .answer import answer
from .evidence_adapter import validate_citation

G2_SETTINGS = Settings(input_chars=1900, max_output_tokens=1450, plan_requirements=True,
                       preserve_alternatives=True, repair_attempts=0, fail_on_batch_error=True,
                       max_facts_per_batch=4, structured_fields=True, scoped_summary=True)


@dataclass
class AnswerResponse:
    status: Literal["answered", "partial", "insufficient", "conflict", "error"]
    summary: list[dict] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    sources: list[dict] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    missing_requirements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    diagnostics: dict = field(default_factory=dict)
    error: str = ""


class GenerationService:
    def generate(self, question, evidence, mode):
        response = AnswerResponse("insufficient")
        if not evidence:
            return response
        by_id = {item.id: item for item in evidence}
        sources = {}

        def cite(identifier, quote):
            item = by_id[identifier]
            validate_citation(item, quote)
            source = sources.setdefault(identifier, {
                "id": identifier, "document_id": item.document_id,
                "document_title": item.document_title, "document_version": item.document_version,
                "locator": item.locator, "source_spans": item.source_spans, "source_hash": item.source_hash,
                "node_id": item.node_id, "parent_id": item.parent_id, "section_path": item.section_path,
                "excerpt": item.full_text, "quotes": [], "incomplete": False, **item.metadata,
            })
            if quote not in source["quotes"]:
                source["quotes"].append(quote)
            return identifier

        if mode == "legacy":
            result = answer(question, [SimpleNamespace(content=item.full_text) for item in evidence])
            if result["status"] == "error":
                return AnswerResponse("error", error=f"LLM: {result['error']}",
                                      diagnostics={"transport_error": result.get("transport_error", False)})

            def legacy_citation(position, quote):
                if type(position) is not int or not 1 <= position <= len(evidence):
                    raise ValueError("Некорректный номер источника")
                return cite(evidence[position - 1].id, quote)

            def legacy_item(item):
                return {"text": item["quote"], "citations": [legacy_citation(item["source"], item["quote"])]}

            response.summary = [legacy_item(item) for item in result["answer"]]
            response.steps = [{"id": f"S{i}", **legacy_item(item)} for i, item in enumerate(result["steps"], 1)]
            for pair in result["conflicts"]:
                response.conflicts.append({"text": f"{pair['left_quote']} / {pair['right_quote']}",
                    "citations": [legacy_citation(pair[side], pair[side + "_quote"]) for side in ("left", "right")]})
            response.status = ("conflict" if response.conflicts else
                               "partial" if response.summary or response.steps else "insufficient")
        elif mode == "g2":
            result = generate_v2(AnswerInputV1(question=question, evidence=evidence), settings=G2_SETTINGS)
            response.diagnostics["trace"] = result.trace
            response.diagnostics["review_issues"] = result.verification.issues
            if detail := result.trace.get("transport_detail"):
                response.diagnostics["transport_detail"] = detail
            if result.status == "error":
                response.status = "error"
                response.error = "LLM: генерация или проверка ответа завершилась ошибкой."
                if result.trace.get("transport_error"):
                    response.diagnostics["transport_error"] = True
                return response
            if result.trace.get("transport_error"):
                response.warnings.append("Локальная модель стала недоступна во время обработки вопроса. "
                                         "Показана часть ответа, которую удалось сверить с источниками.")
            # Quote provenance and review by the same model cannot establish completeness.
            response.status = "partial" if result.status == "answered" else result.status
            facts = {fact.id: fact for fact in result.claims}

            def fact_item(fact):
                return {"text": fact.text, "citations": list(dict.fromkeys(
                    cite(c.evidence_id, c.quote) for c in fact.citations))}

            summary = [facts[identifier] for identifier in result.summary.fact_ids]
            response.summary = [fact_item(fact) for fact in summary]
            for step in result.steps:
                row = step.model_dump(exclude={"fact_ids", "evidence_ids", "requirement_ids", "dependency_citations"})
                fact = facts[step.fact_ids[0]]
                response.steps.append({**row, **fact_item(fact), "action": fact.action or step.action})
            for identifier in result.trace.get("conflict_evidence_ids", []):
                item = by_id[identifier]
                response.conflicts.append({"text": "Источник возможного противоречия",
                                           "citations": [cite(identifier, item.full_text)]})
            response.missing_requirements = [f"{gap.suggested_query} — {gap.reason}" for gap in result.missing_requirements]
            response.warnings.append("G2 экспериментальный. Независимая смысловая проверка ответа не выполнена.")
        else:
            raise ValueError("Неизвестный режим генерации")
        response.sources = list(sources.values())
        response.warnings.append("Актуальность редакций документов требует проверки.")
        if any(item["incomplete"] for item in response.sources):
            response.warnings.append("Часть источников представлена неполными фрагментами.")
        return response
