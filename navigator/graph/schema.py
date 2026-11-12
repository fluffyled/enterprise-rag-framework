from dataclasses import asdict, dataclass, field


NODE_TYPES = {"document", "document_version", "section", "clause", "attachment"}
RELATIONS = {"references", "amends", "supersedes", "repeals", "supplements", "contains"}


@dataclass
class Node:
    id: str
    type: str
    document_id: str
    title: str
    version_id: str | None = None
    locator: str | None = None

    def __post_init__(self):
        if self.type not in NODE_TYPES:
            raise ValueError("Неизвестный тип узла")


@dataclass
class Edge:
    source_id: str
    target_id: str
    relation: str
    evidence: str
    evidence_span: dict
    status: str = "confirmed_textual_reference"
    constraints: dict = field(default_factory=dict)

    def __post_init__(self):
        if self.relation not in RELATIONS:
            raise ValueError("Неизвестный тип связи")


def serialize_graph(nodes, edges):
    return {"schema_version": 1, "nodes": [asdict(node) for node in nodes], "edges": [asdict(edge) for edge in edges], "semantic_warning": "Edges are textual candidates, not proof of legal force"}
