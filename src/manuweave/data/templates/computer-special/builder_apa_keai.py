"""Generate journal-specific formatting facts; research originals stay in TEMP.

No publisher template is needed to regenerate profiles from the checked facts.
The authoring branches and source exceptions are deliberately explicit.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def profiles():
    facts = json.loads((ROOT / 'apa-keai-source-facts.json').read_text(encoding='utf-8'))
    result = []
    for record in facts['verified_layouts']:
        extracted = record['extracted_format']
        requirements = []
        for target, values in [*record['rules'].items(), ('page', record['page'])]:
            group = extracted['page'] if target == 'page' else extracted['roles'][target]
            for prop, value in values.items():
                fact = group[prop]
                requirements.append({
                    'id': target + '-' + prop, 'category': 'layout',
                    'target': target, 'property': prop, 'expected': value,
                    'source': {k: fact['source'][k] for k in ['url', 'file', 'locator']},
                    'certainty': 'verified', 'checking': 'xml', 'applies_to': ['docx'],
                    'detail': fact.get('condition', record['source_version']),
                })
        result.append({
            'id': record['id'], 'name': record['journal'] + ' — ' + record['layout_name'],
            'version': '1.0.0', 'scope': record['scope'],
            'journal_title': record['journal'], 'catalog_journal_id': record['catalog_journal_id'],
            'manuscript_type': 'journal_article', 'stage': record['stage'],
            'aliases': [record['journal'] + ' source formatting'],
            'rules': record['rules'], 'page': record['page'], 'latex': {},
            'extracted_format': deepcopy(extracted), 'sources': record['sources'],
            'compliance': 'source_backed_template_partial_coverage',
            'checks': [{'requirement': r['id'], 'checking': 'xml'} for r in requirements],
            'template': {
                'family': 'computer-special', 'source_version': record['source_version'],
                'source_url': record['sources'][0]['url'],
                'license': 'formatting_facts_only_originals_not_redistributed',
                'assets': [], 'engine_support': {'docx': 'partial', 'latex': 'unsupported'},
                'requirements': requirements, 'coverage_notes': record['coverage_notes'],
            },
        })
    return result


if __name__ == '__main__':
    for profile in profiles():
        destination = ROOT / 'profiles' / (profile['id'] + '.json')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline="\n")
