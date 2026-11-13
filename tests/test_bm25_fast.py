import random

from haystack import Document
from haystack.components.retrievers.in_memory import InMemoryBM25Retriever
from haystack.document_stores.in_memory import InMemoryDocumentStore

from navigator.bm25_fast import FastBM25


def build_store(documents):
    store = InMemoryDocumentStore(embedding_similarity_function="cosine", bm25_algorithm="BM25Okapi")
    store.write_documents(documents)
    return store


def sample_documents(seed=42, count=300):
    random.seed(seed)
    words = [
        "приказ", "регламент", "смета", "бюджет", "подразделение", "сотрудник",
        "командировка", "отпуск", "договор", "закупка", "technology", "report",
        "budget", "order", "policy", "employee", "travel", "contract", "purchase",
    ]
    documents = []
    for index in range(count):
        text = " ".join(random.choices(words, k=random.randint(5, 60)))
        documents.append(Document(content=text, meta={"chunk_id": f"chunk-{index}"}))
    return documents


def test_fast_bm25_matches_haystack_ranking():
    documents = sample_documents()
    store = build_store(documents)
    reference = InMemoryBM25Retriever(store, top_k=20)
    fast = FastBM25(documents)
    queries = [
        "Кто утверждает смету бюджета подразделения?",
        "travel policy employee contract",
        "несуществующее_слово бюджет",
        "приказ приказ приказ смета",
        "Как оформить командировку, и кто подписывает договор закупки?",
    ]
    for query in queries:
        expected = reference.run(query=query)["documents"]
        actual = fast.search(query, top_k=20)
        assert [document.id for document in expected] == [document.id for document in actual], query
        for expected_document, actual_document in zip(expected, actual):
            assert expected_document.score == actual_document.score or abs(expected_document.score - actual_document.score) < 1e-9, query


def test_fast_bm25_handles_empty_and_tiny_documents():
    documents = [Document(content=""), Document(content="одно"), Document(content="одно два два")]
    store = build_store(documents)
    reference = InMemoryBM25Retriever(store, top_k=3)
    fast = FastBM25(documents)
    for query in ("одно", "два", "пусто"):
        expected = [document.id for document in reference.run(query=query)["documents"]]
        actual = [document.id for document in fast.search(query, top_k=3)]
        assert expected == actual, query


def test_fast_bm25_faster_on_repeated_queries():
    import time

    documents = sample_documents(count=2000)
    store = build_store(documents)
    reference = InMemoryBM25Retriever(store, top_k=20)
    fast = FastBM25(documents)
    query = "приказ смета бюджет договор"
    reference.run(query=query)
    fast.search(query, top_k=20)
    started = time.perf_counter()
    for _ in range(20):
        reference.run(query=query)
    reference_seconds = time.perf_counter() - started
    started = time.perf_counter()
    for _ in range(20):
        fast.search(query, top_k=20)
    fast_seconds = time.perf_counter() - started
    assert fast_seconds < reference_seconds
