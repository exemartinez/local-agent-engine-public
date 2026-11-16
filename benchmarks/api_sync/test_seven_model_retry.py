import copy
import seven_model_retry as retry


def test_prepare_only_one_preserves_prior():
    source = {'status': 'resource_guard', 'models': [
        {'model': 'A', 'quantization': 'Q3', 'status': 'resource_guard', 'benchmark': 'old'},
        {'model': 'B', 'quantization': 'Q4', 'status': 'pass', 'benchmark': 'keep'}]}
    original = copy.deepcopy(source)
    prepared = retry.prepare_single(source, ('A', 'Q3'))
    assert source == original
    assert prepared['models'][0]['status'] == 'pending'
    assert 'benchmark' not in prepared['models'][0]
    assert prepared['models'][1] == original['models'][1]


def test_report_shows_blocker_and_pending():
    state = {'status': 'blocked_disk', 'source_queue': 'original.json', 'reason': 'low disk',
             'models': [{'model': 'A', 'quantization': 'Q3', 'prior_status': 'resource_guard', 'status': 'pending'}]}
    report = retry.report_text(state)
    assert 'blocked_disk' in report and 'low disk' in report
    assert '| A | Q3 | resource_guard | pending |' in report


def test_guard_requires_three_ram_only_samples(tmp_path):
    import json
    sample = {'ram_available_bytes': 100, 'disk_free_bytes': 20 * retry.GIB, 'gpu_c': 50}
    path = tmp_path / 'samples.jsonl'
    path.write_text('\n'.join(json.dumps(sample) for _ in range(3)))
    assert retry.low_ram_guard_only(tmp_path)
    sample['gpu_c'] = 90
    path.write_text('\n'.join(json.dumps(sample) for _ in range(3)))
    assert not retry.low_ram_guard_only(tmp_path)
    path.write_text('{}')
    assert not retry.low_ram_guard_only(tmp_path)
