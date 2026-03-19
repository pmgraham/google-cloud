import json
import os
import argparse
import subprocess
import uuid
from jinja2 import Environment, FileSystemLoader
from google.cloud import bigquery


def load_config(config_path: str) -> dict:
    """Loads JSON configuration from the provided path."""
    with open(config_path, "r") as f:
        return json.load(f)


def render_templates(config: dict, template_dir: str) -> list[tuple[str, str]]:
    """Renders Jinja SQL templates with the given configuration dictionary."""
    env = FileSystemLoader(template_dir)
    jinja_env = Environment(loader=env)
    templates = sorted(
        [t for t in os.listdir(template_dir) if t.endswith(".sql.jinja")]
    )

    rendered_queries = []
    for template_name in templates:
        template = jinja_env.get_template(template_name)
        rendered_sql = template.render(**config)
        rendered_queries.append((template_name, rendered_sql))

    return rendered_queries


def execute_queries(rendered_queries: list[tuple[str, str]], dry_run: bool) -> None:
    """Executes strings of SQL queries sequentially against BigQuery."""
    client = bigquery.Client()

    for name, sql in rendered_queries:
        print(f"Processing {name}...")
        try:
            job_config = bigquery.QueryJobConfig()
            if dry_run:
                job_config.dry_run = True
                job_config.use_query_cache = False

            query_job = client.query(sql, job_config=job_config)

            if dry_run:
                bytes_processed = query_job.total_bytes_processed
                print(
                    f"  [DRY RUN] Success. Query will process {bytes_processed} bytes."
                )
            else:
                query_job.result()  # Wait for the job to complete
                print("  [EXECUTE] Successfully executed.")

        except Exception as e:
            print(f"  [ERROR] Failed to execute {name}:\n{e}")
            raise


def run_go_agent(repo_dir: str, config: dict) -> None:
    """
    Compiles and executes the Go parts-matcher binary.
    Passes core configuration as environment variables so the Go binary remains portable.
    """
    go_agent_dir = os.path.join(repo_dir, "go-agent")
    print("\n[Go Agent] Compiling Go Agent binary...")

    # Check if 'go' command exists in the environment
    is_go_installed = (
        subprocess.run(["which", "go"], capture_output=True).returncode == 0
    )
    if not is_go_installed:
        print(
            "  ❌ 'go' command not found. Ensure the Go toolchain is installed in this runtime environment."
        )
        raise FileNotFoundError("Go compiler toolchain is missing")

    try:
        subprocess.run(
            ["go", "build", "-o", "parts-matcher", "main.go"],
            cwd=go_agent_dir,
            check=True,
        )
        print("  ✅ Compilation successful.")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Compilation failed: {e}")
        raise

    print("[Go Agent] Invoking Go Agent...")

    # Prepare environment variables for the Go agent
    env = os.environ.copy()
    env["PROJECT_ID"] = config.get("project_id", "")
    env["DATASET_ID"] = config.get("dataset", "")
    env["MODEL_ID"] = config.get(
        "gemini_text_model_endpoint", ""
    )  # Using endpoint as model ID
    env["LOCATION"] = config.get(
        "location", "us-central1"
    )  # Default location if not provided

    try:
        subprocess.run(["./parts-matcher"], cwd=go_agent_dir, env=env, check=True)
        print("  ✅ Execution successful.")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Execution failed: {e}")
        raise


def record_pipeline_start(config: dict, dry_run: bool) -> str:
    """Creates the pipeline_runtime table if it doesn't exist and records the start time."""
    if dry_run:
        print("[DRY RUN] Would create pipeline_runtime table and record start time.")
        return "dry-run-id"

    client = bigquery.Client(project=config.get("project_id"))
    table_id = f"{config.get('project_id')}.{config.get('dataset')}.pipeline_runtime"

    schema = [
        bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("finished_at", "TIMESTAMP", mode="NULLABLE"),
    ]
    table = bigquery.Table(table_id, schema=schema)
    client.create_table(table, exists_ok=True)

    run_id = str(uuid.uuid4())
    query = f"""
        INSERT INTO `{config.get("project_id")}.{config.get("dataset")}.pipeline_runtime` (run_id, started_at)
        VALUES ('{run_id}', CURRENT_TIMESTAMP())
    """
    client.query(query).result()
    print(f"[Runtime Tracking] Pipeline started. Run ID: {run_id}")
    return run_id


def record_pipeline_finish(config: dict, run_id: str, dry_run: bool) -> None:
    """Updates the pipeline_runtime table with the finish time for the given run_id."""
    if dry_run:
        print("[DRY RUN] Would update pipeline_runtime table and record finish time.")
        return

    client = bigquery.Client(project=config.get("project_id"))
    query = f"""
        UPDATE `{config.get("project_id")}.{config.get("dataset")}.pipeline_runtime`
        SET finished_at = CURRENT_TIMESTAMP()
        WHERE run_id = '{run_id}'
    """
    client.query(query).result()
    print(f"[Runtime Tracking] Pipeline finished. Run ID: {run_id}")


AGENT_BOUNDARY = "05"


def split_phases(rendered_queries: list[tuple[str, str]]) -> tuple[list, list]:
    """Split rendered queries into pre-agent and post-agent phases."""
    pre_agent = []
    post_agent = []
    for name, sql in rendered_queries:
        if name < AGENT_BOUNDARY:
            pre_agent.append((name, sql))
        else:
            post_agent.append((name, sql))
    return pre_agent, post_agent


def main():
    parser = argparse.ArgumentParser(
        description="Render and execute BigQuery SQL templates."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate queries without executing them.",
    )
    parser.add_argument(
        "--run-agent",
        action="store_true",
        default=True,
        help="Compile and run the Go agent after pre-agent SQL execution.",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        default=False,
        help="Skip the Go agent (useful for re-running post-agent steps only).",
    )
    parser.add_argument(
        "--post-agent-only",
        action="store_true",
        default=False,
        help="Skip pre-agent SQL and Go agent; run only post-agent steps (05+).",
    )
    args = parser.parse_args()

    pipeline_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(pipeline_dir)

    config_path = os.path.join(pipeline_dir, "config", "customer_schema_local.json")
    if not os.path.exists(config_path):
        config_path = os.path.join(pipeline_dir, "config", "customer_schema.json")

    template_dir = os.path.join(pipeline_dir, "sql", "templates")
    prompt_path = os.path.join(pipeline_dir, "config", "prompt.txt")

    config = load_config(config_path)

    with open(prompt_path, "r") as f:
        config["ai_prompt"] = f.read()

    run_id = record_pipeline_start(config, args.dry_run)

    rendered_queries = render_templates(config, template_dir)

    out_dir = os.path.join(pipeline_dir, "sql", "rendered_sql")
    os.makedirs(out_dir, exist_ok=True)
    for name, sql in rendered_queries:
        out_name = name.replace(".jinja", "")
        with open(os.path.join(out_dir, out_name), "w") as f:
            f.write(sql)

    pre_agent, post_agent = split_phases(rendered_queries)

    print(f"Rendered {len(rendered_queries)} templates ({len(pre_agent)} pre-agent, {len(post_agent)} post-agent).")

    if not args.post_agent_only:
        print("\n" + "=" * 60)
        print("PHASE 1: PRE-AGENT SQL")
        print("=" * 60)
        execute_queries(pre_agent, dry_run=args.dry_run)

        if not args.dry_run and args.run_agent and not args.skip_agent:
            print("\n" + "=" * 60)
            print("PHASE 2: GO AGENT")
            print("=" * 60)
            run_go_agent(repo_dir, config)

    print("\n" + "=" * 60)
    print("PHASE 3: POST-AGENT SQL (clustering, canonical IDs, reporting)")
    print("=" * 60)
    execute_queries(post_agent, dry_run=args.dry_run)

    record_pipeline_finish(config, run_id, args.dry_run)


if __name__ == "__main__":
    main()
