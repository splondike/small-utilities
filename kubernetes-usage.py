"""
Emits some CSVs containing useful k8s metrics
"""


import argparse
import csv
import collections
import json
import subprocess
import sys


def exec_json(args):
    proc = subprocess.run(args, capture_output=True, check=True)
    return json.loads(proc.stdout)


def normalize_quantity(quantity_str):
    if quantity_str.endswith("m"):
        return float(quantity_str[:-1])
    elif quantity_str.endswith("Ki"):
        return float(quantity_str[:-2]) / 1024.0
    elif quantity_str.endswith("Mi"):
        return float(quantity_str[:-2])
    elif quantity_str.endswith("Gi"):
        return float(quantity_str[:-2]) * 1024
    else:
        raise RuntimeError(f"Unhandled quantity_str: {quantity_str}")

def namespace_stats(log_progress):
    quantity_fieldnames = ["cpu", "memory", "cpu_daemonset", "memory_daemonset", "pod_count"]
    ns_result = exec_json(["kubectl", "get", "ns", "-o", "json"])

    namespace_results = collections.defaultdict(lambda: {q: 0.0 for q in quantity_fieldnames})
    for ns in ns_result["items"]:
        namespace = ns["metadata"]["name"]
        pods = exec_json(["kubectl", "get", "pods", "-o", "json", "--namespace", namespace])
        # Ensure this exists
        namespace_results[namespace]

        if log_progress:
            sys.stderr.write(f"Fetching {namespace}\n")

        namespace_results[namespace]["pod_count"] = len(pods["items"])
        for pod in pods["items"]:
            is_daemonset = any(
                ref["kind"] == "DaemonSet"
                for ref in pod["metadata"].get("ownerReferences", [])
            )

            for container in pod["spec"]["containers"]:
                for resource_type in ("cpu", "memory"):
                    quantity_str = container.get("resources", {}).get("requests", {}).get(resource_type)
                    quantity = 0.0 if quantity_str is None else normalize_quantity(quantity_str)

                    if is_daemonset:
                        namespace_results[namespace][resource_type + "_daemonset"] += quantity
                    else:
                        namespace_results[namespace][resource_type] += quantity

    out = csv.DictWriter(sys.stdout, fieldnames=["namespace"] + quantity_fieldnames)
    out.writeheader()
    for namespace, quantities in namespace_results.items():
        out.writerow({
            "namespace": namespace,
            **{
                fieldname: quantities[fieldname]
                for fieldname in quantity_fieldnames
            }
        })


def node_capacity(log_progress):
    nodes_result = exec_json(["kubectl", "get", "nodes", "-o", "json"])
    quantity_fieldnames = ["cpu", "memory", "pods"]
    out = csv.DictWriter(sys.stdout, fieldnames=["node_name"] + quantity_fieldnames)
    out.writeheader()
    for node in nodes_result["items"]:
        # I think allocatable is the actual memory available to k8s nodes after subtracting the stuff needed by the base k8s sytem
        # see https://learnk8s.io/allocatable-resources
        out.writerow({
            "node_name": node["metadata"]["name"],
            "cpu": normalize_quantity(node["status"]["allocatable"]["cpu"]),
            "memory": normalize_quantity(node["status"]["allocatable"]["memory"]),
            "pods": int(node["status"]["allocatable"]["pods"])
        })


def main():
    parser = argparse.ArgumentParser(description="Emit some k8s stats to stdout")

    parser.add_argument('--action', help="One of namespace-stats (default), and node-capacity", default="namespace-stats")
    parser.add_argument('--log-progress', action="store_true", help="Should we log out some messages to stderr while you wait", default=False)

    args = parser.parse_args()

    if args.action == "namespace-stats":
        namespace_stats(args.log_progress)
    elif args.action == "node-capacity":
        node_capacity(args.log_progress)

if __name__ == "__main__":
    main()
