"""
Simple test script to verify WebSocket consumer works
Run: python test_websocket.py

To get a Firebase token:
1. Open your React app in browser
2. Open DevTools Console
3. Run: firebase.auth().currentUser.getIdToken().then(token => console.log(token))
4. Copy the token and set it as FIREBASE_TOKEN below
"""
import asyncio
import websockets
import json
import sys
import os

# Get token from environment variable or set it here
FIREBASE_TOKEN = os.getenv('FIREBASE_TOKEN', "YOUR_FIREBASE_TOKEN_HERE")

# WebSocket URL - adjust for your environment
WS_URL = os.getenv('WS_URL', "ws://localhost:8000/ws/ai/course-generation/")


async def test_course_generation():
    """Test course generation via WebSocket"""
    print(f"Connecting to {WS_URL}...")
    
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✓ Connected")
            
            # Step 1: Authenticate
            print("\n1. Authenticating...")
            auth_message = {
                "type": "auth",
                "token": FIREBASE_TOKEN
            }
            await websocket.send(json.dumps(auth_message))
            
            # Wait for auth response
            response = await websocket.recv()
            auth_response = json.loads(response)
            print(f"   Response: {auth_response}")
            
            if auth_response.get('type') != 'auth_success':
                print(f"❌ Authentication failed: {auth_response}")
                return
            
            print("✓ Authentication successful")
            
            # Step 2: Send course generation request
            print("\n2. Requesting course generation...")
            course_request = {
                "type": "message",
                "content": "Create a course on Scratch programming for kids aged 8-12",
                "context": {
                    "age_range": "8-12",
                    "level": "beginner"
                }
            }
            await websocket.send(json.dumps(course_request))
            
            # Step 3: Receive streaming responses
            print("\n3. Receiving responses...")
            full_data = None
            
            while True:
                try:
                    response = await websocket.recv()
                    data = json.loads(response)
                    msg_type = data.get('type')
                    
                    if msg_type == 'processing':
                        print(f"   {data.get('message')}")
                    elif msg_type == 'streaming':
                        # Print streaming chunks (can be verbose)
                        print(".", end="", flush=True)
                    elif msg_type == 'complete':
                        print("\n✓ Complete response received!")
                        full_data = data.get('data')
                        print(f"\n   Conversation ID: {data.get('conversation_id')}")
                        print(f"\n   Generated Course Data:")
                        print(f"   - Title: {full_data.get('title')}")
                        print(f"   - Category: {full_data.get('category')}")
                        print(f"   - Short Description: {full_data.get('short_description')[:100]}...")
                        print(f"   - Detailed Description: {full_data.get('detailed_description')[:100]}...")
                        break
                    elif msg_type == 'error':
                        print(f"\n❌ Error: {data.get('message')}")
                        break
                    else:
                        print(f"\n   Unknown message type: {msg_type}")
                        print(f"   Data: {data}")
                        
                except websockets.exceptions.ConnectionClosed:
                    print("\n❌ Connection closed")
                    break
                except Exception as e:
                    print(f"\n❌ Error receiving message: {e}")
                    break
            
            if full_data:
                print("\n✓ Test completed successfully!")
                print("\nFull response:")
                print(json.dumps(full_data, indent=2))
            else:
                print("\n❌ Test failed - no complete response received")
                
    except Exception as e:
        print(f"❌ Connection error: {e}")
        print("\nMake sure:")
        print("1. Django server is running with Daphne: daphne -b 0.0.0.0 -p 8000 backend.asgi:application")
        print("2. Redis is running (or USE_INMEMORY_CHANNELS=true)")
        print("3. You have a valid Firebase token")


async def test_connection_only():
    """Test just the WebSocket connection (without auth)"""
    print(f"Testing connection to {WS_URL}...")
    try:
        async with websockets.connect(WS_URL) as websocket:
            print("✓ WebSocket connection successful!")
            print("   Connection is working. You can now test with authentication.")
            return True
    except Exception as e:
        print(f"❌ Connection failed: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Django is running with Daphne:")
        print("   poetry run daphne -b 0.0.0.0 -p 8000 backend.asgi:application")
        print("2. Check if Redis is running (or USE_INMEMORY_CHANNELS=true)")
        print("3. Verify the URL is correct")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Test WebSocket Course Generation')
    parser.add_argument('--connection-only', action='store_true', 
                       help='Test only WebSocket connection (no auth)')
    parser.add_argument('--token', type=str, 
                       help='Firebase token (or set FIREBASE_TOKEN env var)')
    parser.add_argument('--url', type=str,
                       help='WebSocket URL (or set WS_URL env var)')
    
    args = parser.parse_args()
    
    if args.token:
        FIREBASE_TOKEN = args.token
    if args.url:
        WS_URL = args.url
    
    if args.connection_only:
        print("Testing WebSocket Connection Only")
        print("=" * 50)
        try:
            asyncio.run(test_connection_only())
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")
    else:
        if FIREBASE_TOKEN == "YOUR_FIREBASE_TOKEN_HERE":
            print("❌ Firebase token required for full test")
            print("\nTo get your Firebase token:")
            print("1. Open your React app in browser")
            print("2. Open DevTools Console (F12)")
            print("3. Run this command:")
            print('   firebase.auth().currentUser.getIdToken().then(token => console.log(token))')
            print("4. Copy the token and run:")
            print("   FIREBASE_TOKEN='your-token' poetry run python test_websocket.py")
            print("\nOr test connection only first:")
            print("   poetry run python test_websocket.py --connection-only")
            sys.exit(1)
        
        print("Testing WebSocket Course Generation Consumer")
        print("=" * 50)
        
        try:
            asyncio.run(test_course_generation())
        except KeyboardInterrupt:
            print("\n\nTest interrupted by user")

