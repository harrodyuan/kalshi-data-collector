import json
import os
import sys
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import requests
from auth_manager import AuthManager

class KalshiTerminal:
    """
    A terminal interface for interacting with Kalshi markets
    """
    
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
        self.api_base = "https://trading-api.kalshi.com/trade-api/v2"
        
    def _make_request(self, method: str, path: str, data: Dict = None) -> Dict:
        """Make an API request with proper authentication"""
        headers = self.auth_manager.generate_headers(method, path)
        url = f"{self.api_base}{path}"
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers)
            elif method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=headers)
            else:
                print(f"Unsupported method: {method}")
                return {}
                
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error {response.status_code}: {response.text}")
                return {}
        except Exception as e:
            print(f"Request error: {e}")
            return {}
    
    def get_event(self, event_ticker: str) -> Dict:
        """Get event details"""
        path = f"/events/{event_ticker}"
        return self._make_request("GET", path)
    
    def get_market(self, market_ticker: str) -> Dict:
        """Get market details"""
        path = f"/markets/{market_ticker}"
        return self._make_request("GET", path)
    
    def get_orderbook(self, market_ticker: str) -> Dict:
        """Get market orderbook"""
        path = f"/markets/{market_ticker}/orderbook"
        return self._make_request("GET", path)
        
    def get_positions(self) -> List[Dict]:
        """Get all positions"""
        path = "/portfolio/positions"
        response = self._make_request("GET", path)
        return response.get("positions", [])
        
    def get_market_position(self, market_ticker: str) -> int:
        """Get position for a specific market"""
        path = f"/portfolio/positions/{market_ticker}"
        response = self._make_request("GET", path)
        return response.get("position", 0)
        
    def get_orders(self, market_ticker: Optional[str] = None) -> List[Dict]:
        """Get orders, optionally filtered by market"""
        path = "/orders"
        if market_ticker:
            path += f"?market_id={market_ticker}"
        response = self._make_request("GET", path)
        return response.get("orders", [])
        
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an order"""
        path = f"/orders/{order_id}"
        response = self._make_request("DELETE", path)
        return "order_id" in response
        
    def place_order(self, market_id: str, side: str, price: int, count: int, yes_no: str = "yes") -> Dict:
        """Place an order"""
        path = "/orders"
        
        order_data = {
            "market_id": market_id,
            "client_order_id": f"term_{int(time.time())}",
            "side": side.lower(),
            "type": "limit",
            "count": int(count),
            "price": int(price),
            "yes_or_no": yes_no.lower()
        }
        
        return self._make_request("POST", path, order_data)
        
    def search_markets(self, query: str, limit: int = 10) -> List[Dict]:
        """Search for markets"""
        path = f"/markets?limit={limit}&q={query}"
        response = self._make_request("GET", path)
        return response.get("markets", [])
        
    def format_orderbook(self, orderbook: Dict) -> str:
        """Format orderbook for display"""
        output = []
        
        # Process asks (sell orders) - show highest first
        asks = orderbook.get("asks", {})
        sorted_ask_prices = sorted(map(int, asks.keys()), reverse=True)
        
        if sorted_ask_prices:
            output.append("\nASKS (sells):")
            for price in sorted_ask_prices[:5]:  # Show top 5
                volume = asks.get(str(price), 0)
                total = price * volume / 100
                output.append(f"  ${price/100:.2f}: {volume} contracts (${total:.2f} total)")
        
        # Process bids (buy orders) - show highest first
        bids = orderbook.get("bids", {})
        sorted_bid_prices = sorted(map(int, bids.keys()), reverse=True)
        
        if sorted_bid_prices:
            output.append("\nBIDS (buys):")
            for price in sorted_bid_prices[:5]:  # Show top 5
                volume = bids.get(str(price), 0)
                total = price * volume / 100
                output.append(f"  ${price/100:.2f}: {volume} contracts (${total:.2f} total)")
                
        return "\n".join(output)
    
    def get_market_details(self, market_ticker: str) -> None:
        """Show detailed market information"""
        # Get basic market information
        market = self.get_market(market_ticker)
        if not market:
            print(f"Market {market_ticker} not found")
            return
            
        # Get orderbook
        orderbook = self.get_orderbook(market_ticker)
        
        # Get user position
        position = self.get_market_position(market_ticker)
        
        # Get user orders
        orders = self.get_orders(market_ticker)
            
        # Format and display the information
        print("\n" + "="*50)
        print(f"MARKET: {market.get('title', market_ticker)}")
        print(f"Ticker: {market_ticker}")
        print(f"Status: {market.get('status', 'unknown')}")
        
        expiration = market.get('close_time')
        if expiration:
            expiration_dt = datetime.strptime(expiration, "%Y-%m-%dT%H:%M:%SZ")
            now = datetime.utcnow()
            time_left = expiration_dt - now
            print(f"Closes: {expiration} (in {time_left})")
            
        # Show yes contract price if available
        if "yes" in market.get("last_price", {}):
            yes_price = market["last_price"]["yes"]
            print(f"Last price: ${yes_price/100:.2f} ({yes_price}%)")
            
        # Show user position
        if position:
            print(f"\nYour position: {position}")
            
        # Show orderbook
        if orderbook:
            print(self.format_orderbook(orderbook))
            
        # Show user orders
        if orders:
            print("\nYOUR ACTIVE ORDERS:")
            for order in orders:
                side = order.get("side", "unknown")
                price = order.get("price", 0)
                count = order.get("count", 0)
                yes_no = order.get("yes_or_no", "unknown")
                order_id = order.get("order_id", "unknown")
                print(f"  {side.upper()} {count} {yes_no.upper()} @ ${price/100:.2f} (ID: {order_id})")
                
        print("="*50 + "\n")

    def run(self):
        """Run the interactive terminal"""
        print("Welcome to Kalshi Terminal!")
        print("Type 'help' for available commands")
        
        while True:
            command = input("\n> ").strip().lower()
            parts = command.split()
            
            if not parts:
                continue
                
            cmd = parts[0]
            
            if cmd in ["exit", "quit", "q"]:
                break
                
            elif cmd == "help":
                self.show_help()
                
            elif cmd == "market":
                if len(parts) < 2:
                    print("Usage: market <ticker>")
                else:
                    self.get_market_details(parts[1])
                    
            elif cmd == "search":
                if len(parts) < 2:
                    print("Usage: search <keyword>")
                else:
                    query = " ".join(parts[1:])
                    self.search_and_display(query)
                    
            elif cmd == "buy" or cmd == "sell":
                if len(parts) < 4:
                    print(f"Usage: {cmd} <market_ticker> <price_cents> <count> [yes/no]")
                else:
                    market = parts[1]
                    try:
                        price = int(parts[2])
                        count = int(parts[3])
                        yes_no = "yes" if len(parts) < 5 else parts[4].lower()
                        
                        if yes_no not in ["yes", "no"]:
                            print("Contract type must be 'yes' or 'no'")
                            continue
                            
                        self.place_and_confirm_order(market, cmd, price, count, yes_no)
                    except ValueError:
                        print("Price and count must be valid numbers")
                        
            elif cmd == "cancel":
                if len(parts) < 2:
                    print("Usage: cancel <order_id>")
                else:
                    order_id = parts[1]
                    success = self.cancel_order(order_id)
                    if success:
                        print(f"Order {order_id} canceled successfully")
                    else:
                        print(f"Failed to cancel order {order_id}")
                        
            elif cmd == "orders":
                market = None if len(parts) < 2 else parts[1]
                self.show_orders(market)
                
            elif cmd == "positions":
                self.show_positions()
                
            else:
                print(f"Unknown command: {cmd}")
                self.show_help()
    
    def show_help(self):
        """Display available commands"""
        print("\nAvailable commands:")
        print("  market <ticker>               - Show market details")
        print("  search <keyword>              - Search for markets")
        print("  buy <market> <price> <count>  - Place buy order")
        print("  sell <market> <price> <count> - Place sell order")
        print("  cancel <order_id>             - Cancel an order")
        print("  orders [market]               - Show your orders (optional: filter by market)")
        print("  positions                     - Show your positions")
        print("  help                          - Show this help")
        print("  exit                          - Exit the terminal")
        
    def search_and_display(self, query: str):
        """Search for markets and display results"""
        markets = self.search_markets(query)
        if not markets:
            print(f"No markets found matching '{query}'")
            return
            
        print(f"\nFound {len(markets)} markets matching '{query}':")
        for i, market in enumerate(markets):
            ticker = market.get("id")
            title = market.get("title")
            status = market.get("status")
            if "yes" in market.get("last_price", {}):
                price = market["last_price"]["yes"]
                price_str = f"${price/100:.2f}"
            else:
                price_str = "N/A"
                
            print(f"{i+1}. [{ticker}] {title} ({status}) - Last: {price_str}")
        
        # Allow selecting a market
        choice = input("\nEnter number to view market details (or press Enter to skip): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(markets):
            selected = markets[int(choice) - 1]
            self.get_market_details(selected.get("id"))
            
    def place_and_confirm_order(self, market_id: str, side: str, price: int, count: int, yes_no: str):
        """Place an order with confirmation"""
        # Show market details first
        self.get_market_details(market_id)
        
        # Confirm the order
        print(f"\nPlacing order: {side.upper()} {count} {yes_no.upper()} contracts at ${price/100:.2f}")
        confirm = input("Confirm? (y/n): ").strip().lower()
        
        if confirm == 'y':
            result = self.place_order(market_id, side, price, count, yes_no)
            if "order_id" in result:
                print(f"\nOrder placed successfully! Order ID: {result['order_id']}")
            else:
                print("\nFailed to place order.")
        else:
            print("Order canceled")
            
    def show_orders(self, market: Optional[str] = None):
        """Show active orders"""
        orders = self.get_orders(market)
        
        if not orders:
            print("No active orders" + (f" for {market}" if market else ""))
            return
            
        print("\nACTIVE ORDERS:")
        for order in orders:
            market_id = order.get("market_id", "unknown")
            side = order.get("side", "unknown")
            price = order.get("price", 0)
            count = order.get("count", 0)
            yes_no = order.get("yes_or_no", "unknown")
            order_id = order.get("order_id", "unknown")
            print(f"[{market_id}] {side.upper()} {count} {yes_no.upper()} @ ${price/100:.2f} (ID: {order_id})")
            
    def show_positions(self):
        """Show all positions"""
        positions = self.get_positions()
        
        if not positions:
            print("No active positions")
            return
            
        print("\nACTIVE POSITIONS:")
        for pos in positions:
            market_id = pos.get("market_id", "unknown")
            position = pos.get("position", 0)
            if position != 0:
                print(f"[{market_id}] {position}")


if __name__ == "__main__":
    # Initialize authentication
    auth = AuthManager(
        key_id="05b95ed4-a236-41a1-9e3b-81124f6871dd",
        key_file_path="private_key.pem"
    )
    
    # Create and run terminal
    terminal = KalshiTerminal(auth)
    
    # Check if a market is specified on command line
    if len(sys.argv) > 1:
        market_ticker = sys.argv[1]
        terminal.get_market_details(market_ticker)
    
    # Run interactive terminal
    try:
        terminal.run()
    except KeyboardInterrupt:
        print("\nExiting Kalshi Terminal...")