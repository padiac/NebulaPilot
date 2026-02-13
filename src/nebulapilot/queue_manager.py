import json
from pathlib import Path

QUEUE_FILE = Path("integration_queue.json")

class QueueManager:
    def __init__(self):
        self.queue = self.load_queue()

    def load_queue(self):
        if not QUEUE_FILE.exists():
            return []
        try:
            with open(QUEUE_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def save_queue(self):
        with open(QUEUE_FILE, "w") as f:
            json.dump(self.queue, f, indent=4)

    def add_target(self, target_name):
        if target_name not in self.queue:
            self.queue.append(target_name)
            self.save_queue()
            return True
        return False

    def remove_target(self, target_name):
        if target_name in self.queue:
            self.queue.remove(target_name)
            self.save_queue()

    def get_queue(self):
        return self.queue

    def get_next_target(self):
        if self.queue:
            return self.queue[0]
        return None
    
    def move_to_end(self, target_name):
        if target_name in self.queue:
            self.queue.remove(target_name)
            self.queue.append(target_name)
            self.save_queue()

    def reorder(self, new_queue):
        """Update queue with a new list (e.g. from drag-drop reordering)"""
        self.queue = new_queue
        self.save_queue()
