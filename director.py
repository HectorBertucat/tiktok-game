import heapq
from dataclasses import dataclass, field
from typing import Any
from ruamel.yaml import YAML
from pathlib import Path

@dataclass(order=True)
class Event:
    t: float
    type: str = field(compare=False)
    payload: dict[str, Any] = field(compare=False, default_factory=dict)

class Director:
    def __init__(self, event_file_path: Path):
        self.events: list[Event] = []
        self._load_events(event_file_path)

    def _load_events(self, event_file_path: Path):
        yaml = YAML(typ="safe")
        data = yaml.load(event_file_path.read_text())
        if data and "events" in data:
            for event_data in data["events"]:
                event_t = float(event_data.pop("t"))
                event_type = str(event_data.pop("type"))
                # Remaining items in event_data are the payload
                payload = dict(event_data) 
                event = Event(t=event_t, type=event_type, payload=payload)
                heapq.heappush(self.events, event)

    def tick(self, now_sec: float, battle_instance: Any):
        """Pops and executes all events whose t <= now_sec."""
        while self.events and self.events[0].t <= now_sec:
            event = heapq.heappop(self.events)
            self._execute_event(event, battle_instance)

    def _execute_event(self, event: Event, battle_instance: Any):
        # Add event's own time to the payload for handlers that need it
        event.payload["event_time"] = event.t
        if event.type == "spawn_pickup":
            # This will be handled by the battle_instance
            battle_instance.handle_spawn_pickup_event(event.payload)
        elif event.type == "slowmo":
            # This will be handled by the battle_instance
            battle_instance.handle_slowmo_event(event.payload)
        elif event.type == "text_overlay":
            # This will be handled by the battle_instance
            battle_instance.handle_text_overlay_event(event.payload)
        else:
            raise ValueError(f"Unknown event type: {event.type}")

# Example usage (optional, for testing purposes)
if __name__ == '__main__':
    # Create a dummy events.yml for testing
    dummy_events_content = """
events:
  - {t: 1, type: spawn_pickup, payload: {kind: "heart", x: 100, y: 100}}
  - {t: 2, type: slowmo, payload: {factor: 0.5, duration: 5}}
  - {t: 3, type: text_overlay, payload: {text: "Hello World!", duration: 3}}
  - {t: 0.5, type: spawn_pickup, payload: {kind: "saw", x: 200, y: 200}}
"""
    dummy_event_file = Path("dummy_events.yml")
    dummy_event_file.write_text(dummy_events_content)

    class MockBattle:
        def handle_spawn_pickup_event(self, payload):
            print(f"EVENT: Spawning pickup: {payload}")
        def handle_slowmo_event(self, payload):
            print(f"EVENT: Activating slowmo: {payload}")
        def handle_text_overlay_event(self, payload):
            print(f"EVENT: Displaying text: {payload}")

    director = Director(dummy_event_file)
    mock_battle = MockBattle()

    print("--- Simulating game ticks ---")
    for t_current in [0, 0.6, 1.1, 1.5, 2.1, 3.5]:
        print(f"\nTime: {t_current}")
        director.tick(t_current, mock_battle)
    
    # Test unknown event type
    try:
        malformed_events_content = """
events:
  - {t: 1, type: unknown_event_type, payload: {}}
"""
        malformed_event_file = Path("malformed_events.yml")
        malformed_event_file.write_text(malformed_events_content)
        director_malformed = Director(malformed_event_file)
        director_malformed.tick(1.5, mock_battle)
    except ValueError as e:
        print(f"\nSuccessfully caught error: {e}")

    # Clean up dummy files
    dummy_event_file.unlink()
    malformed_event_file.unlink() 