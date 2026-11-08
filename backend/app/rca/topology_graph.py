"""Topology Graph representation and traversal algorithms for microservice dependencies."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple


@dataclass
class ServiceNodeInfo:
    id: str
    name: str
    tier: str
    downstream: List[str] = field(default_factory=list)  # Services this service calls
    upstream: List[str] = field(default_factory=list)    # Services that call this service


class TopologyGraph:
    """Directed dependency graph representing the microservice communication architecture."""

    def __init__(self):
        self.nodes: Dict[str, ServiceNodeInfo] = {}

    def add_service(self, name: str, tier: str = "business", calls: Optional[List[str]] = None):
        if name not in self.nodes:
            self.nodes[name] = ServiceNodeInfo(id=name, name=name, tier=tier)
        if calls:
            for target in calls:
                self.add_dependency(name, target)

    def add_dependency(self, source: str, target: str):
        if source not in self.nodes:
            self.nodes[source] = ServiceNodeInfo(id=source, name=source, tier="unknown")
        if target not in self.nodes:
            self.nodes[target] = ServiceNodeInfo(id=target, name=target, tier="unknown")

        if target not in self.nodes[source].downstream:
            self.nodes[source].downstream.append(target)
        if source not in self.nodes[target].upstream:
            self.nodes[target].upstream.append(source)

    def get_downstream(self, service: str) -> List[str]:
        return self.nodes[service].downstream if service in self.nodes else []

    def get_upstream(self, service: str) -> List[str]:
        return self.nodes[service].upstream if service in self.nodes else []

    def get_all_services(self) -> List[str]:
        return list(self.nodes.keys())

    def get_descendants(self, service: str) -> Set[str]:
        """Returns all reachable downstream services (transitive closure)."""
        visited = set()
        queue = [service]
        while queue:
            curr = queue.pop(0)
            for neighbor in self.get_downstream(curr):
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        return visited

    def get_ancestors(self, service: str) -> Set[str]:
        """Returns all upstream callers that depend on this service."""
        visited = set()
        queue = [service]
        while queue:
            curr = queue.pop(0)
            for caller in self.get_upstream(curr):
                if caller not in visited:
                    visited.add(caller)
                    queue.append(caller)
        return visited

    @classmethod
    def create_default(cls) -> "TopologyGraph":
        graph = cls()
        graph.add_service("api-gateway", tier="edge", calls=["auth-service", "order-service"])
        graph.add_service("auth-service", tier="security", calls=["redis-cache"])
        graph.add_service("order-service", tier="business", calls=["inventory-service", "payment-service", "postgres-db"])
        graph.add_service("inventory-service", tier="business", calls=["postgres-db"])
        graph.add_service("payment-service", tier="business", calls=["postgres-db", "payment-gateway-external"])
        graph.add_service("postgres-db", tier="persistence", calls=[])
        graph.add_service("redis-cache", tier="cache", calls=[])
        graph.add_service("payment-gateway-external", tier="external", calls=[])
        return graph
