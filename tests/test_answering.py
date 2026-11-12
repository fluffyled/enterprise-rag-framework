"""Synthetic unit fixtures; real MIPT benchmark is kept locally."""
import json
from types import SimpleNamespace
import pytest
from answering.contracts import Fragment,read_bundle
from answering.core import sentence_options,validate_selection,generate,NoRedirect
from answering.catalog import validate_topics,read_assignments,csv_text
from answering.web import public_target,extract_page

TEXT="Руководитель подразделения подает заявку на подбор сотрудника."
def fragment(text=TEXT,**kw):return Fragment("chunk-1","doc-1",text,"Учебный пример","п. 3.1",**kw)

def test_contract_roundtrip_and_duplicate_ids():
    f=fragment();assert read_bundle({"schema_version":1,"fragments":[f.to_dict()]})[0].id==f.id
    with pytest.raises(ValueError):read_bundle({"schema_version":1,"fragments":[f.to_dict(),f.to_dict()]})
    with pytest.raises(ValueError):read_bundle({"schema_version":2,"fragments":[]})

@pytest.mark.parametrize("url",["javascript:alert(1)","file:///etc/passwd","https://name:password@example.com"])
def test_source_urls_are_not_executable(url):
    with pytest.raises(ValueError):fragment(url=url)

def test_answer_is_exact_and_ignores_model_prose():
    options=sentence_options([fragment()]);r=validate_selection({"status":"answered","answer_ids":[1],"answer_text":"Придуманное утверждение"},options)
    assert r["answer"][0]["quote"]==TEXT and r["answer"][0]["fragment_id"]=="chunk-1"
    assert "Придуманное" not in json.dumps(r,ensure_ascii=False)

@pytest.mark.parametrize("ids",[[True],[999],[1,1,1]])
def test_invalid_selection_is_rejected(ids):
    with pytest.raises(ValueError):validate_selection({"status":"answered","answer_ids":ids},sentence_options([fragment()]))

def test_insufficient_clears_selected_quotes():
    r=validate_selection({"status":"insufficient","answer_ids":[1],"step_ids":[1]},sentence_options([fragment()]))
    assert not r["answer"] and not r["steps"]

def test_conflict_needs_two_existing_distinct_evidence_ids():
    with pytest.raises(ValueError):validate_selection({"status":"conflict"},sentence_options([fragment()]))
    with pytest.raises(ValueError):validate_selection({"status":"conflict","conflict_pairs":[[1,1]]},sentence_options([fragment()]))

def test_incomplete_form_rows_and_duplicate_overlap_are_removed():
    options=sentence_options([fragment("Подразделение: 3.\n"+TEXT+"\nнезаконченное предложение"),Fragment("chunk-2","doc-1",TEXT,"Учебный пример","стр. 2")])
    assert [o["quote"] for o in options]==[TEXT]


def test_cloud_llm_blocked_and_empty_context_refuses():
    with pytest.raises(ValueError):generate("Вопрос",[fragment()],"https://cloud.example/v1/chat/completions")
    assert generate("Вопрос",[])["status"]=="insufficient"
    with pytest.raises(ValueError):NoRedirect().redirect_request(None,None,302,"",{},"https://cloud.example")


def test_malformed_or_truncated_model_response_is_error(monkeypatch):
    class Response:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps({"choices":[{"finish_reason":"length","message":{"content":"{}"}}]}).encode()
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr("answering.core.urllib.request.build_opener",lambda *args:Opener())
    assert generate("Кто подает заявку?",[fragment()])["status"]=="error"


def test_700_documents_multilabel_csv_and_bom():
    topics=validate_topics({"schema_version":1,"topics":[{"id":"staff","name":"Персонал"},{"id":"finance","name":"Финансы"}]})
    mapping={f"doc-{i}":("staff","finance") for i in range(700)}
    assert read_assignments("\ufeff"+csv_text(mapping),topics)==mapping
    with pytest.raises(ValueError):read_assignments("document_id,topic_ids\ndoc,unknown\n",topics)
    with pytest.raises(ValueError):read_assignments("document_id,topic_ids\ndoc,staff\ndoc,finance\n",topics)


@pytest.mark.parametrize("address",["127.0.0.1","10.0.0.1","169.254.169.254","::1","192.168.1.1"])
def test_public_loader_blocks_private_and_metadata_ips(monkeypatch,address):
    monkeypatch.setattr("answering.web.socket.getaddrinfo",lambda *a,**kw:[(2,1,6,"",(address,443))])
    with pytest.raises(ValueError):public_target("https://example.com/page")


def test_page_scripts_are_not_evidence():
    title,blocks=extract_page(b"<html><title>Example</title><script>SECRET</script><nav>MENU</nav><main><p>Allowed document text.</p></main></html>","text/html","https://example.com")
    assert title=="Example" and blocks[0][0]=="Allowed document text."


def test_topic_filter_is_applied_to_both_retrievers():
    from answering.bridge import BaselineSearch
    calls=[]
    class Encoder:
        def encode(self,*args,**kwargs):return SimpleNamespace(tolist=lambda:[1.0])
    class Search:
        def run(self,**kwargs):calls.append(kwargs["filters"]);return {"documents":[]}
    class Join:
        def run(self,**kwargs):return {"documents":[]}
    adapter=BaselineSearch.__new__(BaselineSearch)
    adapter.retriever=SimpleNamespace(model=Encoder(),bm25=Search(),dense=Search(),join=Join(),ranker=None)
    assert adapter.search("Вопрос",["staff"],{"doc-1":["staff"],"doc-2":["finance"]})==[]
    assert len(calls)==2 and all(c["value"]==["doc-1"] for c in calls)


def test_complete_web_table_row_without_period_is_selectable():
    row="Полное наименование | Учебный институт для проверки интеграции"
    f=fragment(row,url="https://example.com",complete=True)
    assert sentence_options([f])[0]["quote"]==row
    assert sentence_options([fragment(row)])==[]

def test_next_section_number_is_not_in_answer_quote():
    options=sentence_options([fragment(TEXT+" 3.9.")])
    assert options[0]["quote"]==TEXT

def test_html_table_keeps_label_and_value_together():
    title,blocks=extract_page(b"<main><table><tr><td>Label</td><td>Value</td></tr></table></main>","text/html","https://example.com")
    assert blocks[0][0]=="Label | Value"
