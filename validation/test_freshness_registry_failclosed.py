#!/usr/bin/env python3
import copy
import json
from pathlib import Path
from check_freshness_registry import validate

BASE = Path('validation/FRESHNESS_REGISTRY_V1_2026-10-12.json')


def assert_fails(mutator, label):
    data = json.loads(BASE.read_text(encoding='utf-8'))
    mutator(data)
    errors = validate(data)
    if not errors:
        raise AssertionError(f'{label}: mutation unexpectedly passed')
    print(label, 'PASS_FAIL_CLOSED', errors[0])


def main():
    base = json.loads(BASE.read_text(encoding='utf-8'))
    errors = validate(base)
    if errors:
        raise AssertionError(f'positive registry failed: {errors}')
    print('POSITIVE_REGISTRY_PASS')

    assert_fails(lambda d: d['policy'].__setitem__('fail_closed', False), 'FAIL_CLOSED_POLICY')

    def green_stale_rate(d):
        r = next(x for x in d['records'] if x['layer']=='RATES' and x['key']=='USD')
        r['status'] = 'GREEN'
    assert_fails(green_stale_rate, 'STALE_RATE_CANNOT_BE_GREEN')

    def activate_withheld_cb(d):
        r = next(x for x in d['records'] if x['layer']=='CB_PRICING' and x['key']=='USD')
        r['status'] = 'GREEN'
        r['reason'] = 'forced active without source proof'
        r['provenance'] = None
    assert_fails(activate_withheld_cb, 'WITHHELD_CB_CANNOT_BE_FORCED_GREEN')

    def remove_event_reason(d):
        r = next(x for x in d['records'] if x['layer']=='EVENT_CALENDAR')
        r['reason'] = ''
    assert_fails(remove_event_reason, 'ERROR_REQUIRES_REASON')

    def drop_macro(d):
        d['records'] = [x for x in d['records'] if not (x['layer']=='MACRO' and x['key']=='JPY_LABOUR')]
    assert_fails(drop_macro, 'MACRO_16_CORE_REQUIRED')

    def duplicate_identity(d):
        d['records'].append(copy.deepcopy(d['records'][0]))
    assert_fails(duplicate_identity, 'DUPLICATE_IDENTITY_REJECTED')

    print('FRESHNESS_REGISTRY_FAIL_CLOSED_TESTS_PASS')


if __name__ == '__main__':
    main()
