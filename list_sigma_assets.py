#!/usr/bin/env python3
"""Inventory every Sigma workbook/data model and its data sources."""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sigma_api import SigmaAPIError, SigmaClient


def inventory(client: SigmaClient, workers: int = 8) -> dict[str, Any]:
    models = list(client.paginate("/v2/dataModels", params={"skipPermissionCheck": "true"}))
    workbooks = list(
        client.paginate(
            "/v2/workbooks",
            params={"skipPermissionCheck": "true", "excludeExplorations": "true"},
        )
    )

    jobs = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for model in models:
            model_id = model["dataModelId"]
            jobs.append(("dataModel", model_id, pool.submit(
                lambda value=model_id: list(client.paginate_sources(f"/v2/dataModels/{value}/sources"))
            )))
        for workbook in workbooks:
            workbook_id = workbook["workbookId"]
            jobs.append(("workbook", workbook_id, pool.submit(
                client.request, "GET", f"/v2/workbooks/{workbook_id}/sources"
            )))
        source_lookup = {(kind, asset_id): future.result() for kind, asset_id, future in jobs}

    for model in models:
        model["sources"] = source_lookup[("dataModel", model["dataModelId"])]
    for workbook in workbooks:
        workbook["sources"] = source_lookup[("workbook", workbook["workbookId"])]
    return {"dataModels": models, "workbooks": workbooks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", "-o", help="Write JSON to this file (stdout by default)")
    parser.add_argument("--workers", type=int, default=8, help="Concurrent source requests")
    args = parser.parse_args()
    try:
        result = inventory(SigmaClient.from_env(), max(1, args.workers))
        output = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(output)
            print(f"Wrote {len(result['dataModels'])} data models and "
                  f"{len(result['workbooks'])} workbooks to {args.output}", file=sys.stderr)
        else:
            print(output, end="")
        return 0
    except (SigmaAPIError, ValueError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
