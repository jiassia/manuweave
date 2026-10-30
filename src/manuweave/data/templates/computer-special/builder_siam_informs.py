"""Build the current IJOC numeric review-layout JSON from official source facts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def profiles():
    facts = json.loads((ROOT / 'siam-informs-source-facts.json').read_text(encoding='utf-8'))
    output = []
    for item in facts['verified_layouts']:
        requirements = []
        extracted = item['extracted_format']
        for target, properties in [*item['rules'].items(), ('page', item['page'])]:
            cells = extracted['page'] if target == 'page' else extracted['roles'][target]
            for prop, value in properties.items():
                requirements.append({
                    'id': target + '-' + prop, 'category': 'layout', 'target': target,
                    'property': prop, 'expected': value, 'unit': cells[prop]['unit'],
                    'source': cells[prop]['source'], 'certainty': 'verified', 'checking': 'xml',
                    'applies_to': ['docx', 'latex'],
                    'detail': 'Current review-submission numerical layout. A point is represented as a physical Word/PDF point (1/72 inch); one-inch margins equal 25.4 mm. Abstract and reference text are explicitly included.',
                })
        output.append({
            'id': item['id'], 'name': item['journal'] + ' review-submission layout',
            'version': item['version'], 'scope': item['stage'] + '; ' + item['manuscript_type'],
            'journal_title': item['journal'], 'catalog_journal_id': item['catalog_journal_id'],
            'current_coverage': item['current_coverage'], 'manuscript_type': item['manuscript_type'],
            'stage': item['stage'], 'aliases': ['IJOC review-submission layout'],
            'rules': item['rules'], 'page': item['page'], 'latex': {},
            'sources': item['sources'], 'extracted_format': extracted,
            'compliance': 'source_backed_template_partial_coverage',
            'checks': [{'requirement': r['id'], 'checking': r['checking']} for r in requirements],
            'template': {
                'family': 'computer-special', 'source_version': item['source_version'],
                'source_url': item['sources'][0]['url'], 'license': 'rules_only_source_not_redistributed',
                'assets': [], 'engine_support': {'docx': 'partial', 'latex': 'partial'},
                'requirements': requirements, 'coverage_notes': item['coverage_notes'],
            },
        })
    return output


def build():
    destination = ROOT / 'profiles'
    destination.mkdir(exist_ok=True)
    for profile in profiles():
        (destination / (profile['id'] + '.json')).write_text(
            json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline="\n")


if __name__ == '__main__':
    build()
