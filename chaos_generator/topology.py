"""Service topology definition and graph representation for microservice simulation."""
from __future__ import annotations
from typing import Dict, List
from .models import ServiceNode


class ServiceTopology:
    """Pre-configured microservice dependency graph used for log generation and RCA verification."""

    def __init__(self):
        self.services: Dict[str, ServiceNode] = {
            "api-gateway": ServiceNode(
                name="api-gateway",
                tier="edge",
                dependencies=["auth-service", "order-service"]
            ),
            "auth-service": ServiceNode(
                name="auth-service",
                tier="security",
                dependencies=["redis-cache"]
            ),
            "order-service": ServiceNode(
                name="order-service",
                tier="business",
                dependencies=["inventory-service", "payment-service", "postgres-db"]
            ),
            "inventory-service": ServiceNode(
                name="inventory-service",
                tier="business",
                dependencies=["postgres-db"]
            ),
            "payment-service": ServiceNode(
                name="payment-service",
                tier="business",
                dependencies=["postgres-db", "payment-gateway-external"]
            ),
            "postgres-db": ServiceNode(
                name="postgres-db",
                tier="persistence",
                dependencies=[]
            ),
            "redis-cache": ServiceNode(
                name="redis-cache",
                tier="cache",
                dependencies=[]
            ),
            "payment-gateway-external": ServiceNode(
                name="payment-gateway-external",
                tier="external",
                dependencies=[]
            )
        }

    def get_dependencies(self, service_name: str) -> List[str]:
        node = self.services.get(service_name)
        return node.dependencies if node else []

    def get_upstream_services(self, service_name: str) -> List[str]:
        """Return services that directly call service_name."""
        return [
            name for name, node in self.services.items()
            if service_name in node.dependencies
        ]

    def to_dict(self) -> Dict[str, List[str]]:
        return {name: node.dependencies for name, node in self.services.items()}
