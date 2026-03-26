#!/usr/bin/env python3
"""
ops.py — Operations CLI for Health API infrastructure.

Automates common tasks across staging and production environments:
health checks, pipeline run management, log tailing, rollbacks,
and cost estimates.

Usage:
    ./scripts/ops.py status
    ./scripts/ops.py runs list --status queued
    ./scripts/ops.py runs create SAMPLE-001
    ./scripts/ops.py logs production --tail 50
    ./scripts/ops.py rollback production
    ./scripts/ops.py costs
"""

import argparse
import json
import subprocess
import sys
import urllib.request
import urllib.error


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENVS = {
    "staging": {"namespace": "staging"},
    "production": {"namespace": "production"},
}

GCP_PROJECT = "lucasj-contracts"
GCP_REGION = "us-central1"
CLUSTER = "health-api-cluster"
APP_LABEL = "app.kubernetes.io/name=health-api"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def run(cmd, capture=True, check=True):
    """Run a shell command and return stdout."""
    result = subprocess.run(
        cmd, shell=True, capture_output=capture, text=True, check=check
    )
    return result.stdout.strip() if capture else None


def get_external_ip(namespace):
    """Get the LoadBalancer external IP for a namespace."""
    try:
        ip = run(
            f"kubectl get svc health-api -n {namespace} "
            f"-o jsonpath='{{.status.loadBalancer.ingress[0].ip}}'"
        )
        return ip if ip else None
    except subprocess.CalledProcessError:
        return None


def api_get(ip, path):
    """Make a GET request to the API."""
    try:
        req = urllib.request.Request(f"http://{ip}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError):
        return None


def api_post(ip, path, data):
    """Make a POST request to the API."""
    try:
        body = json.dumps(data).encode()
        req = urllib.request.Request(
            f"http://{ip}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (urllib.error.URLError, TimeoutError):
        return None


def print_header(text):
    print(f"\n\033[1m{text}\033[0m")


def print_ok(text):
    print(f"  \033[32m✓\033[0m {text}")


def print_fail(text):
    print(f"  \033[31m✗\033[0m {text}")


def print_info(text):
    print(f"  {text}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_status(args):
    """Show health and resource status across all environments."""
    print_header("Health API — Status Overview")

    for env, conf in ENVS.items():
        ns = conf["namespace"]
        print_header(f"[{env.upper()}]")

        # Pod status
        try:
            pods_json = run(
                f"kubectl get pods -n {ns} -l {APP_LABEL} "
                f"-o json"
            )
            pods = json.loads(pods_json)
            total = len(pods.get("items", []))
            ready = sum(
                1 for p in pods.get("items", [])
                if all(
                    c.get("ready", False)
                    for c in p.get("status", {}).get("containerStatuses", [])
                )
            )
            if ready == total and total > 0:
                print_ok(f"Pods: {ready}/{total} ready")
            else:
                print_fail(f"Pods: {ready}/{total} ready")
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            print_fail("Pods: unable to fetch")

        # HPA
        try:
            hpa = run(
                f"kubectl get hpa health-api -n {ns} "
                f"-o jsonpath='{{.status.currentReplicas}}/{{.spec.maxReplicas}}'"
            )
            print_info(f"HPA: {hpa} replicas")
        except subprocess.CalledProcessError:
            print_info("HPA: not found")

        # External IP + health check
        ip = get_external_ip(ns)
        if ip:
            print_info(f"IP: {ip}")
            health = api_get(ip, "/health")
            if health and health.get("status") == "healthy":
                print_ok(f"Health: {health['status']} | DB: {health.get('database', 'unknown')}")
            elif health:
                print_fail(f"Health: {health.get('status', 'unknown')}")
            else:
                print_fail("Health: unreachable")
        else:
            print_fail("IP: no external IP assigned")

        # Resource quota
        try:
            quota = run(
                f"kubectl get resourcequota -n {ns} "
                f"-o jsonpath='{{.items[0].status.used.pods}}/{{.items[0].status.hard.pods}}'"
            )
            print_info(f"Quota: {quota} pods used")
        except subprocess.CalledProcessError:
            pass


def cmd_runs_list(args):
    """List pipeline runs from the API."""
    env = args.env or "production"
    ip = get_external_ip(ENVS[env]["namespace"])
    if not ip:
        print_fail(f"Cannot reach {env} — no external IP")
        return

    path = "/api/runs"
    if args.status:
        path += f"?status={args.status}"

    runs = api_get(ip, path)
    if runs is None:
        print_fail("Failed to fetch runs")
        return

    if not runs:
        print_info("No runs found.")
        return

    print_header(f"Pipeline Runs — {env}")
    print(f"  {'ID':<6} {'SAMPLE':<20} {'STATUS':<12} {'DURATION':<10} {'CREATED'}")
    print(f"  {'─'*6} {'─'*20} {'─'*12} {'─'*10} {'─'*20}")
    for r in runs:
        duration = f"{r['duration']:.1f}s" if r.get("duration") else "—"
        created = r.get("created_at", "")[:19]
        print(f"  {r['id']:<6} {r['sample_id']:<20} {r['status']:<12} {duration:<10} {created}")


def cmd_runs_create(args):
    """Create a new pipeline run."""
    env = args.env or "production"
    ip = get_external_ip(ENVS[env]["namespace"])
    if not ip:
        print_fail(f"Cannot reach {env} — no external IP")
        return

    result = api_post(ip, "/api/runs", {"sample_id": args.sample_id})
    if result:
        print_ok(f"Created run #{result['id']} for sample {result['sample_id']} ({env})")
    else:
        print_fail("Failed to create run")


def cmd_logs(args):
    """Tail logs from an environment."""
    env = args.env
    ns = ENVS[env]["namespace"]
    tail = args.tail or 50

    print_header(f"Logs — {env} (last {tail} lines)")
    run(
        f"kubectl logs -l {APP_LABEL} -n {ns} --tail={tail} --all-containers",
        capture=False,
        check=False,
    )


def cmd_rollback(args):
    """Rollback to the previous Helm release."""
    env = args.env
    ns = ENVS[env]["namespace"]

    print_header(f"Rollback — {env}")

    # Show current history
    print_info("Release history:")
    run(f"helm history health-api -n {ns} --max 5", capture=False, check=False)

    if args.yes:
        confirm = "y"
    else:
        confirm = input(f"\n  Rollback {env} to previous revision? [y/N] ")

    if confirm.lower() == "y":
        print_info("Rolling back...")
        run(f"helm rollback health-api -n {ns}", capture=False, check=False)
        print_ok(f"Rollback initiated for {env}")
    else:
        print_info("Cancelled.")


def cmd_costs(args):
    """Estimate monthly GCP costs for the infrastructure."""
    print_header("Cost Estimate — Health API Infrastructure")
    print()

    costs = []

    # GKE
    try:
        node_count = run(
            "kubectl get nodes -o json | "
            "python3 -c \"import sys,json; print(len(json.load(sys.stdin)['items']))\""
        )
        gke_cost = 74.40 + (int(node_count) * 25.0)
        costs.append(("GKE Autopilot (control plane + nodes)", gke_cost))
    except (subprocess.CalledProcessError, ValueError):
        costs.append(("GKE Autopilot (estimated)", 150.0))

    # Cloud SQL
    try:
        tier = run(
            f"gcloud sql instances describe health-api-db "
            f"--project={GCP_PROJECT} --format='value(settings.tier)'"
        )
        sql_cost = 7.67 if "micro" in tier else 25.0
        costs.append((f"Cloud SQL ({tier})", sql_cost))
    except subprocess.CalledProcessError:
        costs.append(("Cloud SQL (estimated)", 10.0))

    # Load Balancers
    lb_count = 2  # staging + production
    lb_cost = lb_count * 18.26
    costs.append((f"Load Balancers (x{lb_count})", lb_cost))

    # Artifact Registry (storage)
    costs.append(("Artifact Registry (storage)", 2.0))

    # Networking
    costs.append(("VPC / Networking (estimated)", 5.0))

    total = sum(c[1] for c in costs)

    print(f"  {'RESOURCE':<45} {'MONTHLY':>10}")
    print(f"  {'─'*45} {'─'*10}")
    for name, cost in costs:
        print(f"  {name:<45} ${cost:>8.2f}")
    print(f"  {'─'*45} {'─'*10}")
    print(f"  {'TOTAL':<45} \033[1m${total:>8.2f}\033[0m")
    print()
    print_info("Estimates based on us-central1 pricing. Actual costs may vary.")
    print_info("Run 'gcloud billing projects describe' for real billing data.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        prog="ops.py",
        description="Operations CLI for Health API infrastructure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  ops.py status                          Show health across all environments
  ops.py runs list                       List all pipeline runs
  ops.py runs list --status queued       Filter runs by status
  ops.py runs create SAMPLE-001          Create a new pipeline run
  ops.py logs staging                    Tail staging logs
  ops.py logs production --tail 100      Tail last 100 lines from production
  ops.py rollback production             Rollback production to previous release
  ops.py costs                           Estimate monthly infrastructure costs
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # status
    subparsers.add_parser("status", help="Show health and resource status across all environments")

    # runs
    runs_parser = subparsers.add_parser("runs", help="Manage pipeline runs")
    runs_sub = runs_parser.add_subparsers(dest="runs_command")

    runs_list = runs_sub.add_parser("list", help="List pipeline runs")
    runs_list.add_argument("--status", help="Filter by status (queued, running, completed, failed)")
    runs_list.add_argument("--env", choices=ENVS.keys(), default="production", help="Environment (default: production)")

    runs_create = runs_sub.add_parser("create", help="Create a new pipeline run")
    runs_create.add_argument("sample_id", help="Sample ID for the run")
    runs_create.add_argument("--env", choices=ENVS.keys(), default="production", help="Environment (default: production)")

    # logs
    logs_parser = subparsers.add_parser("logs", help="Tail application logs")
    logs_parser.add_argument("env", choices=ENVS.keys(), help="Environment to tail")
    logs_parser.add_argument("--tail", type=int, default=50, help="Number of lines (default: 50)")

    # rollback
    rollback_parser = subparsers.add_parser("rollback", help="Rollback to previous Helm release")
    rollback_parser.add_argument("env", choices=ENVS.keys(), help="Environment to rollback")
    rollback_parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")

    # costs
    subparsers.add_parser("costs", help="Estimate monthly GCP infrastructure costs")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    if args.command == "status":
        cmd_status(args)
    elif args.command == "runs":
        if not args.runs_command:
            runs_parser.print_help()
        elif args.runs_command == "list":
            cmd_runs_list(args)
        elif args.runs_command == "create":
            cmd_runs_create(args)
    elif args.command == "logs":
        cmd_logs(args)
    elif args.command == "rollback":
        cmd_rollback(args)
    elif args.command == "costs":
        cmd_costs(args)


if __name__ == "__main__":
    main()
