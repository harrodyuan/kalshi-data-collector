import json
import os
import time
from datetime import datetime
from typing import Dict, List, Optional
from auth_manager import AuthManager
from market_data import MarketDataManager

class MarketCollector:
    def __init__(self, auth_manager: AuthManager):
        self.market_data = MarketDataManager(auth_manager)
        self.data_dir = "historical_data"
        self.date = datetime.now().strftime('%Y%m%d')
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

    def load_checkpoint(self) -> Dict:
        """Load checkpoint of previously processed events."""
        checkpoint_file = os.path.join(self.data_dir, "checkpoint_markets.json")
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, 'r') as f:
                return json.load(f)
        return {'processed_events': [], 'last_timestamp': None}

    def save_checkpoint(self, processed_events: List[str], timestamp: str):
        """Save checkpoint of processed events."""
        checkpoint_file = os.path.join(self.data_dir, "checkpoint_markets.json")
        with open(checkpoint_file, 'w') as f:
            json.dump({
                'processed_events': processed_events,
                'last_timestamp': timestamp,
                'total_processed': len(processed_events)
            }, f, indent=2)

    def collect_markets_by_event(self, event_ticker: str, retries: int = 3) -> Optional[List[Dict]]:
        """Collect all markets for a specific event with retries."""
        for attempt in range(retries):
            try:
                response = self.market_data.get_markets(event_ticker=event_ticker)
                markets = response.get('markets', [])
                if markets:
                    return markets
                time.sleep(1)  # Rate limiting protection
            except Exception as e:
                print(f"Attempt {attempt + 1}/{retries} failed for {event_ticker}: {e}")
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
        
        # Log failed event
        self.log_failure(event_ticker)
        return None

    def log_failure(self, event_ticker: str):
        """Log failed event collections."""
        failure_file = os.path.join(self.data_dir, "failures", f"failures_{datetime.now().strftime('%Y%m%d')}.txt")
        with open(failure_file, 'a') as f:
            f.write(f"{datetime.now().isoformat()}: Failed to collect markets for {event_ticker}\n")

    def get_event_ticker(self, event: Dict) -> Optional[str]:
        """Extract or construct event ticker from event data."""
        # First try to get direct event_ticker if exists
        ticker = event.get('event_ticker')
        if ticker:
            return ticker
            
        # If no direct ticker, try to construct from category and strike_date/period
        category = event.get('category', '').upper()
        if category:
            # Clean up category for ticker
            category = ''.join(c for c in category if c.isalnum())
            
            # Get date part
            if event.get('strike_date'):
                date_str = event['strike_date'][:10].replace('-', '')  # YYYYMMDD
                return f"KX{category}-{date_str}"
            elif event.get('strike_period'):
                # For periods, use current date as reference
                date_str = datetime.now().strftime('%Y%m%d')
                return f"KX{category}P-{date_str}"
                
        return None

    def collect_all_markets(self, events_file, max_events) -> str:
        """Collect markets from events file with limit."""
        # Load checkpoint
        checkpoint = self.load_checkpoint()
        processed_events = set(checkpoint['processed_events'])
        

        # Load events
        with open(events_file, 'r') as f:
            events_data = json.load(f)
            events = events_data.get('events', [])

        all_markets = []
        total_events = len(events)
        timestamp = datetime.now().isoformat()

        print(f"Processing up to {max_events} events from {events_file}")
        print(f"Already processed: {len(processed_events)} events")

        events_processed = 0

        try:
            # Collect markets for each event
            
            for i, event in enumerate(events, 1):
                if events_processed >= max_events:
                    print(f"\nReached maximum event limit of {max_events}")
                    break

                event_ticker = self.get_event_ticker(event)
                
                # Skip if no valid ticker or already processed
                if not event_ticker:
                    continue
                if event_ticker in processed_events:
                    print(f"[{i}/{total_events}] Skipping already processed event: {event_ticker}")
                    continue

                print(f"[{i}/{total_events}] Fetching markets for event: {event_ticker}")
                markets = self.collect_markets_by_event(event_ticker)
                
                if markets:
                    # Save individual event markets
                    event_file = os.path.join(
                        self.data_dir, 
                        "markets", 
                        f"markets_{event_ticker}_{datetime.now().strftime('%Y%m%d')}.json"
                    )
                    with open(event_file, 'w') as f:
                        json.dump({
                            'timestamp': timestamp,
                            'event_ticker': event_ticker,
                            'total_markets': len(markets),
                            'markets': markets
                        }, f, indent=2)
                    
                    all_markets.extend(markets)
                    processed_events.add(event_ticker)
                    events_processed += 1
                    
                    # Update checkpoint periodically
                    if i % 10 == 0:
                        self.save_checkpoint(list(processed_events), timestamp)
                        print(f"Checkpoint saved: {len(processed_events)} events processed")

                # Rate limiting
                
                time.sleep(0.5)

        except KeyboardInterrupt:
            print("\nCollection interrupted. Saving progress...")
        finally:
            # Save final results
            output_file = os.path.join(
                self.data_dir,
                "markets",
                f"all_markets_{datetime.now().strftime('%Y%m%d')}.json"
            )
            
            with open(output_file, 'w') as f:
                json.dump({
                    'timestamp': timestamp,
                    'total_markets': len(all_markets),
                    'markets': all_markets,
                    'events_processed': events_processed
                }, f, indent=2)

            # Save final checkpoint
            self.save_checkpoint(list(processed_events), timestamp)
            
            print(f"\nSaved {len(all_markets)} total markets to {output_file}")
            print(f"Processed {events_processed} events")
            return output_file

# if __name__ == "__main__":
#     auth = AuthManager(
#         key_id="YOUR_KALSHI_KEY_ID",
#         key_file_path="private_key.pem"
#     )
    
#     collector = MarketCollector(auth)
#     date_today = collector.date
#     markets_file = collector.collect_all_markets(events_file=f"historical_data/events/events_{date_today}.json", max_events=10)
#     print(f"Collection complete. Market data saved to: {markets_file}")
