"""Algorithmic Prefix-Tree Log Parser based on the Drain algorithm.

Paper: 'Drain: An Online Log Parsing Approach with Fixed Depth Tree' (ICWS 2017)
Converts unstructured log messages into structured event clusters and templates.
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple


class LogCluster:
    def __init__(self, cluster_id: str, log_template_tokens: List[str]):
        self.cluster_id: str = cluster_id
        self.log_template_tokens: List[str] = log_template_tokens
        self.size: int = 1

    @property
    def template_str(self) -> str:
        return " ".join(self.log_template_tokens)


class Node:
    def __init__(self):
        self.children: Dict[str, Node] = {}
        self.clusters: List[LogCluster] = []


class DrainParser:
    """Fixed-depth prefix tree log template miner."""

    def __init__(self, depth: int = 4, sim_threshold: float = 0.5, max_children: int = 100):
        self.depth = depth  # max depth of tree
        self.sim_threshold = sim_threshold
        self.max_children = max_children
        self.root = Node()
        self.clusters: List[LogCluster] = []
        self._cluster_counter = 0

        # Regex rules for variable masking
        self.mask_patterns = [
            (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "<IP>"),
            (re.compile(r"\b[0-9a-fA-F]{8,32}\b"), "<HEX>"),
            (re.compile(r"\b\d+\b"), "<NUM>"),
            (re.compile(r"\/[a-zA-Z0-9_\-\.\/]+"), "<PATH>"),
        ]

    def _preprocess(self, message: str) -> List[str]:
        cleaned = message.strip()
        for pattern, replacement in self.mask_patterns:
            cleaned = pattern.sub(replacement, cleaned)
        return cleaned.split()

    def _get_similarity(self, seq1: List[str], seq2: List[str]) -> Tuple[float, int]:
        if len(seq1) != len(seq2):
            return 0.0, 0
        matching_tokens = 0
        for token1, token2 in zip(seq1, seq2):
            if token1 == token2:
                matching_tokens += 1
            elif token1 == "<*>" or token2 == "<*>":
                matching_tokens += 1
        similarity = matching_tokens / max(1, len(seq1))
        return similarity, matching_tokens

    def _update_template(self, template: List[str], new_tokens: List[str]) -> List[str]:
        updated = []
        for t1, t2 in zip(template, new_tokens):
            if t1 == t2:
                updated.append(t1)
            else:
                updated.append("<*>")
        return updated

    def parse(self, raw_message: str) -> Tuple[str, str]:
        """Parses a log message and returns (cluster_id, template_string)."""
        tokens = self._preprocess(raw_message)
        token_len = len(tokens)
        if token_len == 0:
            return "E0", "<EMPTY>"

        # Step 1: Traverse tree by token length
        curr_node = self.root
        len_key = str(token_len)
        if len_key not in curr_node.children:
            curr_node.children[len_key] = Node()
        curr_node = curr_node.children[len_key]

        # Step 2: Traverse by prefix tokens up to depth
        max_prefix_depth = min(self.depth - 1, token_len)
        for i in range(max_prefix_depth):
            token = tokens[i]
            # If token contains digits or masks, map to wildcard branch
            if any(char.isdigit() for char in token) or "<" in token:
                token = "<*>"
            if token not in curr_node.children:
                if len(curr_node.children) >= self.max_children:
                    token = "<*>"
                else:
                    curr_node.children[token] = Node()
            curr_node = curr_node.children[token]

        # Step 3: Find best matching cluster in leaf node
        best_cluster: Optional[LogCluster] = None
        max_similarity = -1.0

        for cluster in curr_node.clusters:
            sim, _ = self._get_similarity(cluster.log_template_tokens, tokens)
            if sim > max_similarity:
                max_similarity = sim
                best_cluster = cluster

        # Step 4: Add to best cluster or create new cluster
        if best_cluster is not None and max_similarity >= self.sim_threshold:
            best_cluster.log_template_tokens = self._update_template(
                best_cluster.log_template_tokens, tokens
            )
            best_cluster.size += 1
            return best_cluster.cluster_id, best_cluster.template_str
        else:
            self._cluster_counter += 1
            new_id = f"E{self._cluster_counter}"
            new_cluster = LogCluster(new_id, list(tokens))
            curr_node.clusters.append(new_cluster)
            self.clusters.append(new_cluster)
            return new_id, new_cluster.template_str
