from __future__ import annotations

from datetime import datetime

from app.repositories.mock_data import build_mock_state


class HostRepository:
    def __init__(self, state: dict) -> None:
        self.by_id = state["hosts_by_id"]
        self.by_agent_id = state["hosts_by_agent_id"]
        self.by_token = state["hosts_by_token"]

    def list_all(self):
        return list(self.by_id.values())

    def get(self, host_id: str):
        return self.by_id.get(host_id)

    def get_by_agent_id(self, agent_id: str):
        return self.by_agent_id.get(agent_id)

    def get_by_token_hash(self, token_hash: str):
        return self.by_token.get(token_hash)

    def save(self, host):
        existing = self.by_id.get(host.host_id)
        if existing is not None:
            self.by_agent_id.pop(existing.agent_id, None)
            stale_tokens = [token for token, stored_host in self.by_token.items() if stored_host.host_id == host.host_id]
            for stale_token in stale_tokens:
                self.by_token.pop(stale_token, None)
        self.by_id[host.host_id] = host
        self.by_agent_id[host.agent_id] = host
        if host.token is not None:
            self.by_token[host.token] = host
        return host

    def exists(self, host_id: str) -> bool:
        return host_id in self.by_id


class InventoryRepository:
    def __init__(self, state: dict) -> None:
        self.versions = state["inventory_versions"]
        self.snapshots = state["inventory_snapshots"]
        self.history = state["inventory_history"]

    def get_version(self, host_id: str) -> int | None:
        return self.versions.get(host_id)

    def get_snapshot(self, host_id: str):
        return self.snapshots.get(host_id)

    def save_snapshot(self, host_id: str, version: int, snapshot: dict) -> None:
        self.versions[host_id] = version
        self.snapshots[host_id] = snapshot
        self.history.setdefault(host_id, []).append({"version": version, "payload": snapshot})

    def prune_history(self, host_id: str, keep_latest: int) -> None:
        items = self.history.get(host_id, [])
        if len(items) > keep_latest:
            self.history[host_id] = items[-keep_latest:]

    def list_history(self, host_id: str, limit: int | None = None):
        items = list(reversed(self.history.get(host_id, [])))
        if limit is not None:
            items = items[:limit]
        return items


class ExecutionRepository:
    def __init__(self, state: dict) -> None:
        self.runs = state["execution_runs"]

    def list_all(self):
        return self.runs.items()

    def get(self, run_id: str):
        return self.runs.get(run_id)

    def save(self, run_id: str, run: dict) -> None:
        self.runs[run_id] = run

    def prune_before(self, cutoff: datetime) -> int:
        stale_ids = [run_id for run_id, run in self.runs.items() if run["started_at"] < cutoff]
        for run_id in stale_ids:
            self.runs.pop(run_id, None)
        return len(stale_ids)


class GroupRepository:
    def __init__(self, state: dict) -> None:
        self.items = state["groups"]
        self.memberships = state["host_group_memberships"]

    def list_all(self):
        return list(self.items.values())

    def get(self, group_id: str):
        return self.items.get(group_id)

    def save(self, group):
        key = group["group_id"] if isinstance(group, dict) else group.id
        self.items[key] = group
        return group

    def delete(self, group) -> None:
        key = group["group_id"] if isinstance(group, dict) else group.id
        self.items.pop(key, None)

    def add_host_membership(self, host_id: str, group_id: str) -> None:
        membership = {"host_id": host_id, "group_id": group_id}
        if membership not in self.memberships:
            self.memberships.append(membership)

    def list_host_group_ids(self, host_id: str):
        return [membership["group_id"] for membership in self.memberships if membership["host_id"] == host_id]


class PolicyRepository:
    def __init__(self, state: dict) -> None:
        self.items = state["policies"]
        self.assignments = state["policy_assignments"]
        self.resources = state["policy_resources"]

    def list_all(self):
        return list(self.items.values())

    def get(self, policy_id: str):
        return self.items.get(policy_id)

    def save(self, policy):
        key = policy["policy_id"] if isinstance(policy, dict) else policy.id
        self.items[key] = policy
        return policy

    def delete(self, policy) -> None:
        key = policy["policy_id"] if isinstance(policy, dict) else policy.id
        self.items.pop(key, None)

    def list_assignments(self, policy_id: str):
        return [assignment for assignment in self.assignments.values() if assignment["policy_id"] == policy_id]

    def list_all_assignments(self):
        return list(self.assignments.values())

    def get_assignment(self, assignment_id: str):
        return self.assignments.get(assignment_id)

    def save_assignment(self, assignment: dict):
        self.assignments[assignment["assignment_id"]] = assignment
        return assignment

    def delete_assignment(self, assignment_id: str) -> None:
        self.assignments.pop(assignment_id, None)

    def list_resources(self, policy_id: str):
        return [resource for resource in self.resources.values() if resource["policy_id"] == policy_id]

    def list_all_resources(self):
        return list(self.resources.values())

    def get_resource(self, resource_id: str):
        return self.resources.get(resource_id)

    def save_resource(self, resource: dict):
        self.resources[resource["resource_id"]] = resource
        return resource

    def delete_resource(self, resource_id: str) -> None:
        self.resources.pop(resource_id, None)


class PlaybookRepository:
    def __init__(self, state: dict) -> None:
        self.items = state["playbooks"]

    def list_all(self):
        return list(self.items.values())

    def get(self, playbook_id: str):
        return self.items.get(playbook_id)

    def save(self, playbook):
        key = playbook["playbook_id"] if isinstance(playbook, dict) else playbook.id
        self.items[key] = playbook
        return playbook

    def delete(self, playbook) -> None:
        key = playbook["playbook_id"] if isinstance(playbook, dict) else playbook.id
        self.items.pop(key, None)


class ArtifactRepository:
    def __init__(self, state: dict) -> None:
        self.items = state["artifacts"]

    def get(self, artifact_id: str):
        return self.items.get(artifact_id)

    def list_by_playbook(self, playbook_id: str):
        return [artifact for artifact in self.items.values() if artifact["playbook_id"] == playbook_id]

    def get_by_playbook_version(self, playbook_id: str, version: str):
        for artifact in self.items.values():
            if artifact["playbook_id"] == playbook_id and artifact["version"] == version:
                return artifact
        return None

    def list_all(self):
        return list(self.items.values())

    def save(self, artifact):
        key = artifact["artifact_id"] if isinstance(artifact, dict) else artifact.id
        self.items[key] = artifact
        return artifact


class UserRepository:
    def __init__(self, state: dict) -> None:
        self.by_id = state["users_by_id"]
        self.by_username = state["users_by_username"]
        for user in self.by_id.values():
            self.by_username[user["username"]] = user

    def get(self, user_id: str):
        return self.by_id.get(user_id)

    def get_by_username(self, username: str):
        return self.by_username.get(username)

    def save(self, user: dict):
        self.by_id[user["user_id"]] = user
        self.by_username[user["username"]] = user
        return user


class AuditLogRepository:
    def __init__(self, state: dict) -> None:
        self.items = state["audit_logs"]

    def list_all(
        self,
        *,
        user_id: str | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        limit: int | None = None,
    ):
        items = list(reversed(self.items))
        if user_id is not None:
            items = [item for item in items if item["actor_user_id"] == user_id]
        if entity_type is not None:
            items = [item for item in items if item["entity_type"] == entity_type]
        if action is not None:
            items = [item for item in items if item["action"] == action]
        if limit is not None:
            items = items[:limit]
        return items

    def save(self, entry: dict):
        self.items.append(entry)
        return entry

    def prune_before(self, cutoff: datetime) -> int:
        original_len = len(self.items)
        self.items[:] = [item for item in self.items if item["created_at"] >= cutoff]
        return original_len - len(self.items)


class InMemoryRepository:
    def __init__(self, now: datetime) -> None:
        state = build_mock_state(now)
        self.hosts = HostRepository(state)
        self.users = UserRepository(state)
        self.inventory = InventoryRepository(state)
        self.execution = ExecutionRepository(state)
        self.groups = GroupRepository(state)
        self.policies = PolicyRepository(state)
        self.playbooks = PlaybookRepository(state)
        self.artifacts = ArtifactRepository(state)
        self.audit_logs = AuditLogRepository(state)
