#!/usr/bin/env python3
"""Export namespace-scoped Prometheus evidence for a load-test time window."""

import argparse
import json
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prom-url', default='http://localhost:19090')
    parser.add_argument('--namespace', default='otterworks-loadtest')
    parser.add_argument('--start', type=float, required=True)
    parser.add_argument('--end', type=float, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.namespace.startswith('otterworks-') or not args.namespace.replace('-', '').isalnum():
        parser.error('Expected a tenant namespace')
    selector = f'namespace="{args.namespace}",container!="",container!="POD"'
    queries = {
        'cpu_cores': f'sum by (pod) (rate(container_cpu_usage_seconds_total{{{selector}}}[1m]))',
        'memory_bytes': f'sum by (pod) (container_memory_working_set_bytes{{{selector}}})',
        'throttled_fraction': f'sum by (pod) (rate(container_cpu_cfs_throttled_periods_total{{{selector}}}[1m])) / sum by (pod) (rate(container_cpu_cfs_periods_total{{{selector}}}[1m]))',
        'restarts': f'kube_pod_container_status_restarts_total{{namespace="{args.namespace}"}}',
        'gateway_requests': f'sum by (status) (rate(api_gateway_http_requests_total{{namespace="{args.namespace}"}}[1m]))',
    }
    results = {'namespace': args.namespace, 'start': args.start, 'end': args.end, 'queries': queries, 'data': {}}
    for name, query in queries.items():
        params = urllib.parse.urlencode({'query': query, 'start': args.start, 'end': args.end, 'step': 15})
        with urllib.request.urlopen(f'{args.prom_url.rstrip("/")}/api/v1/query_range?{params}', timeout=30) as response:
            payload = json.load(response)
        if payload.get('status') != 'success':
            raise RuntimeError(f'Prometheus query failed for {name}')
        results['data'][name] = payload['data']['result']
    args.output.write_text(json.dumps(results, indent=2) + '\n')
    print(f'Evidence saved: {args.output}')
    for name in ('cpu_cores', 'memory_bytes', 'throttled_fraction', 'restarts'):
        print(name)
        for series in results['data'][name]:
            values = [float(value) for _, value in series['values'] if value not in ('NaN', '+Inf', '-Inf')]
            if values:
                print(f'  {series["metric"].get("pod", "unknown")}: min={min(values):.4f} max={max(values):.4f}')


if __name__ == '__main__':
    main()
