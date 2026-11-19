import contextlib
import io
import json
import sys
import unittest
from unittest.mock import patch
import subprocess

import simulate


class PublishSecurityTest(unittest.TestCase):
    topic = 'arn:aws:sns:us-east-1:123456789012:demo-topic'

    def test_command_preserves_values(self):
        body = '{"owner":"literal; touch injected"}'
        command = simulate.publish_command(self.topic, 'us-east-1', body)
        self.assertEqual(command[:3], ['aws', 'sns', 'publish'])
        self.assertEqual(command[command.index('--topic-arn') + 1], self.topic)
        self.assertEqual(command[command.index('--message') + 1], body)

    def test_invalid_region_and_topic(self):
        for topic, region in [(self.topic, ''), (self.topic, 'us-east-1;touch injected'),
                              ('--endpoint-url=malicious', 'us-east-1'), ('', 'us-east-1')]:
            with self.subTest(topic=topic, region=region), self.assertRaises(ValueError):
                simulate.publish_command(topic, region, '{}')

    def test_publish_never_invokes_a_shell(self):
        owner = 'literal; touch injected'
        result = subprocess.CompletedProcess([], 0, 'message-id\n', '')
        with patch.object(sys, 'argv', ['simulate', '--topic-arn', self.topic, '--region', 'us-east-1',
                                       '--owner', owner]), patch.dict('os.environ', {'CW_DRY_RUN': '0'}), \
                patch.object(simulate.subprocess, 'run', return_value=result) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(simulate.main(), 0)
        kwargs = run.call_args.kwargs
        self.assertIs(kwargs['shell'], False)
        command = kwargs['args']
        self.assertEqual(json.loads(command[command.index('--message') + 1])['ownerId'], owner)


if __name__ == '__main__':
    unittest.main()
