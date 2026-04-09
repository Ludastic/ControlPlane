from datetime import datetime


def build_mock_state(now: datetime) -> dict:
    return {
        "hosts_by_id": {},
        "hosts_by_agent_id": {},
        "hosts_by_token": {},
        "inventory_versions": {},
        "inventory_snapshots": {},
        "execution_runs": {},
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
            }
        },
        "policy_assignments": {
            "asg_global_base": {
                "assignment_id": "asg_global_base",
                "policy_id": "pol_global_base",
                "target_type": "global",
                "target_id": None,
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
                "checksum": "sha256:abc123",
                "content_type": "application/gzip",
                "size_bytes": 128,
                "filename": "base-config-1.0.0.tar.gz",
                "content": b"mock-base-config-archive",
            },
            "art_vpn_01": {
                "artifact_id": "art_vpn_01",
                "name": "vpn-config",
                "playbook_id": "pb_vpn",
                "version": "2.0.1",
                "checksum": "sha256:def456",
                "content_type": "application/gzip",
                "size_bytes": 120,
                "filename": "vpn-config-2.0.1.tar.gz",
                "content": b"mock-vpn-config-archive",
            },
        },
    }
