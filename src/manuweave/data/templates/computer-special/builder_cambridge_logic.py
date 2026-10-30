"""Build JSON-only Cambridge MSCS, TPLP and ASL JSL layout profiles from measured facts."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def profiles():
    facts = json.loads((ROOT / 'cambridge-logic-source-facts.json').read_text(encoding='utf-8'))
    result = []
    for item in facts['verified_layouts']:
        requirements = []
        extracted = item['extracted_format']
        for target, properties in [*item['rules'].items(), ('page', item['page'])]:
            cells = extracted['page'] if target == 'page' else extracted['roles'][target]
            for prop, value in properties.items():
                requirements.append({
                    'id': target + '-' + prop, 'category': 'layout', 'target': target,
                    'property': prop, 'expected': value, 'unit': cells[prop]['unit'],
                    'source': cells[prop]['source'], 'certainty': 'verified',
                    'checking': 'xml', 'applies_to': ['docx', 'latex'],
                    'detail': 'Physical layout extracted in the original template context. '
                    'Native TeX points and font identifiers remain in extracted_format. '
                    'Natural baseline becomes Word minimum line spacing.',
                })
        result.append({
            'id': item['id'], 'name': item['journal'] + ' detailed author-template layout',
            'version': item['version'], 'journal_title': item['journal'],
            'catalog_journal_id': item['catalog_journal_id'], 'stage': item['stage'],
            'scope': item['source_version'], 'rules': item['rules'], 'page': item['page'],
            'latex': {}, 'sources': item['sources'], 'extracted_format': extracted,
            'compliance': 'source_backed_template_partial_coverage',
            'checks': [{'requirement': r['id'], 'checking': r['checking']} for r in requirements],
            'template': {
                'family': 'computer-special', 'source_version': item['source_version'],
                'source_url': item['sources'][0]['url'],
                'license': 'rules_only_source_not_redistributed', 'assets': [],
                'engine_support': {'docx': 'partial', 'latex': 'partial'},
                'requirements': requirements, 'coverage_notes': item['coverage_notes'],
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
