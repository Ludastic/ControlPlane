from datetime import datetime

from app.core.security import hash_password
from app.services.checksums import sha256_digest


def build_mock_state(now: datetime) -> dict:
    return {
        "hosts_by_id": {},
        "hosts_by_agent_id": {},
        "hosts_by_token": {},
        "users_by_id": {
            "usr_admin_01": {
                "user_id": "usr_admin_01",
                "username": "admin",
                "password_hash": hash_password("admin"),
                "role": "admin",
                "is_active": True,
                "token_version": 1,
            },
            "usr_operator_01": {
                "user_id": "usr_operator_01",
                "username": "operator",
                "password_hash": hash_password("operator"),
                "role": "operator",
                "is_active": True,
                "token_version": 1,
            },
            "usr_auditor_01": {
                "user_id": "usr_auditor_01",
                "username": "auditor",
                "password_hash": hash_password("auditor"),
                "role": "auditor",
                "is_active": True,
                "token_version": 1,
            },
        },
        "users_by_username": {},
        "inventory_versions": {},
        "inventory_snapshots": {},
        "inventory_history": {},
        "execution_runs": {},
        "audit_logs": [],
        "host_group_memberships": [],
        "groups": {
            "grp_eng": {
                "group_id": "grp_eng",
                "name": "Engineering",
                "description": "Developer workstations",
            }
        },
        "policies": {
            "pol_global_base": {
                "policy_id": "pol_global_base",
                "name": "Base Linux Policy",
                "description": "Base configuration for Linux hosts",
                "priority": 100,
                "is_active": True,
            },
            "pol_group_vpn": {
                "policy_id": "pol_group_vpn",
                "name": "Engineering VPN Policy",
                "description": "VPN configuration for engineering hosts",
                "priority": 200,
                "is_active": True,
            }
        },
        "policy_assignments": {
            "asg_global_base": {
                "assignment_id": "asg_global_base",
                "policy_id": "pol_global_base",
                "target_type": "global",
                "target_id": None,
            },
            "asg_group_vpn": {
                "assignment_id": "asg_group_vpn",
                "policy_id": "pol_group_vpn",
                "target_type": "group",
                "target_id": "grp_eng",
            }
        },
        "policy_resources": {
            "res_bind_base": {
                "resource_id": "res_bind_base",
                "policy_id": "pol_global_base",
                "type": "ansible_playbook",
                "playbook_id": "pb_base",
                "playbook_version": "1.0.0",
                "execution_order": 10,
                "variables": {"timezone": "Europe/Moscow", "ntp_enabled": True},
                "on_failure": "stop",
            },
            "res_bind_vpn": {
                "resource_id": "res_bind_vpn",
                "policy_id": "pol_group_vpn",
                "type": "ansible_playbook",
                "playbook_id": "pb_vpn",
                "playbook_version": "2.0.1",
                "execution_order": 20,
                "variables": {"vpn_server": "vpn.company.local"},
                "on_failure": "continue",
            }
        },
        "playbooks": {
            "pb_base": {
                "playbook_id": "pb_base",
                "name": "base-config",
                "description": "Base workstation setup",
            },
            "pb_vpn": {
                "playbook_id": "pb_vpn",
                "name": "vpn-config",
                "description": "VPN workstation setup",
            },
        },
        "artifacts": {
            "art_base_01": {
                "artifact_id": "art_base_01",
                "name": "base-config",
                "playbook_id": "pb_base",
                "version": "1.0.0",
                "checksum": sha256_digest(b"mock-base-config-archive"),
                "content_type": "application/gzip",
                "size_bytes": 128,
                "filename": "base-config-1.0.0.tar.gz",
                "storage_path": "seed/base-config-1.0.0.tar.gz",
                "content": b"mock-base-config-archive",
            },
            "art_vpn_01": {
                "artifact_id": "art_vpn_01",
                "name": "vpn-config",
                "playbook_id": "pb_vpn",
                "version": "2.0.1",
                "checksum": sha256_digest(b"mock-vpn-config-archive"),
                "content_type": "application/gzip",
                "size_bytes": 120,
                "filename": "vpn-config-2.0.1.tar.gz",
                "storage_path": "seed/vpn-config-2.0.1.tar.gz",
                "content": b"mock-vpn-config-archive",
            },
        },
    }
