import json
import os
import argparse
import subprocess
from jinja2 import Environment, FileSystemLoader
from google.cloud import bigquery

def load_config(config_path: str) -> dict:
    """Loads JSON configuration from the provided path."""
    with open(config_path, 'r') as f:
        return json.load(f)

def render_templates(config: dict, template_dir: str) -> list[tuple[str, str]]:
    """Renders Jinja SQL templates with the given configuration dictionary."""
    env = FileSystemLoader(template_dir)
    jinja_env = Environment(loader=env)
    templates = sorted([t for t in os.listdir(template_dir) if t.endswith('.sql.jinja')])
    
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
                print(f"  [DRY RUN] Success. Query will process {bytes_processed} bytes.")
            else:
                query_job.result() # Wait for the job to complete
                print(f"  [EXECUTE] Successfully executed.")
                
        except Exception as e:
            print(f"  [ERROR] Failed to execute {name}:\n{e}")
            raise



def run_go_agent(repo_dir: str, config: dict) -> None:
    """
    Compiles and executes the Go parts-matcher binary.
    Passes core configuration as environment variables so the Go binary remains portable.
    """
    go_agent_dir = os.path.join(repo_dir, 'go-agent')
    print("\n[Go Agent] Compiling Go Agent binary...")
    
    # Check if 'go' command exists in the environment
    is_go_installed = subprocess.run(["which", "go"], capture_output=True).returncode == 0
    if not is_go_installed:
        print("  ❌ 'go' command not found. Ensure the Go toolchain is installed in this runtime environment.")
        raise FileNotFoundError("Go compiler toolchain is missing")

    try:
        subprocess.run(["go", "build", "-o", "parts-matcher", "main.go"], cwd=go_agent_dir, check=True)
        print("  ✅ Compilation successful.")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Compilation failed: {e}")
        raise

    print("[Go Agent] Invoking Go Agent...")
    
    # Prepare environment variables for the Go agent
    env = os.environ.copy()
    env["PROJECT_ID"] = config.get("project_id", "")
    env["DATASET_ID"] = config.get("dataset", "")
    env["MODEL_ID"] = config.get("gemini_text_model_endpoint", "") # Using endpoint as model ID
    env["LOCATION"] = config.get("location", "us-central1") # Default location if not provided
    
    try:
        subprocess.run(["./parts-matcher"], cwd=go_agent_dir, env=env, check=True)
        print("  ✅ Execution successful.")
    except subprocess.CalledProcessError as e:
        print(f"  ❌ Execution failed: {e}")
        raise

def main():
    parser = argparse.ArgumentParser(description="Render and execute BigQuery SQL templates.")
    parser.add_argument("--dry-run", action="store_true", help="Validate queries without executing them.")
    parser.add_argument("--run-agent", action="store_true", default=True, help="Compile and run the Go agent after SQL execution.")
    args = parser.parse_args()

    pipeline_dir = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(pipeline_dir)
    
    # Priority: customer_schema_local.json > customer_schema.json
    config_path = os.path.join(pipeline_dir, 'config', 'customer_schema_local.json')
    if not os.path.exists(config_path):
        config_path = os.path.join(pipeline_dir, 'config', 'customer_schema.json')
    
    template_dir = os.path.join(pipeline_dir, 'sql', 'templates')
    
    prompt_path = os.path.join(pipeline_dir, 'config', 'prompt.txt')
    
    config = load_config(config_path)
    
    with open(prompt_path, 'r') as f:
        config['ai_prompt'] = f.read()

    rendered_queries = render_templates(config, template_dir)
    
    out_dir = os.path.join(pipeline_dir, 'sql', 'rendered_sql')
    os.makedirs(out_dir, exist_ok=True)
    for name, sql in rendered_queries:
        out_name = name.replace('.jinja', '')
        with open(os.path.join(out_dir, out_name), 'w') as f:
            f.write(sql)
            
    print(f"Rendered {len(rendered_queries)} templates.")
    execute_queries(rendered_queries, dry_run=args.dry_run)
    
    if not args.dry_run and args.run_agent:
        run_go_agent(repo_dir, config)

if __name__ == "__main__":
    main()
