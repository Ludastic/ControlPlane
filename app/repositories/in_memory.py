from datetime import datetime

from app.repositories.mock_data import build_mock_state


class InMemoryRepository:
    def __init__(self, now: datetime) -> None:
        state = build_mock_state(now)
        self.hosts_by_id = state["hosts_by_id"]
        self.hosts_by_agent_id = state["hosts_by_agent_id"]
        self.hosts_by_token = state["hosts_by_token"]
        self.inventory_versions = state["inventory_versions"]
        self.inventory_snapshots = state["inventory_snapshots"]
        self.execution_runs = state["execution_runs"]
        self.groups = state["groups"]
        self.policies = state["policies"]
        self.policy_assignments = state["policy_assignments"]
        self.policy_resources = state["policy_resources"]
        self.playbooks = state["playbooks"]
        self.artifacts = state["artifacts"]
