import json

import pytest
from cairn.dispatcher.config import WorkerConfig, DispatchConfig
from cairn.dispatcher.workers.adapters.opencode import OpenCodeDriver
from conftest import make_config


def test_opencode_cli_events_session_and_final_response():
    driver = OpenCodeDriver()
    stdout = '\n'.join(json.dumps(e) for e in [
        {'type': 'step_start', 'sessionID': 'ses_test'},
        {'type': 'tool_use', 'part': {'text': 'ignore tool output'}},
        {'type': 'text', 'part': {'text': '{"complete": true}'}},
    ])
    assert driver.extract_session(None, stdout, '') == 'ses_test'
    assert driver.extract_response_text(stdout, '') == '{"complete": true}'
    assert driver.extract_session('ses_existing', stdout, '') == 'ses_existing'
    with pytest.raises(RuntimeError, match='OpenCode worker failed'):
        driver.extract_response_text('{"type":"error","error":{"message":"rate limited"}}', '')


def test_opencode_resume_and_local_only():
    worker = WorkerConfig(name='oc', type='opencode', task_types=['bootstrap'], max_running=1, priority=0)
    argv = OpenCodeDriver().build_conclude(worker, 'a prompt; with $special chars', 'ses_test')
    assert argv[argv.index('--session') + 1] == 'ses_test'
    assert argv[-2:] == ['--', 'a prompt; with $special chars']
    payload = make_config().model_dump()
    payload['workers'] = [worker.model_dump()]
    with pytest.raises(ValueError, match='require runtime.execution: local'):
        DispatchConfig.model_validate(payload)
