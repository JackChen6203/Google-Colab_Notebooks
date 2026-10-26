import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).with_name('monitor.py'))
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class MonitorTests(unittest.TestCase):
    def test_queue_transition_is_persisted_and_interrupt_exits(self):
        with tempfile.TemporaryDirectory() as directory:
            responses = [io.BytesIO(json.dumps(q).encode()) for q in (
                {'queue_running': [[1]], 'queue_pending': []},
                {'queue_running': [], 'queue_pending': []})]
            with patch.object(monitor.urllib.request, 'urlopen', side_effect=responses), \
                    patch.object(monitor.time, 'sleep', side_effect=[None, KeyboardInterrupt]):
                monitor.watch(directory)
            events = [json.loads(line) for line in (Path(directory) / 'logs/session-monitor.jsonl').read_text().splitlines()]
            self.assertEqual([event['running'] for event in events], [1, 0])

    def test_unavailable_server_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(monitor.urllib.request, 'urlopen', side_effect=OSError('connection refused')), \
                    patch.object(monitor.time, 'sleep', side_effect=KeyboardInterrupt):
                monitor.watch(directory)
            event = json.loads((Path(directory) / 'logs/session-monitor.jsonl').read_text())
            self.assertIn('connection refused', event['error'])


if __name__ == '__main__':
    unittest.main()
