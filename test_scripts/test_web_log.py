"""The command window: services/logbuf.py (the ring buffer and the stdout tee) and /api/log."""

import sys

from src.web.server import create_app
from src.web.services.logbuf import LogBuffer, capture
from registry_files import write_registry


def test_since_returns_only_the_newer_lines():
    log = LogBuffer()
    log.add('one')
    log.add('two')
    rows, nxt = log.since(0)
    assert [r['text'] for r in rows] == ['one', 'two']
    log.add('three')
    rows, nxt2 = log.since(nxt)
    assert [r['text'] for r in rows] == ['three'] and nxt2 > nxt
    assert log.since(nxt2) == ([], nxt2)


def test_the_buffer_keeps_only_the_newest_lines():
    log = LogBuffer(max_lines=3)
    for i in range(5):
        log.add(f'l{i}')
    assert [r['text'] for r in log.since(0)[0]] == ['l2', 'l3', 'l4']


def test_capture_tees_finished_lines_and_still_prints(capsys):
    log = LogBuffer()
    with capture(log):
        print('scanning 3 files')
        sys.stdout.write('half a line')
    assert [r['text'] for r in log.since(0)[0]] == ['scanning 3 files', 'half a line']
    assert 'scanning 3 files' in capsys.readouterr().out


def test_api_log_lists_lines_and_a_failed_request_is_in_it(tmp_path):
    write_registry(tmp_path, [])
    client = create_app(tmp_path).test_client()
    assert client.get('/api/cases/nonesuch/history?columns=a&rows=0').status_code == 404
    got = client.get('/api/log?since=0').get_json()
    assert any('nonesuch' in l['text'] and l['level'] == 'error' for l in got['lines'])
    again = client.get(f"/api/log?since={got['next']}").get_json()
    assert again['lines'] == [] and again['next'] == got['next']


def test_api_log_takes_no_input(tmp_path):
    write_registry(tmp_path, [])
    client = create_app(tmp_path).test_client()
    assert client.post('/api/log', json={'text': 'x'}).status_code == 405


def test_the_page_has_the_command_window_and_the_spinner(tmp_path):
    write_registry(tmp_path, [])
    page = create_app(tmp_path).test_client().get('/').get_data(as_text=True)
    assert 'id="command-window"' in page and 'id="busy"' in page and 'js/log.js' in page
