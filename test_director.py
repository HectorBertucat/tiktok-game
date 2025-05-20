import unittest
import heapq
from pathlib import Path
from director import Director, Event # Assuming director.py is in the same directory or accessible via PYTHONPATH
from ruamel.yaml import YAML

# A mock battle class to help test event execution
class MockBattle:
    def __init__(self):
        self.event_log = []

    def handle_spawn_pickup_event(self, payload):
        self.event_log.append(("spawn_pickup", payload))

    def handle_slowmo_event(self, payload):
        self.event_log.append(("slowmo", payload))

    def handle_text_overlay_event(self, payload):
        self.event_log.append(("text_overlay", payload))

class TestDirector(unittest.TestCase):
    def setUp(self):
        # Create a dummy YAML file for testing
        self.test_events_content = """
events:
  - {t: 5.0, type: text_overlay, payload: {text: "Event 3"}}
  - {t: 0.5, type: spawn_pickup, payload: {kind: "saw"}}
  - {t: 2.0, type: slowmo, payload: {factor: 0.5, duration: 2}}
"""
        self.test_event_file = Path("test_events.yml")
        self.test_event_file.write_text(self.test_events_content)
        self.mock_battle = MockBattle()

    def tearDown(self):
        # Clean up the dummy YAML file
        if self.test_event_file.exists():
            self.test_event_file.unlink()

    def test_event_loading_and_ordering(self):
        director = Director(self.test_event_file)
        self.assertEqual(len(director.events), 3)
        # Events should be in a min-heap, so the smallest t is at the front
        self.assertEqual(director.events[0].t, 0.5)
        self.assertEqual(director.events[0].type, "spawn_pickup")

        # Check full order by popping (simulates how Director.tick would do it)
        loaded_events_in_order = []
        temp_heap = list(director.events) # Copy to not modify the original during this check
        while temp_heap:
            loaded_events_in_order.append(heapq.heappop(temp_heap))
        
        self.assertEqual(loaded_events_in_order[0].t, 0.5)
        self.assertEqual(loaded_events_in_order[1].t, 2.0)
        self.assertEqual(loaded_events_in_order[2].t, 5.0)

    def test_tick_processes_events_in_order(self):
        director = Director(self.test_event_file)
        
        director.tick(0.0, self.mock_battle) # No events yet
        self.assertEqual(len(self.mock_battle.event_log), 0)

        director.tick(1.0, self.mock_battle) # Process event at t=0.5
        self.assertEqual(len(self.mock_battle.event_log), 1)
        self.assertEqual(self.mock_battle.event_log[0], ("spawn_pickup", {"kind": "saw"}))
        self.assertEqual(director.events[0].t, 2.0) # Next event

        director.tick(3.0, self.mock_battle) # Process event at t=2.0
        self.assertEqual(len(self.mock_battle.event_log), 2)
        self.assertEqual(self.mock_battle.event_log[1], ("slowmo", {"factor": 0.5, "duration": 2}))
        self.assertEqual(director.events[0].t, 5.0) # Next event
        
        director.tick(5.0, self.mock_battle) # Process event at t=5.0
        self.assertEqual(len(self.mock_battle.event_log), 3)
        self.assertEqual(self.mock_battle.event_log[2], ("text_overlay", {"text": "Event 3"}))
        self.assertEqual(len(director.events), 0) # All events processed

    def test_unknown_event_type_raises_error(self):
        malformed_content = """
events:
  - {t: 1.0, type: very_unknown_event, payload: {data: 123}}
"""
        malformed_file = Path("malformed_test_events.yml")
        malformed_file.write_text(malformed_content)
        
        director = Director(malformed_file)
        with self.assertRaisesRegex(ValueError, "Unknown event type: very_unknown_event"):
            director.tick(1.5, self.mock_battle)
        
        if malformed_file.exists():
            malformed_file.unlink()

    def test_event_payload_handling(self):
        # Test case where payload might be missing or explicitly null in YAML
        content_with_missing_payload = """
events:
  - {t: 1.0, type: spawn_pickup, kind: "heart"} # Payload implicitly {} 
  - {t: 2.0, type: text_overlay, payload: null, text: "Hello"} # Payload explicitly null
  - {t: 3.0, type: slowmo, payload: {factor: 0.1}} # Payload present
"""
        payload_test_file = Path("payload_test_events.yml")
        payload_test_file.write_text(content_with_missing_payload)
        director = Director(payload_test_file)

        director.tick(1.0, self.mock_battle)
        self.assertEqual(len(self.mock_battle.event_log), 1)
        # The Director should create an empty dict if payload is missing.
        # The event creation logic within _load_events itself has a 'kind' key at the same level as 't' and 'type'.
        # The current Event dataclass expects 'payload' to be a dict.
        # We need to ensure the YAML structure matches what _load_events expects or adjust _load_events.
        # Based on the YAML example: - { t: 4,  type: spawn_pickup, kind: "saw" }
        # The 'kind' is not nested under 'payload'. It's passed directly.
        # Let's adjust the test to reflect that 'kind' (and 'text' for text_overlay) are part of the top-level event_data.
        # The Director's _load_events puts all extra keys into the payload dict.
        self.assertEqual(self.mock_battle.event_log[0], ("spawn_pickup", {"kind": "heart"}))

        director.tick(2.0, self.mock_battle)
        self.assertEqual(len(self.mock_battle.event_log), 2)
        # If payload is null, it should become an empty dict. 'text' is also top-level here.
        self.assertEqual(self.mock_battle.event_log[1], ("text_overlay", {"text": "Hello"}))

        director.tick(3.0, self.mock_battle)
        self.assertEqual(len(self.mock_battle.event_log), 3)
        self.assertEqual(self.mock_battle.event_log[2], ("slowmo", {"factor": 0.1}))

        if payload_test_file.exists():
            payload_test_file.unlink()

if __name__ == '__main__':
    unittest.main() 