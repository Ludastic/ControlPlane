from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.artifact import Artifact
from app.models.execution import ExecutionEvent, ExecutionRun
from app.models.group import Group, HostGroupMembership
from app.models.host import Host
from app.models.inventory import InventorySnapshot
from app.models.playbook import Playbook
from app.models.policy import Policy, PolicyAssignment, PolicyResource
from app.models.user import User


def _parse_datetime(value):
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def _group_to_dict(group: Group) -> dict:
    return {"group_id": group.id, "name": group.name, "description": group.description}


def _policy_to_dict(policy: Policy) -> dict:
    return {
        "policy_id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "priority": policy.priority,
        "is_active": policy.is_active,
    }


def _assignment_to_dict(assignment: PolicyAssignment) -> dict:
    target_id = None
    if assignment.target_type == "host":
        target_id = assignment.host_id
    if assignment.target_type == "group":
        target_id = assignment.group_id
    return {
        "assignment_id": assignment.id,
        "policy_id": assignment.policy_id,
        "target_type": assignment.target_type,
        "target_id": target_id,
    }


def _resource_to_dict(resource: PolicyResource) -> dict:
    return {
        "resource_id": resource.id,
        "policy_id": resource.policy_id,
        "type": resource.type,
        "playbook_id": resource.playbook_id,
        "playbook_version": resource.playbook_version,
        "execution_order": resource.execution_order,
        "variables": resource.variables,
        "on_failure": resource.on_failure,
    }


def _playbook_to_dict(playbook: Playbook) -> dict:
    return {"playbook_id": playbook.id, "name": playbook.name, "description": playbook.description}


def _artifact_to_dict(artifact: Artifact, playbook_name: str | None = None) -> dict:
    return {
        "artifact_id": artifact.id,
        "name": playbook_name or artifact.playbook.name,
        "playbook_id": artifact.playbook_id,
        "version": artifact.version,
        "checksum": artifact.checksum,
        "content_type": artifact.content_type,
        "size_bytes": artifact.size_bytes,
        "filename": artifact.storage_path.rsplit("/", 1)[-1],
        "storage_path": artifact.storage_path,
    }


class SqlAlchemyHostRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self):
        return self._session.scalars(select(Host).order_by(Host.hostname)).all()

    def get(self, host_id: str):
        return self._session.get(Host, host_id)

    def get_by_agent_id(self, agent_id: str):
        return self._session.scalar(select(Host).where(Host.agent_id == agent_id))

    def get_by_token_hash(self, token_hash: str):
        return self._session.scalar(select(Host).where(Host.agent_token_hash == token_hash))

    def save(self, host):
        if isinstance(host, Host):
            entity = host
        else:
            entity = self.get(host.host_id) or Host(
                id=host.host_id,
                agent_id=host.agent_id,
                hostname=host.hostname,
                fqdn=host.fqdn,
                status=host.status,
                agent_token_hash=host.token,
                registered_at=host.registered_at,
                last_seen_at=host.last_seen_at,
            )
            entity.agent_id = host.agent_id
            entity.hostname = host.hostname
            entity.fqdn = host.fqdn
            entity.status = host.status
            entity.agent_token_hash = host.token
            entity.registered_at = host.registered_at
            entity.last_seen_at = host.last_seen_at
        self._session.add(entity)
        self._session.flush()
        return entity

    def exists(self, host_id: str) -> bool:
        return self.get(host_id) is not None


class SqlAlchemyInventoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_version(self, host_id: str) -> int | None:
        snapshot = self._session.scalar(
            select(InventorySnapshot).where(InventorySnapshot.host_id == host_id).order_by(InventorySnapshot.version.desc())
        )
        return None if snapshot is None else snapshot.version

    def get_snapshot(self, host_id: str):
        snapshot = self._session.scalar(
            select(InventorySnapshot).where(InventorySnapshot.host_id == host_id).order_by(InventorySnapshot.version.desc())
        )
        return None if snapshot is None else snapshot.payload

    def save_snapshot(self, host_id: str, version: int, snapshot: dict) -> None:
        collected_at = datetime.fromisoformat(snapshot["collected_at"].replace("Z", "+00:00"))
        entity = InventorySnapshot(host_id=host_id, version=version, collected_at=collected_at, payload=snapshot)
        self._session.add(entity)
        self._session.flush()

    def prune_history(self, host_id: str, keep_latest: int) -> None:
        snapshot_ids = self._session.scalars(
            select(InventorySnapshot.id)
            .where(InventorySnapshot.host_id == host_id)
            .order_by(InventorySnapshot.version.desc())
            .offset(keep_latest)
        ).all()
        if snapshot_ids:
            self._session.execute(delete(InventorySnapshot).where(InventorySnapshot.id.in_(snapshot_ids)))
            self._session.flush()

    def list_history(self, host_id: str, limit: int | None = None):
        query = (
            select(InventorySnapshot)
            .where(InventorySnapshot.host_id == host_id)
            .order_by(InventorySnapshot.version.desc())
        )
        if limit is not None:
            query = query.limit(limit)
        snapshots = self._session.scalars(query).all()
        return [{"version": snapshot.version, "payload": snapshot.payload} for snapshot in snapshots]


class SqlAlchemyExecutionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self):
        runs = self._session.scalars(select(ExecutionRun).order_by(ExecutionRun.started_at)).all()
        return [(run.id, self.get(run.id)) for run in runs]

    def get(self, run_id: str):
        run = self._session.get(ExecutionRun, run_id)
        if run is None:
            return None
        return {
            "host_id": run.host_id,
            "state_revision": run.state_revision,
            "started_at": run.started_at,
            "reported_at": run.reported_at,
            "events": [
                {
                    "event_id": event.event_id,
                    "resource_id": event.resource_id,
                    "artifact_id": event.artifact_id,
                    "status": event.status,
                    "started_at": event.started_at,
                    "finished_at": event.finished_at,
                    "message": event.message,
                }
                for event in run.events
            ],
        }

    def save(self, run_id: str, run: dict) -> None:
        entity = self._session.get(ExecutionRun, run_id)
        if entity is None:
            entity = ExecutionRun(
                id=run_id,
                host_id=run["host_id"],
                state_revision=run["state_revision"],
                started_at=_parse_datetime(run["started_at"]),
                reported_at=_parse_datetime(run.get("reported_at")),
            )
            self._session.add(entity)
            self._session.flush()
        else:
            entity.reported_at = _parse_datetime(run.get("reported_at"))
            existing_events = {
                (event.event_id or f"{event.resource_id}|{event.artifact_id}|{event.status}|{event.started_at}|{event.finished_at}|{event.message}"): event
                for event in entity.events
            }
            incoming_keys = set()
            for item in run.get("events", []):
                event_key = item.get("event_id") or f"{item['resource_id']}|{item['artifact_id']}|{item['status']}|{item.get('started_at')}|{item.get('finished_at')}|{item.get('message')}"
                incoming_keys.add(event_key)
                event_entity = existing_events.get(event_key)
                if event_entity is None:
                    self._session.add(
                        ExecutionEvent(
                            run_id=run_id,
                            event_id=item.get("event_id"),
                            resource_id=item["resource_id"],
                            artifact_id=item["artifact_id"],
                            status=item["status"],
                            started_at=_parse_datetime(item.get("started_at")),
                            finished_at=_parse_datetime(item.get("finished_at")),
                            message=item.get("message"),
                        )
                    )
                else:
                    event_entity.event_id = item.get("event_id")
                    event_entity.resource_id = item["resource_id"]
                    event_entity.artifact_id = item["artifact_id"]
                    event_entity.status = item["status"]
                    event_entity.started_at = _parse_datetime(item.get("started_at"))
                    event_entity.finished_at = _parse_datetime(item.get("finished_at"))
                    event_entity.message = item.get("message")
            stale_keys = [key for key in existing_events if key not in incoming_keys]
            for stale_key in stale_keys:
                self._session.delete(existing_events[stale_key])
            self._session.flush()
            return
        for item in run.get("events", []):
            self._session.add(
                ExecutionEvent(
                    run_id=run_id,
                    event_id=item.get("event_id"),
                    resource_id=item["resource_id"],
                    artifact_id=item["artifact_id"],
                    status=item["status"],
                    started_at=_parse_datetime(item.get("started_at")),
                    finished_at=_parse_datetime(item.get("finished_at")),
                    message=item.get("message"),
                )
            )
        self._session.flush()

    def prune_before(self, cutoff: datetime) -> int:
        run_ids = self._session.scalars(
            select(ExecutionRun.id).where(ExecutionRun.started_at < cutoff)
        ).all()
        if not run_ids:
            return 0
        self._session.execute(delete(ExecutionRun).where(ExecutionRun.id.in_(run_ids)))
        self._session.flush()
        return len(run_ids)


class SqlAlchemyGroupRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self):
        return [_group_to_dict(group) for group in self._session.scalars(select(Group).order_by(Group.name)).all()]

    def get(self, group_id: str):
        group = self._session.get(Group, group_id)
        return None if group is None else _group_to_dict(group)

    def save(self, group):
        entity = self._session.get(Group, group["group_id"])
        if entity is None:
            entity = Group(id=group["group_id"], name=group["name"], description=group.get("description"))
        else:
            entity.name = group["name"]
            entity.description = group.get("description")
        self._session.add(entity)
        self._session.flush()
        return _group_to_dict(entity)

    def delete(self, group) -> None:
        entity = self._session.get(Group, group["group_id"])
        if entity is not None:
            self._session.delete(entity)
            self._session.flush()

    def add_host_membership(self, host_id: str, group_id: str) -> None:
        existing = self._session.scalar(
            select(HostGroupMembership).where(
                HostGroupMembership.host_id == host_id,
                HostGroupMembership.group_id == group_id,
            )
        )
        if existing is None:
            self._session.add(HostGroupMembership(host_id=host_id, group_id=group_id))
            self._session.flush()

    def list_host_group_ids(self, host_id: str):
        return self._session.scalars(
            select(HostGroupMembership.group_id).where(HostGroupMembership.host_id == host_id)
        ).all()


class SqlAlchemyPolicyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self):
        return [_policy_to_dict(policy) for policy in self._session.scalars(select(Policy).order_by(Policy.name)).all()]

    def get(self, policy_id: str):
        policy = self._session.get(Policy, policy_id)
        return None if policy is None else _policy_to_dict(policy)

    def save(self, policy):
        entity = self._session.get(Policy, policy["policy_id"])
        if entity is None:
            entity = Policy(
                id=policy["policy_id"],
                name=policy["name"],
                description=policy.get("description"),
                priority=policy["priority"],
                is_active=policy["is_active"],
            )
        else:
            entity.name = policy["name"]
            entity.description = policy.get("description")
            entity.priority = policy["priority"]
            entity.is_active = policy["is_active"]
        self._session.add(entity)
        self._session.flush()
        return _policy_to_dict(entity)

    def delete(self, policy) -> None:
        entity = self._session.get(Policy, policy["policy_id"])
        if entity is not None:
            self._session.delete(entity)
            self._session.flush()

    def list_assignments(self, policy_id: str):
        rows = self._session.scalars(select(PolicyAssignment).where(PolicyAssignment.policy_id == policy_id)).all()
        return [_assignment_to_dict(row) for row in rows]

    def list_all_assignments(self):
        rows = self._session.scalars(select(PolicyAssignment)).all()
        return [_assignment_to_dict(row) for row in rows]

    def get_assignment(self, assignment_id: str):
        row = self._session.get(PolicyAssignment, assignment_id)
        return None if row is None else _assignment_to_dict(row)

    def save_assignment(self, assignment: dict):
        entity = self._session.get(PolicyAssignment, assignment["assignment_id"])
        target_type = assignment["target_type"]
        host_id = assignment["target_id"] if target_type == "host" else None
        group_id = assignment["target_id"] if target_type == "group" else None
        if entity is None:
            entity = PolicyAssignment(
                id=assignment["assignment_id"],
                policy_id=assignment["policy_id"],
                target_type=target_type,
                host_id=host_id,
                group_id=group_id,
            )
        else:
            entity.target_type = target_type
            entity.host_id = host_id
            entity.group_id = group_id
        self._session.add(entity)
        self._session.flush()
        return _assignment_to_dict(entity)

    def delete_assignment(self, assignment_id: str) -> None:
        row = self._session.get(PolicyAssignment, assignment_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def list_resources(self, policy_id: str):
        rows = self._session.scalars(select(PolicyResource).where(PolicyResource.policy_id == policy_id)).all()
        return [_resource_to_dict(row) for row in rows]

    def list_all_resources(self):
        rows = self._session.scalars(select(PolicyResource)).all()
        return [_resource_to_dict(row) for row in rows]

    def get_resource(self, resource_id: str):
        row = self._session.get(PolicyResource, resource_id)
        return None if row is None else _resource_to_dict(row)

    def save_resource(self, resource: dict):
        entity = self._session.get(PolicyResource, resource["resource_id"])
        if entity is None:
            entity = PolicyResource(
                id=resource["resource_id"],
                policy_id=resource["policy_id"],
                type=resource["type"],
                playbook_id=resource["playbook_id"],
                playbook_version=resource["playbook_version"],
                execution_order=resource["execution_order"],
                variables=resource["variables"],
                on_failure=resource["on_failure"],
            )
        else:
            entity.type = resource["type"]
            entity.playbook_id = resource["playbook_id"]
            entity.playbook_version = resource["playbook_version"]
            entity.execution_order = resource["execution_order"]
            entity.variables = resource["variables"]
            entity.on_failure = resource["on_failure"]
        self._session.add(entity)
        self._session.flush()
        return _resource_to_dict(entity)

    def delete_resource(self, resource_id: str) -> None:
        row = self._session.get(PolicyResource, resource_id)
        if row is not None:
            self._session.delete(row)
            self._session.flush()


class SqlAlchemyPlaybookRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self):
        return [_playbook_to_dict(playbook) for playbook in self._session.scalars(select(Playbook).order_by(Playbook.name)).all()]

    def get(self, playbook_id: str):
        playbook = self._session.get(Playbook, playbook_id)
        return None if playbook is None else _playbook_to_dict(playbook)

    def save(self, playbook):
        entity = self._session.get(Playbook, playbook["playbook_id"])
        if entity is None:
            entity = Playbook(id=playbook["playbook_id"], name=playbook["name"], description=playbook.get("description"))
        else:
            entity.name = playbook["name"]
            entity.description = playbook.get("description")
        self._session.add(entity)
        self._session.flush()
        return _playbook_to_dict(entity)

    def delete(self, playbook) -> None:
        entity = self._session.get(Playbook, playbook["playbook_id"])
        if entity is not None:
            self._session.delete(entity)
            self._session.flush()


class SqlAlchemyArtifactRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, artifact_id: str):
        artifact = self._session.get(Artifact, artifact_id)
        return None if artifact is None else _artifact_to_dict(artifact)

    def list_by_playbook(self, playbook_id: str):
        rows = self._session.scalars(select(Artifact).where(Artifact.playbook_id == playbook_id).order_by(Artifact.version)).all()
        return [_artifact_to_dict(row) for row in rows]

    def get_by_playbook_version(self, playbook_id: str, version: str):
        row = self._session.scalar(select(Artifact).where(Artifact.playbook_id == playbook_id, Artifact.version == version))
        return None if row is None else _artifact_to_dict(row)

    def list_all(self):
        rows = self._session.scalars(select(Artifact).order_by(Artifact.playbook_id, Artifact.version)).all()
        return [_artifact_to_dict(row) for row in rows]

    def save(self, artifact):
        entity = self._session.get(Artifact, artifact["artifact_id"])
        storage_path = artifact["storage_path"]
        if entity is None:
            entity = Artifact(
                id=artifact["artifact_id"],
                playbook_id=artifact["playbook_id"],
                version=artifact["version"],
                checksum=artifact["checksum"],
                content_type=artifact["content_type"],
                size_bytes=artifact["size_bytes"],
                storage_path=storage_path,
            )
        else:
            entity.version = artifact["version"]
            entity.checksum = artifact["checksum"]
            entity.content_type = artifact["content_type"]
            entity.size_bytes = artifact["size_bytes"]
            entity.storage_path = storage_path
        self._session.add(entity)
        self._session.flush()
        return _artifact_to_dict(entity, playbook_name=artifact.get("name"))


class SqlAlchemyUserRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, user_id: str):
        user = self._session.get(User, user_id)
        if user is None:
            return None
        return {
            "user_id": user.id,
            "username": user.username,
            "password_hash": user.password_hash,
            "role": user.role,
            "is_active": user.is_active,
            "token_version": user.token_version,
        }

    def get_by_username(self, username: str):
        user = self._session.scalar(select(User).where(User.username == username))
        if user is None:
            return None
        return {
            "user_id": user.id,
            "username": user.username,
            "password_hash": user.password_hash,
            "role": user.role,
            "is_active": user.is_active,
            "token_version": user.token_version,
        }

    def save(self, user: dict):
        entity = self._session.get(User, user["user_id"])
        if entity is None:
            entity = User(
                id=user["user_id"],
                username=user["username"],
                password_hash=user["password_hash"],
                role=user["role"],
                is_active=user["is_active"],
                token_version=user["token_version"],
            )
        else:
            entity.username = user["username"]
            entity.password_hash = user["password_hash"]
            entity.role = user["role"]
            entity.is_active = user["is_active"]
            entity.token_version = user["token_version"]
        self._session.add(entity)
        self._session.flush()
        return {
            "user_id": entity.id,
            "username": entity.username,
            "password_hash": entity.password_hash,
            "role": entity.role,
            "is_active": entity.is_active,
            "token_version": entity.token_version,
        }


class SqlAlchemyAuditLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(
        self,
        *,
        user_id: str | None = None,
        entity_type: str | None = None,
        action: str | None = None,
        limit: int | None = None,
    ):
        query = select(AuditLog).order_by(AuditLog.created_at.desc())
        if user_id is not None:
            query = query.where(AuditLog.actor_user_id == user_id)
        if entity_type is not None:
            query = query.where(AuditLog.entity_type == entity_type)
        if action is not None:
            query = query.where(AuditLog.action == action)
        if limit is not None:
            query = query.limit(limit)
        rows = self._session.scalars(query).all()
        return [
            {
                "audit_id": row.id,
                "actor_user_id": row.actor_user_id,
                "actor_username": row.actor_username,
                "action": row.action,
                "entity_type": row.entity_type,
                "entity_id": row.entity_id,
                "details": row.details,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def save(self, entry: dict):
        entity = AuditLog(
            id=entry["audit_id"],
            actor_user_id=entry["actor_user_id"],
            actor_username=entry["actor_username"],
            action=entry["action"],
            entity_type=entry["entity_type"],
            entity_id=entry.get("entity_id"),
            details=entry.get("details"),
            created_at=_parse_datetime(entry["created_at"]),
        )
        self._session.add(entity)
        self._session.flush()
        return entry

    def prune_before(self, cutoff: datetime) -> int:
        result = self._session.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
        self._session.flush()
        return result.rowcount or 0


class SqlAlchemyRepositoryBundle:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.hosts = SqlAlchemyHostRepository(session)
        self.users = SqlAlchemyUserRepository(session)
        self.inventory = SqlAlchemyInventoryRepository(session)
        self.execution = SqlAlchemyExecutionRepository(session)
        self.groups = SqlAlchemyGroupRepository(session)
        self.policies = SqlAlchemyPolicyRepository(session)
        self.playbooks = SqlAlchemyPlaybookRepository(session)
        self.artifacts = SqlAlchemyArtifactRepository(session)
        self.audit_logs = SqlAlchemyAuditLogRepository(session)

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()

    def close(self) -> None:
        self.session.close()
