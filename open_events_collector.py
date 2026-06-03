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
        self.checkpoint_file = os.path.join(self.data_dir, "events_collection_history.json")

    def ensure_directories(self):
        """Create necessary directory structure."""
        dirs = [
            self.data_dir,
            os.path.join(self.data_dir, "open_events"),  # This is where we'll save open events
        ]
        for dir_path in dirs:
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)

    def load_checkpoint(self) -> Dict:
        """Load checkpoint history file"""
        try:
            if os.path.exists(self.checkpoint_file):
                if os.path.getsize(self.checkpoint_file) > 0:  # Check if file is not empty
                    with open(self.checkpoint_file, 'r') as f:
                        return json.load(f)
                else:
                    print("Checkpoint file exists but is empty, creating new checkpoint")
            else:
                print("No existing checkpoint file found, creating new one")
        except json.JSONDecodeError as e:
            print(f"Error reading checkpoint file: {e}")
            print("Creating new checkpoint file")
            # Optionally backup the corrupted file
            if os.path.exists(self.checkpoint_file):
                backup = f"{self.checkpoint_file}.bak"
                os.rename(self.checkpoint_file, backup)
                print(f"Backed up corrupted checkpoint to: {backup}")
        except Exception as e:
            print(f"Unexpected error with checkpoint file: {e}")
        
        return {'collections': []}

    def get_event_changes(self, current_events: List[Dict], previous_events: List[Dict]) -> Dict:
        """Compare current and previous events to identify specific changes."""
        current_event_dict = {e['event_ticker']: e for e in current_events}
        previous_event_dict = {e['event_ticker']: e for e in previous_events}
        
        added_tickers = set(current_event_dict.keys()) - set(previous_event_dict.keys())
        removed_tickers = set(previous_event_dict.keys()) - set(current_event_dict.keys())
        
        def extract_event_info(event: Dict) -> Dict:
            return {
                'event_ticker': event['event_ticker'],
                'title': event.get('title', 'N/A'),
                'category': event.get('category', 'N/A'),
                'strike_date': event.get('strike_date', 'N/A'),
                'series_ticker': event.get('series_ticker', 'N/A')
            }
        
        added_events = [extract_event_info(current_event_dict[ticker]) for ticker in added_tickers]
        removed_events = [extract_event_info(previous_event_dict[ticker]) for ticker in removed_tickers]
        
        return {
            'added': added_events,
            'removed': removed_events,
            'total_added': len(added_events),
            'total_removed': len(removed_events)
        }

    def get_previous_events(self, date_str: str) -> List[Dict]:
        """Get events from previous collection."""
        checkpoint_data = self.load_checkpoint()
        if not checkpoint_data['collections']:
            return []
            
        previous_collection = checkpoint_data['collections'][-1]
        try:
            with open(previous_collection['output_file'], 'r') as f:
                data = json.load(f)
                return data.get('events', [])
        except Exception as e:
            print(f"Warning: Could not load previous events: {e}")
            return []

    def update_checkpoint(self, date_str: str, total_events: int, filename: str, current_events: List[Dict]):
        """Update checkpoint with new collection information including specific changes."""
        checkpoint_data = self.load_checkpoint()
        current_time = datetime.now()
        
        # Get previous events and calculate changes
        previous_events = self.get_previous_events(date_str)
        event_changes = self.get_event_changes(current_events, previous_events)
        
        # Create collection info
        collection_info = {
            'date': date_str,
            'timestamp': current_time.isoformat(),
            'time': current_time.strftime('%H:%M:%S'),
            'total_events': total_events,
            'output_file': filename,
            'changes': event_changes
        }
        
        # Add previous counts and changes
        if checkpoint_data['collections']:
            previous_collection = checkpoint_data['collections'][-1]
            collection_info['previous_count'] = previous_collection['total_events']
            collection_info['total_change'] = total_events - previous_collection['total_events']
            
            same_day_collections = [c for c in checkpoint_data['collections'] if c['date'] == date_str]
            if same_day_collections:
                last_same_day = same_day_collections[-1]
                collection_info['previous_time'] = last_same_day['time']
                collection_info['intraday_change'] = total_events - last_same_day['total_events']
        
        checkpoint_data['collections'].append(collection_info)
        
        # Save updated checkpoint
        with open(self.checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2)
        
        # Print detailed change information
        print("\nChange Summary:")
        if event_changes['added']:
            print("\nNew Events Added:")
            for event in event_changes['added']:
                print(f"+ {event['event_ticker']}: {event['title']} ({event['category']}) - Strike: {event['strike_date']}")
        
        if event_changes['removed']:
            print("\nEvents Removed:")
            for event in event_changes['removed']:
                print(f"- {event['event_ticker']}: {event['title']} ({event['category']}) - Strike: {event['strike_date']}")
        
        if 'intraday_change' in collection_info:
            print(f"\nIntraday change since {collection_info['previous_time']}: {collection_info['intraday_change']:+d} events")
        print(f"Current total events: {total_events}")

    def collect_events(self) -> str:
        """Collect only open events and save to file. Returns filename."""
        all_events = []
        cursor = None
        page = 1
        timestamp = datetime.now()
        date_str = timestamp.strftime('%Y%m%d')

        print("Collecting open events...")
        while True:
            print(f"Fetching page {page}...")
            response = self.market_data.get_events(cursor=cursor, status="open")
            
            if not response or not isinstance(response, dict):
                print(f"Invalid response received: {response}")
                break
            
            events = response.get('events', [])
            if not events:
                print("No more events to fetch")
                break
            
            all_events.extend(events)
            print(f"Fetched {len(events)} events")
            
            # Check if we have a new cursor
            new_cursor = response.get('cursor')
            if not new_cursor or new_cursor == cursor:
                print("No more pages available")
                break
                
            cursor = new_cursor
            page += 1

        # Move this check before saving
        if not all_events:
            raise Exception("No events collected")

        filename = os.path.join(self.data_dir, "open_events", f"events_{date_str}.json")
        output_data = {
            'timestamp': timestamp.isoformat(),
            'total_open_events': len(all_events),
            'events': all_events
        }
        
        with open(filename,
                    'w') as f:
            json.dump(output_data, f, indent=2)
                        
        self.update_checkpoint(date_str, len(all_events), filename, all_events)  # Pass current events
        print(f"\nSuccessfully collected {len(all_events)} open events")
        print(f"Saved to: {filename}")
        return filename

if __name__ == "__main__":
    auth = AuthManager.from_env()
    
    collector = EventsCollector(auth)
    events_file = collector.collect_events()
