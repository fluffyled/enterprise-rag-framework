import json
import re
import urllib.parse
import urllib.request

from .query_analysis import decompose_question
from .selection import similarity


def adaptive_analysis(question, documents, config):
    settings = config["retrieval"]
    scores = [document.meta.get("rerank_score") for document in documents if document.meta.get("rerank_score") is not None]
    top_score = max(scores) if scores else float("-inf")
    unique_documents = len({document.meta.get("document_id") or document.meta.get("relative_path") or document.meta.get("name") for document in documents[:6]})
    independent = 0
    for index, document in enumerate(documents[:6]):
        if all(similarity(document, other) < 0.8 for other in documents[:index]):
            independent += 1
    reasons = []
    if len(documents) < settings["adaptive_min_candidates"]:
        reasons.append("few_candidates")
    if independent < settings["adaptive_min_candidates"]:
        reasons.append("few_independent_candidates")
    if unique_documents < settings["adaptive_min_unique_documents"]:
        reasons.append("few_documents")
    if top_score < settings["adaptive_min_score"]:
        reasons.append("low_relative_relevance")
    return {"sufficient": not reasons, "reasons": reasons, "top_score": top_score, "independent_candidates": independent, "unique_documents": unique_documents}


def query_expansion(question):
    tasks = decompose_question(question)
    queries = [task.text for task in tasks if task.text != question]
    if not queries:
        rewritten = re.sub(r"^(какой|какая|какие|кто|когда|как)\s+", "", question.strip(), flags=re.IGNORECASE).rstrip("?")
        replacements = [("срок", "в течение дней"), ("кто", "ответственный"), ("когда", "дата или срок")]
        for source, target in replacements:
            if source in rewritten.lower():
                rewritten = re.sub(source, target, rewritten, flags=re.IGNORECASE)
                break
        if rewritten and rewritten != question:
            queries.append(rewritten)
    return queries[:2]


def local_query_plan(question, endpoint=None, timeout=90):
    endpoint = endpoint or "http://127.0.0.1:8080/v1/chat/completions"
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1", "llm"):
        raise ValueError("Query Planner разрешён только на локальном endpoint")
    schema = {"type": "object", "properties": {"queries": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 2}}, "required": ["queries"], "additionalProperties": False}
    payload = {"messages": [{"role": "system", "content": "Rewrite the user search query into one or two short retrieval queries. Always return queries. Preserve every constraint, use only facts present in the question, and never answer it."}, {"role": "user", "content": question}], "temperature": 0, "max_tokens": 160, "response_format": {"type": "json_object", "schema": schema}}
    import time
    for attempt in range(3):
        try:
            request = urllib.request.Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                content = json.load(response)["choices"][0]["message"]["content"]
            break
        except urllib.error.URLError:
            if attempt == 2:
                raise
            time.sleep(0.5)
    queries = json.loads(content).get("queries", [])
    if not isinstance(queries, list):
        raise ValueError("Query Planner вернул некорректный список")
    result = [query.strip() for query in queries[:2] if isinstance(query, str) and query.strip()]
    if not result:
        raise ValueError("Query Planner не вернул поисковых переписываний")
    return result
