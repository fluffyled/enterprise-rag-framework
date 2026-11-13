"""Быстрый BM25Okapi, эквивалентный haystack InMemoryBM25Retriever.

Haystack при каждом запросе пересчитывает IDF по всему словарю (O(vocab))
и скорит документы в чистом Python (O(N·|Q|)). Здесь статистика корпуса
строится один раз, а запрос скорится векторно через posting lists.
Формула, токенизация и порядок сортировки повторяют haystack 3.5.x,
чтобы top-k списки совпадали побайтово (sorted с kind="stable" —
аналог стабильного sorted Python по невозрастанию score).
"""

import math
import re
import unicodedata
from dataclasses import replace

import numpy as np

_CJK_CHAR_CLASS = (
    r"\u4e00-\u9fff"
    r"\uf900-\ufaff"
    r"\uff66-\uff9f"
    r"\uffa0-\uffdc"
)
_TOKEN_RE = re.compile(rf"[^\W{_CJK_CHAR_CLASS}]+|[{_CJK_CHAR_CLASS}]")


def tokenize(text):
    return _TOKEN_RE.findall(unicodedata.normalize("NFC", (text or "").lower()))


class FastBM25:
    def __init__(self, documents, k1=1.5, b=0.75, epsilon=0.25):
        self.k1 = float(k1)
        self.b = float(b)
        self.epsilon = float(epsilon)
        self.documents = list(documents)
        tokenized = [tokenize(document.content) for document in self.documents]
        self.doc_lens = np.array([len(tokens) for tokens in tokenized], dtype=np.float64)
        self.avgdl = float(self.doc_lens.mean()) if tokenized else 0.0
        self.postings = {}
        df = {}
        for index, tokens in enumerate(tokenized):
            counts = {}
            for token in tokens:
                counts[token] = counts.get(token, 0) + 1
            for token, freq in counts.items():
                column = self.postings.setdefault(token, [[], []])
                column[0].append(index)
                column[1].append(freq)
                df[token] = df.get(token, 0) + 1
        for token, (rows, values) in self.postings.items():
            self.postings[token] = (np.array(rows, dtype=np.int64), np.array(values, dtype=np.float64))
        corpus_size = len(tokenized)
        self.idf = {}
        sum_idf = 0.0
        for token in df:
            value = math.log((corpus_size - df[token] + 0.5) / (df[token] + 0.5))
            self.idf[token] = value
            sum_idf += value
        if self.idf:
            eps = self.epsilon * sum_idf / len(self.idf)
            for token, value in self.idf.items():
                if value < 0:
                    self.idf[token] = eps

    def scores(self, query):
        scores = np.zeros(len(self.documents), dtype=np.float64)
        if not self.documents or self.avgdl == 0:
            return scores
        for token in set(tokenize(query)):
            token_idf = self.idf.get(token)
            if token_idf is None:
                continue
            rows, freqs = self.postings[token]
            norm = freqs + self.k1 * (1 - self.b + self.b * self.doc_lens[rows] / self.avgdl)
            scores[rows] += token_idf * freqs * (1 + self.k1) / norm
        return scores

    def search(self, query, top_k):
        scores = self.scores(query)
        order = np.argsort(-scores, kind="stable")[:top_k]
        results = []
        for index in order:
            results.append(replace(self.documents[index], score=float(scores[index])))
        return results
