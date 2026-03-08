_REQUIRED_FIELDS = [
    "file_hash",
    "parquet_uri",
    "target_namespace",
    "target_table",
    "original_file_uri",
]

_DEFAULTS = {
    "write_mode": "APPEND",
    "upsert_keys": [],
    "partition_spec": [],
    "schema": [],
}


def parse_load_request(raw: dict) -> dict:
    missing = [f for f in _REQUIRED_FIELDS if not raw.get(f)]
    if missing:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    parsed = dict(raw)
    for key, default in _DEFAULTS.items():
        if key not in parsed or parsed[key] is None:
            parsed[key] = default

    parsed["write_mode"] = parsed["write_mode"].upper()
    if parsed["write_mode"] not in ("APPEND", "OVERWRITE", "UPSERT"):
        raise ValueError(f"Invalid write_mode: {parsed['write_mode']}")

    if parsed["write_mode"] == "UPSERT" and not parsed.get("upsert_keys"):
        raise ValueError("UPSERT write_mode requires upsert_keys")

    return parsed
