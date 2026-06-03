import json
import os
from datetime import datetime
from typing import Dict, List
from auth_manager import AuthManager
from market_data import MarketDataManager

class EventsCollector:
    def __init__(self, auth_manager: AuthManager):
        self.market_data = MarketDataManager(auth_manager)
        self.data_dir = "historical_data"
        self.ensure_directories()

    def ensure_directories(self):
        """Create necessary directory structure."""
        dirs = [
            self.data_dir,
            os.path.join(self.data_dir, "events"),
            os.path.join(self.data_dir, "markets"),
            os.path.join(self.data_dir, "failures")
        ]
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

    def collect_events(self) -> str:
        """Collect all events and save to file. Returns filename."""
        all_events = []
        cursor = None
        page = 1
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')

        # check if the data is already collected
        checkpoint_file = os.path.join(self.data_dir, "checkpoint_events.json")
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r') as f:
                checkpoint = json.load(f)
                last_collection = datetime.fromisoformat(checkpoint['last_events_collection'])
                if last_collection.date() == timestamp.date():
                    print("Events already collected for today.")
                    return checkpoint['events_file']

        print("Collecting events...")
        while True:
            try:
                print(f"Fetching page {page}...")
                response = self.market_data.get_events(cursor=cursor)
                events = response.get('events', [])
                
                if not events:
                    break
                    
                all_events.extend(events)
                cursor = response.get('cursor')
                page += 1
                
                if not cursor:
                    break
                    
            except Exception as e:
                print(f"Error on page {page}: {e}")
                # Log failure
                failure_file = os.path.join(self.data_dir, "failures", f"events_failures_{date_str}.txt")
                with open(failure_file, 'a') as f:
                    f.write(f"{timestamp.isoformat()}: Failed to fetch page {page} - {str(e)}\n")
                break

        # Save events to file
        filename = os.path.join(self.data_dir, "events", f"events_{date_str}.json")
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': timestamp.isoformat(),
                'total_events': len(all_events),
                'events': all_events
            }, f, indent=2)
            
        print(f"\nCollected {len(all_events)} events")
        print(f"Saved to: {filename}")
        
        # Create checkpoint - fixed filename for events checkpoint
        checkpoint_file = os.path.join(self.data_dir, "checkpoint_events.json")
        with open(checkpoint_file, 'w') as f:
            json.dump({
                'last_events_collection': timestamp.isoformat(),
                'events_file': filename,
                'total_events': len(all_events)
            }, f, indent=2)
        
        return filename

# if __name__ == "__main__":
#     auth = AuthManager(
#         key_id="YOUR_KALSHI_KEY_ID",
#         key_file_path="private_key.pem"
#     )
    
#     collector = EventsCollector(auth)
#     events_file = collector.collect_events()
#     print(f"\nCollection complete. Data saved to: {events_file}")
