from __future__ import annotations

from collections import defaultdict, deque

from backend.schemas.workflow import WorkflowConnection, WorkflowGraph


def inbound_connections(graph: WorkflowGraph) -> dict[tuple[str, str], WorkflowConnection]:
    return {(conn.to.nodeId, conn.to.key): conn for conn in graph.connections}


def outbound_connections(graph: WorkflowGraph) -> dict[tuple[str, str], list[WorkflowConnection]]:
    result: dict[tuple[str, str], list[WorkflowConnection]] = defaultdict(list)
    for conn in graph.connections:
        result[(conn.from_.nodeId, conn.from_.key)].append(conn)
    return result


def topological_order(graph: WorkflowGraph) -> list[str]:
    node_ids = [node.id for node in graph.nodes]
    edges: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    indegree = {node_id: 0 for node_id in node_ids}
    for conn in graph.connections:
        if conn.from_.nodeId not in edges or conn.to.nodeId not in indegree:
            continue
        if conn.from_.nodeId == conn.to.nodeId:
            continue
        if conn.to.nodeId not in edges[conn.from_.nodeId]:
            edges[conn.from_.nodeId].add(conn.to.nodeId)
            indegree[conn.to.nodeId] += 1
    queue = deque([node_id for node_id in node_ids if indegree[node_id] == 0])
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for next_id in edges[node_id]:
            indegree[next_id] -= 1
            if indegree[next_id] == 0:
                queue.append(next_id)
    return order


def has_cycle(graph: WorkflowGraph) -> bool:
    return len(topological_order(graph)) != len(graph.nodes)
