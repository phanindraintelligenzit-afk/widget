import os
import time
import logging

logging.basicConfig(level=logging.DEBUG)

import sys
class FakePkgResources:
    def get_distribution(self, name):
        class Dist:
            version = "1.0.1"
        return Dist()
sys.modules['pkg_resources'] = FakePkgResources()

from skywalking import agent, config
from skywalking.trace.context import get_context

config.init(
    agent_collector_backend_services='127.0.0.1:11800',
    agent_name='dpi-ls-test-agent',
    agent_logging_level='DEBUG'
)
agent.start()

context = get_context()
with context.new_local_span("TestSpan") as span:
    from skywalking.trace.tags import Tag
    class CustomTag(Tag):
        def __init__(self, key, val):
            self.key = key
            super().__init__(val)
    span.tag(CustomTag("hello", "world"))

print("Span created. Waiting for flush...")
time.sleep(5)
agent.stop()
print("Done.")
