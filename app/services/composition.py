from __future__ import annotations

import hashlib
import json

from fastapi import status

from app.core.errors import AppError


SCOPE_WEIGHTS = {"global": 1, "group": 2, "host": 3}


def collect_applicable_policies(repo, host_id: str) -> list[dict]:
    group_ids = set(repo.groups.list_host_group_ids(host_id))
    policy_by_id = {policy["policy_id"]: policy for policy in repo.policies.list_all() if policy["is_active"]}
    applicable: list[dict] = []

    for assignment in repo.policies.list_all_assignments():
        policy = policy_by_id.get(assignment["policy_id"])
        if policy is None:
            continue

        scope = assignment["target_type"]
        target_id = assignment["target_id"]
        applies = (
            scope == "global"
            or (scope == "host" and target_id == host_id)
            or (scope == "group" and target_id in group_ids)
        )
        if not applies:
            continue

        applicable.append(
            {
                "policy_id": policy["policy_id"],
                "name": policy["name"],
                "description": policy.get("description"),
                "priority": policy["priority"],
                "scope": scope,
                "target_id": target_id,
                "scope_weight": SCOPE_WEIGHTS[scope],
            }
        )

    applicable.sort(key=lambda item: (item["scope_weight"], item["priority"], item["policy_id"]))
    return applicable


def build_desired_state_payload(repo, host_id: str) -> dict:
    applicable = collect_applicable_policies(repo, host_id)
    resource_map: dict[str, dict] = {}

    for policy in applicable:
        for resource in repo.policies.list_resources(policy["policy_id"]):
            artifact = repo.artifacts.get_by_playbook_version(resource["playbook_id"], resource["playbook_version"])
            if artifact is None:
                continue

            resource_key = resource["playbook_id"]
            candidate = {
                "resource_id": resource["resource_id"],
                "type": resource["type"],
                "name": artifact["name"],
                "artifact": {
                    "artifact_id": artifact["artifact_id"],
                    "playbook_id": artifact["playbook_id"],
                    "version": artifact["version"],
                    "checksum": artifact["checksum"],
                    "download_url": f"/api/v1/agent/artifacts/{artifact['artifact_id']}/download",
                },
                "execution_order": resource["execution_order"],
                "variables": resource["variables"],
                "timeout_seconds": 600,
                "on_failure": resource["on_failure"],
                "_scope_weight": policy["scope_weight"],
                "_priority": policy["priority"],
                "_scope": policy["scope"],
                "_policy_id": policy["policy_id"],
            }
            current = resource_map.get(resource_key)
            if current is None:
                resource_map[resource_key] = candidate
                continue

            same_rank = (
                current["_scope_weight"] == candidate["_scope_weight"]
                and current["_priority"] == candidate["_priority"]
            )
            if same_rank and _resource_conflicts(current, candidate):
                raise AppError(
                    status_code=status.HTTP_409_CONFLICT,
                    code="CONFIGURATION_CONFLICT",
                    message=f"Conflicting policies detected for host {host_id}",
                    details={
                        "resource_key": resource_key,
                        "current_policy_id": current["_policy_id"],
                        "incoming_policy_id": candidate["_policy_id"],
                        "scope": candidate["_scope"],
                        "priority": candidate["_priority"],
                    },
                )

            if _should_override(current, candidate):
                resource_map[resource_key] = candidate

    resources = sorted(resource_map.values(), key=lambda item: (item["execution_order"], item["resource_id"]))
    for item in resources:
        item.pop("_scope_weight", None)
        item.pop("_priority", None)
        item.pop("_scope", None)
        item.pop("_policy_id", None)

    checksum_source = json.dumps(
        {"host_id": host_id, "resources": resources},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    checksum_value = hashlib.sha256(checksum_source).hexdigest()
    revision = max(1, int(checksum_value[:8], 16))

    return {
        "host_id": host_id,
        "revision": revision,
        "checksum": f"sha256:{checksum_value}",
        "resources": resources,
        "effective_policies": applicable,
    }


def _resource_conflicts(current: dict, candidate: dict) -> bool:
    comparable_keys = ("artifact", "execution_order", "variables", "on_failure", "type")
    return any(current[key] != candidate[key] for key in comparable_keys)


def _should_override(current: dict, candidate: dict) -> bool:
    current_rank = (current["_scope_weight"], current["_priority"])
    candidate_rank = (candidate["_scope_weight"], candidate["_priority"])
    return candidate_rank >= current_rank
