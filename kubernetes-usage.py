"""
Emits some CSVs containing useful k8s metrics
"""


import argparse
import csv
import collections
import json
import re
import subprocess
import sys


def exec_json(args):
    proc = subprocess.run(args, capture_output=True, check=True)
    return json.loads(proc.stdout)


def normalize_quantity(quantity_str):
    if quantity_str.endswith("n"):
        # nanocores
        return float(quantity_str[:-1]) / (1000**3)
    elif quantity_str.endswith("m"):
        # millicores
        return float(quantity_str[:-1]) / (1000)
    elif quantity_str.endswith("Ki"):
        return float(quantity_str[:-2]) / 1024.0
    elif quantity_str.endswith("Mi"):
        return float(quantity_str[:-2])
    elif quantity_str.endswith("Gi"):
        return float(quantity_str[:-2]) * 1024
    else:
        # Just bytes
        return float(quantity_str)


def glob_to_re(glob):
    return re.compile(glob.replace(".", "\\.").replace("*", ".*").replace("?", "."))


def namespace_stats(namespace, pod_globs, node_globs, log_progress):
    quantity_fieldnames = [
        "cpu_used",
        "memory_used",
        "cpu_used_daemonset",
        "memory_used_daemonset",
        "cpu_request",
        "memory_request",
        "cpu_request_daemonset",
        "memory_request_daemonset",
        "pod_count"
    ]
    if namespace == "all":
        ns_result = exec_json(["kubectl", "get", "ns", "-o", "json"])
        namespaces = [
            ns["metadata"]["name"]
            for ns in ns_result["items"]
        ]
    else:
        namespaces = [namespace]

    pod_globs_ = pod_globs or []
    allowlist_pod_globs = [glob_to_re(g) for g in pod_globs_ if not g.startswith("!")]
    denylist_pod_globs = [glob_to_re(g[1:]) for g in pod_globs_ if g.startswith("!")]
    node_globs_ = node_globs or []
    allowlist_node_globs = [glob_to_re(g) for g in node_globs_]

    namespace_results = collections.defaultdict(lambda: {q: 0.0 for q in quantity_fieldnames})
    daemonset_pods = set()
    for namespace in namespaces:
        pods_data = exec_json(["kubectl", "get", "pods", "-o", "json", "--namespace", namespace])
        # Ensure this exists
        namespace_results[namespace]

        pods = []
        for pod in pods_data["items"]:
            name = pod["metadata"]["name"]
            # May not have a node allocated
            node_name = pod["spec"].get("nodeName", "")
            if len(allowlist_pod_globs) > 0:
                allowed = any(glob.match(name) for glob in allowlist_pod_globs)
            else:
                allowed = True

            if len(allowlist_node_globs) > 0:
                allowed = allowed and any(glob.match(node_name) for glob in allowlist_node_globs)

            allowed = allowed and not any(glob.match(name) for glob in denylist_pod_globs)

            if allowed:
                pods.append(pod)

        if log_progress:
            sys.stderr.write(f"Fetching {namespace}\n")

        namespace_results[namespace]["pod_count"] = len(pods)
        for pod in pods:
            is_daemonset = any(
                ref["kind"] == "DaemonSet"
                for ref in pod["metadata"].get("ownerReferences", [])
            )
            pod_name = pod["metadata"]["name"]
            if is_daemonset:
                daemonset_pods.add(f"{namespace}.{pod_name}")

            for container in pod["spec"]["containers"]:
                for resource_type in ("cpu", "memory"):
                    quantity_str = container.get("resources", {}).get("requests", {}).get(resource_type)
                    quantity = 0.0 if quantity_str is None else normalize_quantity(quantity_str)

                    label_base = resource_type + "_request"
                    if is_daemonset:
                        namespace_results[namespace][label_base + "_daemonset"] += quantity
                    else:
                        namespace_results[namespace][label_base] += quantity

    metrics_data = exec_json(
        ["kubectl", "get", "--raw", "/apis/metrics.k8s.io/v1beta1/pods"]
    )
    for namespace in namespaces:
        for pod in metrics_data["items"]:
            if pod["metadata"]["namespace"] != namespace:
                continue
            pod_name = pod["metadata"]["name"]

            is_daemonset = f"{namespace}.{pod_name}" in daemonset_pods

            for container in pod["containers"]:
                for metric in ("cpu", "memory"):
                    label = f"{metric}_used_daemonset" if is_daemonset else f"{metric}_used"
                    namespace_results[namespace][label] += normalize_quantity(
                        container["usage"][metric]
                    )

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
    parser.add_argument('--namespace', help="Just fetch this namespace", default="all")
    parser.add_argument('--node-name-glob', nargs="*", help="Just fetch pods for this node", default="all")
    parser.add_argument('--pod-name-glob', nargs="*", help="Just count pods matching this name. If prefixed with ! exclude those pods.")

    args = parser.parse_args()

    if args.action == "namespace-stats":
        namespace_stats(args.namespace, args.pod_name_glob, args.node_name_glob, args.log_progress)
    elif args.action == "node-capacity":
        node_capacity(args.log_progress)


if __name__ == "__main__":
    main()
