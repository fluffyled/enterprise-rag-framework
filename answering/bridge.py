"""Temporary adapter to developer 1 baseline; public answering contract is separate."""
import json
from pathlib import Path
from .contracts import Fragment
from .catalog import DATA


def external_sources():
    path = DATA / "external_sources.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def save_external(fragments, info):
    sources = [x for x in external_sources() if x["info"]["document_id"] != info["document_id"]]
    sources.append({"info": info, "fragments": [f.to_dict() for f in fragments]})
    DATA.mkdir(exist_ok=True)
    temp = DATA / "external_sources.tmp"
    temp.write_text(json.dumps(sources,ensure_ascii=False,indent=2),encoding="utf-8")
    temp.replace(DATA / "external_sources.json")


def documents():
    result = {}
    manifest = DATA / "manifest.json"
    if manifest.exists():
        for item in json.loads(manifest.read_text(encoding="utf-8"))["files"]:
            result[item["sha256"]] = {"document_id": item["sha256"], "title": item["name"], "url": None}
    for item in external_sources():
        info = item["info"]
        result[info["document_id"]] = {"document_id": info["document_id"], "title": info["title"], "url": info["url"]}
    return result


class BaselineSearch:
    def __init__(self):
        from navigator.retrieval import Retriever
        from haystack import Document
        self.retriever = Retriever()
        for source in external_sources():
            docs=[]
            for row in source["fragments"]:
                f=Fragment(**row)
                docs.append(Document(id=f.id,content=f.text,meta={"sha256":f.document_id,"name":f.title,"locator":f.locator,"url":f.url,"order":f.order,"complete":f.complete}))
            if docs:
                vectors=self.retriever.model.encode(["passage: "+d.meta["name"]+" "+d.content for d in docs],normalize_embeddings=True,batch_size=16)
                for d,v in zip(docs,vectors): d.embedding=v.tolist()
                self.retriever.store.write_documents(docs)

    def search(self, question, selected_topics=(), mapping=None):
        mapping=mapping or {}
        filters=None
        if selected_topics:
            allowed=[doc for doc,topics in mapping.items() if set(topics)&set(selected_topics)]
            if not allowed:return []
            filters={"field":"meta.sha256","operator":"in","value":allowed}
        r=self.retriever
        q=r.model.encode("query: "+question,normalize_embeddings=True).tolist()
        sparse=r.bm25.run(query=question,filters=filters)["documents"]
        dense=r.dense.run(query_embedding=q,filters=filters)["documents"]
        docs=r.join.run(documents=[sparse,dense])["documents"]
        if r.ranker and docs:
            scores=r.ranker.predict([(question,d.content) for d in docs])
            docs=[d for _,d in sorted(zip(scores,docs),key=lambda pair:float(pair[0]),reverse=True)]
        result=[]
        for d in docs[:6]:
            m=d.meta;doc=m["sha256"]
            result.append(Fragment(d.id,doc,d.content,m["name"],m["locator"],tuple(mapping.get(doc,())),m.get("url"),m.get("date_hint"),m.get("order",m.get("page",0)*100000+m.get("word_start",0)),complete=m.get("complete",False)))
        return result
