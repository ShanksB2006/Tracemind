"""Runbook Knowledge Base and RAG Retrieval Engine.

Indexes markdown SRE playbooks and performs hybrid similarity retrieval to ground
incident investigation and remediation suggestions.
"""
from __future__ import annotations
import glob
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class RunbookChunk:
    doc_id: str
    runbook_title: str
    section_title: str
    content: str
    file_path: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RetrievalResult:
    chunk: RunbookChunk
    score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.chunk.runbook_title,
            "section": self.chunk.section_title,
            "score": round(float(self.score), 4),
            "content": self.chunk.content,
            "source": self.chunk.file_path
        }


class RunbookRetriever:
    """RAG index and retriever for SRE troubleshooting documentation."""

    def __init__(self, runbooks_dir: Optional[str] = None):
        self.runbooks_dir = runbooks_dir or str(
            Path(__file__).resolve().parent.parent.parent.parent / "data" / "runbooks"
        )
        self.chunks: List[RunbookChunk] = []
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.tfidf_matrix: Optional[np.ndarray] = None
        self._load_and_index()

    def _load_and_index(self):
        md_files = glob.glob(f"{self.runbooks_dir}/*.md")
        chunks: List[RunbookChunk] = []

        for fpath in md_files:
            p = Path(fpath)
            content = p.read_text(encoding="utf-8")
            title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            runbook_title = title_match.group(1).strip() if title_match else p.stem

            # Split sections by '## '
            sections = re.split(r"\n##\s+", content)
            for i, sec in enumerate(sections):
                sec = sec.strip()
                if not sec:
                    continue
                lines = sec.split("\n", 1)
                sec_title = lines[0].strip().lstrip("#").strip() if len(lines) > 0 else "Overview"
                sec_body = lines[1].strip() if len(lines) > 1 else lines[0].strip()

                chunk = RunbookChunk(
                    doc_id=f"{p.stem}_{i}",
                    runbook_title=runbook_title,
                    section_title=sec_title,
                    content=f"## {sec_title}\n{sec_body}",
                    file_path=p.name
                )
                chunks.append(chunk)

        self.chunks = chunks

        if self.chunks:
            corpus = [f"{c.runbook_title} {c.section_title} {c.content}" for c in self.chunks]
            self.vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2))
            self.tfidf_matrix = self.vectorizer.fit_transform(corpus)

    def retrieve(self, query: str, top_k: int = 2) -> List[RetrievalResult]:
        if not self.chunks or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        query_vec = self.vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, self.tfidf_matrix).flatten()

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results: List[RetrievalResult] = []

        for idx in top_indices:
            score = float(similarities[idx])
            if score > 0.05:  # Relevance threshold
                results.append(RetrievalResult(chunk=self.chunks[idx], score=score))

        return results
