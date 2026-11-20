{% macro documents_spark_replace_partition() %}
{% if is_incremental() %}
delete from {{ this }} where RUN_DATE = '{{ documents_spark_run_date() }}'
{% else %}
select 1
{% endif %}
{% endmacro %}

{% macro documents_spark_run_date() %}
{% set value = var('documents_spark_run_date', none) %}
{% if execute and value is none %}
{{ exceptions.raise_compiler_error('documents_spark_run_date must be supplied for binary extraction') }}
{% endif %}
{{ return(value if value is not none else '') }}
{% endmacro %}

{% macro documents_spark_similarity() %}
{% set sql %}
CREATE OR REPLACE TEMPORARY FUNCTION DOCS_SIMILARITY(before VARCHAR, after VARCHAR)
RETURNS FLOAT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'similarity'
AS $$
{% raw %}
import difflib
def similarity(before, after):
    return difflib.SequenceMatcher(None, before or '', after or '').ratio()
{% endraw %}
$$;
{% endset %}
{{ return(sql) }}
{% endmacro %}

{% macro documents_spark_parse_action() %}
{% set sql %}
CREATE OR REPLACE TEMPORARY FUNCTION DOCS_PARSE_ACTION(line VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'parse_action'
AS $$
{% raw %}
import re
def parse_action(line):
    match = re.search('action=(\\w+)', line or '')
    return match.group(1) if match else None
{% endraw %}
$$;
{% endset %}
{{ return(sql) }}
{% endmacro %}

{% macro documents_spark_normalize() %}
{% set sql %}
CREATE OR REPLACE TEMPORARY FUNCTION DOCS_NORMALIZE(tag VARCHAR)
RETURNS VARCHAR
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'normalize'
AS $$
{% raw %}
import re
def normalize(tag):
    return re.sub('\\s+', '-', (tag or '').strip().lower())
{% endraw %}
$$;
{% endset %}
{{ return(sql) }}
{% endmacro %}

{% macro documents_spark_extract_document() %}
{% set sql %}
CREATE OR REPLACE TEMPORARY FUNCTION DOCS_EXTRACT_DOCUMENT(content BINARY)
RETURNS VARIANT
LANGUAGE PYTHON
RUNTIME_VERSION = '3.11'
HANDLER = 'extract_result'
AS $$
{% raw %}
import argparse
from dataclasses import dataclass
import os
from pathlib import Path
import re
import shlex
TOKEN_PATTERN = re.compile('sfx-?[a-z0-9]+(?:-[a-z0-9]+)*')

@dataclass(frozen=True)
class RunConfig:
    token: str = 'sfx1119'

    def __post_init__(self):
        if not TOKEN_PATTERN.fullmatch(self.token):
            raise ValueError('RUN_TOKEN must be a lowercase sfx-prefixed identifier')

    @classmethod
    def from_env(cls):
        if 'RUN_TOKEN' in os.environ:
            return cls(os.environ['RUN_TOKEN'])
        legacy = os.environ.get('SNOWFLAKE_RUN_TOKEN', '')
        return cls(legacy) if TOKEN_PATTERN.fullmatch(legacy) else cls()

    @property
    def suffix(self):
        return self.token[3:].lstrip('-')

    @property
    def database(self):
        return 'SFX_' + self.suffix.upper().replace('-', '_')

    @property
    def before_namespace(self):
        return 'sfx-' + self.suffix + '-before'

    @property
    def after_namespace(self):
        return 'sfx-' + self.suffix + '-after'

    def environment(self):
        return {'RUN_TOKEN': self.token, 'RUN_DATABASE': self.database, 'RUN_BEFORE_NAMESPACE': self.before_namespace, 'RUN_AFTER_NAMESPACE': self.after_namespace}

    def render(self, text):
        if not isinstance(text, str):
            return text
        values = {'__RUN_TOKEN__': self.token, '__RUN_DATABASE__': self.database, '__BEFORE_NAMESPACE__': self.before_namespace, '__AFTER_NAMESPACE__': self.after_namespace}

        def replacement(match):
            marker = match.group()
            if marker in values:
                return values[marker]
            if marker.startswith('SFX_D'):
                return self.database
            if marker.endswith('-before'):
                return self.before_namespace
            if marker.endswith('-after'):
                return self.after_namespace
            return self.token
        pattern = '|'.join([*values, 'sfx-d[0-9]+(?:-(?:before|after))?', 'SFX_D[0-9]+(?:_AFTER)?'])
        return re.sub(pattern, replacement, text)

def render(text):
    return RunConfig.from_env().render(text)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['env', 'render'])
    parser.add_argument('path', nargs='?', type=Path)
    args = parser.parse_args()
    config = RunConfig.from_env()
    if args.command == 'env':
        for key, value in config.environment().items():
            print(f'export {key}={shlex.quote(value)}')
    else:
        if args.path is None:
            parser.error('render requires an asset path')
        print(config.render(args.path.read_text()), end='')
_run_render = render
import hashlib
from io import BytesIO
import re
import pyexpat
from zipfile import BadZipFile, ZipFile

def document_text(content):
    parser = pyexpat.ParserCreate(namespace_separator='}')
    paragraphs = []
    depth = 0

    def start(name, attributes):
        nonlocal depth
        if depth:
            depth += 1
        elif name == 'http://schemas.openxmlformats.org/wordprocessingml/2006/main}t':
            depth = 1
            paragraphs.append([])

    def end(name):
        nonlocal depth
        if depth:
            depth -= 1

    def text(value):
        if depth:
            paragraphs[-1].append(value)

    def reject(*arguments):
        raise ValueError('Document type declarations and external entities are not supported')
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartDoctypeDeclHandler = reject
    parser.ExternalEntityRefHandler = reject
    parser.Parse(content, True)
    return '\n'.join((''.join(parts) for parts in paragraphs))

def extract_document(content):
    raw = bytes(content)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        if raw.startswith(b'%PDF-'):
            text = '\n'.join((part.decode('utf-8', 'replace') for part in re.findall(b'\\((.*?)\\) Tj', raw)))
            pages = len(re.findall(b'/Type /Page\\b', raw))
            if not pages:
                raise ValueError('PDF contains no page objects')
            return ('application/pdf', text[:4096], pages, digest, None)
        with ZipFile(BytesIO(raw)) as archive:
            if 'word/document.xml' in archive.namelist():
                text = document_text(_run_render(archive.read('word/document.xml')))
                return ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', text[:4096], max(1, (len(text) + 2999) // 3000), digest, None)
            text = '\n'.join((_run_render(archive.read(name)).decode('utf-8', 'replace') for name in archive.namelist() if name.endswith('.txt')))
            return ('application/zip', text[:4096], max(1, text.count('\x0c') + 1), digest, None)
    except (BadZipFile, pyexpat.ExpatError, ValueError, OSError) as error:
        return ('application/octet-stream', '', 0, digest, str(error)[:200])
def extract_result(content):
    return dict(zip(("MEDIA_TYPE","TEXT","PAGE_COUNT","SHA256","ERROR"),extract_document(content)))
{% endraw %}
$$;
{% endset %}
{{ return(sql) }}
{% endmacro %}
