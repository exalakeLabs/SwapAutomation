# Sigma source-swap automation

Two dependency-free Python scripts support promotion from development to production:

- `list_sigma_assets.py` lists every organization-visible workbook and data model, including each asset's sources.
- `create_source_swap_policies.py` idempotently creates deployment source-swap policies. Sigma policies are organization-level and connection-based, so one policy covers every deployed workbook and data model that uses its `fromConnectionId`.

The API identity must be a Sigma Admin for `skipPermissionCheck=true` to inventory the entire organization. Source-swap policies are a Sigma beta feature and must be enabled for the organization.

## Authentication

Use either an existing access token:

```shell
export SIGMA_ACCESS_TOKEN='...'
```

or API client credentials (the scripts obtain the OAuth token):

```shell
export SIGMA_CLIENT_ID='...'
export SIGMA_CLIENT_SECRET='...'
```

Set `SIGMA_BASE_URL` when the organization is not on Sigma's default GCP-US deployment, for example `https://aws-api.sigmacomputing.com`.

## Inventory

```shell
python3 list_sigma_assets.py --output sigma-inventory.json
```

The output retains Sigma's complete asset and source objects, making it suitable for CI artifacts and for discovering the source `connectionId` values that need policies.

## Create policies

Copy `policies.example.json` and add one entry for each development connection found in the inventory. `toConnectionUserAttributeId` is the Sigma user attribute whose value resolves to the destination connection during deployment. Optional `deploymentSwaps` entries can map database/schema/table path segments using the Sigma API payload format.

Preview first (no writes):

```shell
python3 create_source_swap_policies.py policies.json
```

Apply after reviewing the printed payloads:

```shell
python3 create_source_swap_policies.py policies.json --apply
```

The creator reads existing policies and skips a matching deployment policy with the same name and source connection, so rerunning it in CI does not create duplicates.
