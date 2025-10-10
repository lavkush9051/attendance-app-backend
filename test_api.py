#!/usr/bin/env python3
"""
Simple API testing script for the attendance management system
"""
import requests
import json
import sys

def test_api_endpoint(url, method="GET", data=None, headers=None):
    """Test an API endpoint and return the response"""
    try:
        if headers is None:
            headers = {"Content-Type": "application/json"}
        
        print(f"\n{'='*50}")
        print(f"Testing {method} {url}")
        print(f"{'='*50}")
        
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=data)
        elif method == "PUT":
            response = requests.put(url, headers=headers, json=data)
        else:
            print(f"Unsupported method: {method}")
            return None
            
        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        
        try:
            json_response = response.json()
            print(f"Response JSON: {json.dumps(json_response, indent=2)}")
        except:
            print(f"Response Text: {response.text}")
            
        return response
        
    except requests.exceptions.ConnectionError:
        print("❌ Connection Error: Server might not be running")
        return None
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    base_url = "http://127.0.0.1:8000"
    
    print("🚀 Starting API Tests...")
    
    # Test 1: Health check - try to access the root endpoint
    print("\n1. Testing server availability...")
    test_api_endpoint(f"{base_url}/")
    
    # Test 2: Login endpoint
    print("\n2. Testing login endpoint...")
    login_data = {
        "username": "10001",
        "password": "test@123"
    }
    response = test_api_endpoint(f"{base_url}/login", "POST", login_data)
    
    # Test 3: Try different credentials
    print("\n3. Testing login with different credentials...")
    login_data2 = {
        "username": "test",
        "password": "test"
    }
    test_api_endpoint(f"{base_url}/login", "POST", login_data2)
    
    # Test 4: Get employees without authentication
    print("\n4. Testing employees endpoint without auth...")
    test_api_endpoint(f"{base_url}/api/employees")
    
    print(f"\n{'='*50}")
    print("API Testing Complete!")
    print(f"{'='*50}")

if __name__ == "__main__":
    main()