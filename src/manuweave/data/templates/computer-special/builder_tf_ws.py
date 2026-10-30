"""Build source-bound T&F authoring-layout profiles from extracted template facts."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def profiles():
    facts = json.loads((ROOT / 'tf-ws-source-facts.json').read_text(encoding='utf-8'))
    result = []
    for record in facts['verified_layouts']:
        requirements = []
        for item in record['requirements']:
            requirements.append({
                'id': item['target'] + '-' + item['property'], 'category': 'layout',
                'target': item['target'], 'property': item['property'], 'expected': item['expected'],
                'source': {'url': item['url'], 'file': item['file'], 'locator': item['locator']},
                'certainty': 'verified', 'checking': 'xml', 'applies_to': ['docx'],
                'detail': item['native_units'],
            })
        result.append({
            'id': record['id'], 'name': record['journal'] + ' — selected authoring layout (Word)',
            'version': '1.0.0', 'scope': record['stage'] + '; ' + record['manuscript_type'],
            'journal_title': record['journal'], 'catalog_journal_id': record['catalog_journal_id'],
            'manuscript_type': record['manuscript_type'], 'stage': record['stage'],
            'aliases': [record['journal'] + ' Word authoring layout'],
            'rules': record['rules'], 'page': record['page'], 'latex': {},
            'extracted_format': record['extracted_format'],
            'sources': [{**source, 'verified': True} for source in record['sources']],
            'compliance': 'source_backed_template_partial_coverage',
            'checks': [{'requirement': item['id'], 'checking': 'xml'} for item in requirements],
            'examples': [{'kind': 'docx', 'path': 'computer-special/examples/tf-ws-synthetic.docx', 'synthetic': True}],
            'template': {
                'family': 'computer-special', 'source_version': record['source_version'],
                'source_url': record['sources'][-1]['url'], 'license': 'rules_only_source_not_redistributed',
                'assets': [], 'engine_support': {'docx': 'partial', 'latex': 'unsupported'},
                'requirements': requirements, 'coverage_notes': record['coverage_notes'],
            },
        })
    return result


def build():
    destination = ROOT / 'profiles'
    destination.mkdir(exist_ok=True)
    for profile in profiles():
        (destination / (profile['id'] + '.json')).write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline="\n")


if __name__ == '__main__':
    build()
