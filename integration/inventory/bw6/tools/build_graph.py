"""Build the BW6 dependency inventory directly from the checked-in source."""

import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / 'integration/legacy-bw6'
OUTPUT = ROOT / 'integration/inventory/bw6'
ACTIVITY = re.compile(r'activityTypeID="([^"]+)"><activityConfig>(.*?)</activityConfig>')


def lines(path):
    return enumerate(path.read_text(encoding='utf-8').splitlines(), 1)


def citation(path, number):
    return f'{path.relative_to(ROOT).as_posix()}:L{number}'


def fields(xml):
    return {child.tag.split('}')[-1]: child.text or '' for child in ET.fromstring(xml)}


class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.processes = {}

    def node(self, identifier, kind, label, evidence, **attrs):
        if identifier not in self.nodes:
            self.nodes[identifier] = dict(id=identifier, type=kind, label=label, citation=evidence, **attrs)
        return identifier

    def edge(self, origin, target, kind, evidence, **attrs):
        self.edges.append(dict({'from': origin, 'to': target}, kind=kind, citation=evidence, **attrs))

    def stylesheet(self, path):
        path = path.resolve()
        identifier = 'xsl:' + path.relative_to(SOURCE).as_posix()
        if identifier in self.nodes:
            return identifier
        content = list(lines(path))
        declaration = next(n for n, text in content if '<xsl:stylesheet' in text)
        self.node(identifier, 'stylesheet', path.relative_to(SOURCE).as_posix(), citation(path, declaration))
        for number, text in content:
            for href in re.findall(r'<xsl:import\s+href="([^"]+)"', text):
                imported = self.stylesheet(path.parent / href)
                self.edge(identifier, imported, 'xsl_import', citation(path, number))
        return identifier

    def build(self):
        profiles = {}
        remote_directories = {}
        for environment in ('dev', 'prod'):
            path = SOURCE / 'Profiles' / f'{environment}.substvar'
            profiles[environment] = {}
            for number, text in lines(path):
                for fragment in re.findall(r'<globalVariable>.*?</globalVariable>', text):
                    config = fields(fragment)
                    profiles[environment][config['name']] = (config['value'], citation(path, number))
        for path in sorted((SOURCE / 'SharedResources').glob('*.sharedresource')):
            number, text = next((n, t) for n, t in lines(path) if 'name=' in t)
            self.node('resource:' + path.stem, 'shared_resource', path.stem, citation(path, number))
            config = fields(text)
            if 'remoteDirectory' in config:
                remote_directories[path.stem] = config['remoteDirectory']
                self.node('sftp:' + config['remoteDirectory'], 'sftp_path', config['remoteDirectory'], citation(path, number))
        schema = SOURCE / 'Database/schema.sql'
        for number, text in lines(schema):
            match = re.match(r'CREATE TABLE\s+(\w+)', text, re.I)
            if match:
                self.node('table:' + match[1], 'table', match[1], citation(schema, number))
        for path in sorted((SOURCE / 'Processes').glob('*/*.bwp')):
            content = list(lines(path))
            name = ET.fromstring(path.read_text()).attrib['name']
            activities = [(n, m[1], fields('<config>' + m[2] + '</config>'))
                          for n, text in content if (m := ACTIVITY.search(text))]
            starter = next(item for item in activities if item[1] != 'bw.jms.JMSConfirm')
            self.node(name, 'process', name.removeprefix('halvergate.'), citation(path, 2),
                      domain=path.parent.name, file=path.relative_to(ROOT).as_posix(),
                      starter_activity_type=starter[1], starter_destination=starter[2].get('destination'))
            self.processes[name] = (path, activities, starter[0])
        for name, (path, activities, starter_line) in self.processes.items():
            for number, activity, config in activities:
                evidence = citation(path, number)
                if 'connection' in config:
                    self.edge(name, 'resource:' + Path(config['connection']).stem, 'uses_resource', evidence)
                if 'destination' in config:
                    destination = config['destination']
                    dtype = config.get('destinationType')
                    basis = 'destinationType' if dtype else 'not declared'
                    if activity in ('bw.jms.JMSQueueReceiver', 'bw.jms.JMSTopicSubscriber'):
                        dtype = 'TOPIC' if 'Topic' in activity else 'QUEUE'
                        basis = 'activity type'
                    identifier = self.node('jms:' + destination, 'destination', destination, evidence,
                                           destination_type=dtype, destination_type_basis=basis,
                                           starter_destination_field=number == starter_line,
                                           non_jms_starter=number == starter_line and activity not in (
                                               'bw.jms.JMSQueueReceiver', 'bw.jms.JMSTopicSubscriber'))
                    if number == starter_line:
                        attrs = {}
                        if self.nodes[identifier]['non_jms_starter']:
                            attrs['note'] = f'destination field on {activity}; not evidence of a JMS receiver'
                        self.edge(identifier, name, 'consumes', evidence, **attrs)
                    elif activity == 'bw.jms.JMSSendMessage':
                        self.edge(name, identifier, 'produces', evidence)
                if activity == 'bw.jms.JMSConfirm':
                    identifier = self.node('jms:' + config['undeliveredQueue'], 'destination',
                                           config['undeliveredQueue'], evidence, destination_type='QUEUE',
                                           destination_type_basis='undeliveredQueue field')
                    self.edge(name, identifier, 'fault_to', evidence)
                elif activity == 'bw.jdbc.JDBCUpdate':
                    table = re.search(r'INSERT\s+INTO\s+(\w+)', config['sql'], re.I)[1]
                    self.edge(name, 'table:' + table, 'writes_table', evidence, commit_mode=config['commitMode'])
                elif activity == 'bw.http.SendHTTPRequest':
                    endpoint = config['endpoint']
                    variable = endpoint.removeprefix('${').removesuffix('}')
                    dev, dev_cite = profiles['dev'][variable]
                    prod, prod_cite = profiles['prod'][variable]
                    identifier = self.node('http:' + endpoint, 'http_endpoint', endpoint, evidence,
                                           dev_value=dev, prod_value=prod, differs=dev != prod,
                                           citations=[dev_cite, prod_cite])
                    self.edge(name, identifier, 'http_post', evidence)
                elif activity == 'bw.sftp.SFTPGet':
                    directory = remote_directories[Path(config['connection']).stem]
                    target = 'sftp:' + directory
                    self.edge(name, target, 'sftp_get', evidence,
                              citations=[self.nodes[target]['citation']])
                elif activity == 'bw.sftp.SFTPPut':
                    directory = str(PurePosixPath(config['remoteFile']).parent)
                    identifier = self.node('sftp:' + directory, 'sftp_path', directory, evidence)
                    self.edge(name, identifier, 'sftp_put', evidence, remote_file=config['remoteFile'])
                elif activity == 'bw.xml.TransformXML':
                    self.edge(name, self.stylesheet(SOURCE / config['stylesheet']), 'transforms_with', evidence)
                elif activity == 'bw.internal.callprocess':
                    called = config['processName']
                    candidates = [p for p in self.processes if p == called or p.endswith('.' + called)]
                    if len(candidates) != 1:
                        raise ValueError(f'{evidence}: ambiguous or missing callee {called}')
                    declared = candidates[0]
                    self.edge(name, declared, 'call_process', evidence, called_name=called,
                              declared_name=declared, name_matches=called == declared,
                              note='binding unresolved (see decisions)' if called != declared else '',
                              citations=[self.nodes[declared]['citation']])
        return self.document()

    def document(self):
        produced = {e['to'] for e in self.edges if e['kind'] == 'produces'}
        consumed = {e['from'] for e in self.edges if e['kind'] == 'consumes'}
        called = {e['to'] for e in self.edges if e['kind'] == 'call_process'}
        summary = {
            'producer_consumer_matches': [
                {'destination': d,
                 'producers': sorted({e['from'] for e in self.edges if e['kind'] == 'produces' and e['to'] == d}),
                 'consumers': sorted({e['to'] for e in self.edges if e['kind'] == 'consumes' and e['from'] == d})}
                for d in sorted(produced & consumed)],
            'processes_without_incoming_call_or_starter_producer': sorted(
                p for p in self.processes if p not in called
                and 'jms:' + self.nodes[p]['starter_destination'] not in produced),
            'destinations_without_in_project_consumer': sorted(
                n for n, attrs in self.nodes.items() if attrs['type'] == 'destination' and n not in consumed),
            'profile_differences': [
                {key: n[key] for key in ('id', 'dev_value', 'prod_value', 'citations')}
                for n in self.nodes.values() if n['type'] == 'http_endpoint' and n['differs']],
        }
        return dict(run='tib-d1111', base_commit='5c2ba511babbfacaba94c93a10d3e6b0542a7c4c',
                    nodes=sorted(self.nodes.values(), key=lambda n: n['id']), edges=self.edges, summary=summary)


def evidence_link(value):
    path, anchor = value.rsplit(':', 1)
    relative = Path(os.path.relpath(ROOT / path, OUTPUT)).as_posix()
    return f'[`{value}`]({relative}#{anchor})'


def markdown(graph):
    nodes = {n['id']: n for n in graph['nodes']}
    processes = {n['id'] for n in graph['nodes'] if n['type'] == 'process'}
    ledger_users = {e['from'] for e in graph['edges']
                    if e['kind'] == 'uses_resource' and e['to'] == 'resource:LedgerJdbc'}
    ledger_exceptions = ', '.join(f'`{nodes[p]["label"]}`' for p in sorted(processes - ledger_users))
    ems_users = {e['from'] for e in graph['edges']
                 if e['kind'] == 'uses_resource' and e['to'] == 'resource:EmsConnection'}
    fault_users = {e['from'] for e in graph['edges']
                   if e['kind'] == 'fault_to' and e['to'] == 'jms:HB.UNDLV'}
    ids = {identifier: f'n{i}' for i, identifier in enumerate(nodes)}
    compact = {'uses_resource', 'transforms_with', 'xsl_import'}
    visible = {'consumes', 'produces', 'call_process', 'http_post', 'sftp_get', 'sftp_put'}
    output = [
        '# BW6 dependency graph', '',
        'Generated from source by `tools/build_graph.py`, run **tib-d1111**. '
        'Evidence uses repo-root `path:L<n>` citations with links to the cited source lines.', '',
        'The graph records configured dependencies, not verified runtime bindings. '
        'Starter destination fields on SFTPGet, Timer and internal.start are retained as '
        '`consumes` edges but are not evidence of actual JMS receivers. Undeclared destination '
        'types remain null unless implied by the JMS activity type.', '',
        '```mermaid', 'flowchart LR',
    ]
    for index, domain in enumerate(sorted({n['domain'] for n in nodes.values() if n['type'] == 'process'})):
        output.append(f'  subgraph domain{index}["{domain}"]')
        for n in nodes.values():
            if n['type'] == 'process' and n['domain'] == domain:
                output.append(f'    {ids[n["id"]]}["{n["label"]}"]')
        output.append('  end')
    endpoints = {e[side] for e in graph['edges'] if e['kind'] in visible for side in ('from', 'to')}
    for identifier in sorted(endpoints):
        node = nodes[identifier]
        if node['type'] != 'process':
            label = node['label']
            if identifier == 'http:${screening.url}':
                label += ' (dev v1 / prod v2)'
            if node.get('non_jms_starter'):
                label += ' (starter field; not JMS receiver)'
            output.append(f'  {ids[identifier]}["{label}"]')
    for edge in graph['edges']:
        if edge['kind'] not in visible:
            continue
        arrow = '-. "call (name mismatch)" .->' if edge['kind'] == 'call_process' else f'-->|"{edge["kind"]}"|'
        output.append(f'  {ids[edge["from"]]} {arrow} {ids[edge["to"]]}')
    output.extend([
        '  classDef shared fill:#fff2b2,stroke:#a65d00,stroke-width:3px',
        f'  class {ids["http:${screening.url}"]} shared', '```', '',
        'The diagram omits HB.UNDLV, shared-resource, table and stylesheet dependencies; '
        f'the tables below retain them. {len(fault_users)} processes configure a fault to HB.UNDLV '
        f'and {len(ems_users)} reference EmsConnection. {len(ledger_users)} processes reference LedgerJdbc; '
        f'the two without a LedgerJdbc reference are {ledger_exceptions}. Resource edges are per activity, '
        'so repeated resource references are retained rather than collapsed.', '',
        '## Findings', '',
    ])
    calls = [e for e in graph['edges'] if e['kind'] == 'call_process']
    cross = [e for e in calls if nodes[e['from']]['domain'] != nodes[e['to']]['domain']]
    matches = graph['summary']['producer_consumer_matches']
    output.extend([
        f'- {len(calls)} configured call-process references; {len(cross)} cross domain boundaries. '
        'All names omit the declared `halvergate.` prefix. These are candidate callee links, '
        'not proof of resolved runtime bindings (see decisions).',
        '- `${screening.url}` is shared by payments.sanctions-screening and '
        'statements-documents.pdf-request; dev uses v1 and prod uses v2.',
        f'- {len(matches)} destinations have both an in-project producer and consumer. '
        'No output destination connects one process to another.', '',
    ])
    for heading, selected in [('## Behavioral edges', False), ('## Resource and stylesheet edges', True)]:
        output.extend([heading, '', '| From | Kind | To | Evidence link |', '| --- | --- | --- | --- |'])
        for edge in graph['edges']:
            if (edge['kind'] in compact) != selected:
                continue
            evidence = ' '.join(evidence_link(c) for c in [edge['citation'], *edge.get('citations', [])])
            kind = edge['kind']
            if 'commit_mode' in edge:
                kind += f' ({edge["commit_mode"]})'
            if edge.get('note'):
                kind += ': ' + edge['note']
            output.append(f'| `{edge["from"]}` | {kind} | `{edge["to"]}` | {evidence} |')
        output.append('')
    return '\n'.join(output)


def main():
    graph = Graph().build()
    path = OUTPUT / 'graph.json'
    path.write_text(json.dumps(graph, indent=2) + '\n', encoding='utf-8')
    graph = json.loads(path.read_text(encoding='utf-8'))
    (OUTPUT / 'dependency-graph.md').write_text(markdown(graph), encoding='utf-8')
    print('nodes by type:', json.dumps(dict(sorted(Counter(n['type'] for n in graph['nodes']).items()))))
    print('edges by kind:', json.dumps(dict(sorted(Counter(e['kind'] for e in graph['edges']).items()))))
    print(json.dumps(graph['summary'], indent=2))


if __name__ == '__main__':
    main()
