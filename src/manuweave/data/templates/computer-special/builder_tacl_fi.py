"""Build detailed TACL/Fundamenta formatting profiles from retained JSON facts."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def profiles():
    records = json.loads((ROOT / 'tacl-fi-source-facts.json').read_text(encoding='utf-8'))['verified_layouts']
    result = []
    for record in records:
        profile = deepcopy(record)
        profile.pop('layout_name')
        requirements = []
        for target, values in [*profile['rules'].items(), ('page', profile['page'])]:
            detailed = profile['extracted_format']['page'] if target == 'page' else profile['extracted_format']['roles'][target]
            for prop, value in values.items():
                item = detailed[prop]
                requirements.append({
                    'id': target + '-' + prop, 'category': 'layout', 'target': target,
                    'property': prop, 'expected': value, 'unit': item['unit'],
                    'source': item['source'], 'certainty': 'verified', 'checking': 'xml',
                    'applies_to': ['docx', 'latex'],
                    'detail': item.get('condition', 'Source dimensions converted to physical bp; natural TeX baselines map to minimum line height.'),
                })
        profile['template']['requirements'] = requirements
        profile['checks'] = [{'requirement': r['id'], 'checking': 'xml'} for r in requirements]
        result.append(profile)
    return result


if __name__ == '__main__':
    for profile in profiles():
        destination = ROOT / 'profiles' / (profile['id'] + '.json')
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline="\n")
