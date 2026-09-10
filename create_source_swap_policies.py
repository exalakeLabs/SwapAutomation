#!/usr/bin/env python3
"""Idempotently create Sigma deployment source-swap policies from JSON config."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sigma_api import SigmaAPIError, SigmaClient


def desired_payload(item: dict[str, Any]) -> dict[str, Any]:
    required = ("name", "fromConnectionId", "toConnectionUserAttributeId")
    missing = [key for key in required if not item.get(key)]
    if missing:
        raise ValueError(f"policy missing required field(s): {', '.join(missing)}")
    return {
        "type": "deployment",
        "name": item["name"],
        "fromConnectionId": item["fromConnectionId"],
        "swaps": {
            "toConnection": {
                "swapType": "attribute",
                "userAttributeId": item["toConnectionUserAttributeId"],
            },
            "deploymentSwaps": item.get("deploymentSwaps", []),
        },
    }


def create_policies(client: SigmaClient, config: dict[str, Any], apply: bool) -> list[dict[str, Any]]:
    existing = list(client.paginate("/v2/sourceSwapPolicies"))
    keys = {(p.get("type"), p.get("name"), p.get("fromConnectionId")) for p in existing}
    results = []
    for item in config.get("policies", []):
        payload = desired_payload(item)
        key = (payload["type"], payload["name"], payload["fromConnectionId"])
        if key in keys:
            results.append({"status": "exists", "name": payload["name"]})
        elif apply:
            response = client.request("POST", "/v2/sourceSwapPolicies", json_body=payload)
            results.append({"status": "created", "name": payload["name"], **(response or {})})
            keys.add(key)
        else:
            results.append({"status": "would-create", "name": payload["name"], "payload": payload})
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path, help="Policy JSON file")
    parser.add_argument("--apply", action="store_true", help="Create policies; default is dry-run")
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
        results = create_policies(SigmaClient.from_env(), config, args.apply)
        print(json.dumps(results, indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, SigmaAPIError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
