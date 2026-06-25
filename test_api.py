import os
import json
import sys
import urllib.request
import urllib.error

# Parse the local .env file for API_URL
env_vars = {}
try:
    with open(".env", "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
except Exception as e:
    print(f"Error reading .env file: {e}")
    sys.exit(1)

api_url = env_vars.get("API_URL")
if not api_url:
    print("Error: API_URL not found in .env file.")
    sys.exit(1)

# Normalize API URL (remove trailing slash)
if api_url.endswith("/"):
    api_url = api_url[:-1]

print(f"Running Integration Tests against deployed API: {api_url}\n")

def make_request(url: str, method: str = "GET", headers: dict = None, body: dict = None):
    req_headers = {
        "Content-Type": "application/json"
    }
    if headers:
        req_headers.update(headers)
        
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8")
            return status_code, json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as e:
        response_body = e.read().decode("utf-8")
        try:
            err_data = json.loads(response_body)
        except:
            err_data = response_body
        return e.code, err_data
    except urllib.error.URLError as e:
        print(f"Connection Error: {e.reason}")
        return 0, {}

failed_tests = 0

def test_root():
    global failed_tests
    print("Test 1: GET / (Root Healthcheck)")
    code, data = make_request(f"{api_url}/")
    if code == 200 and data.get("status") in ("online", "running"):
        print("  ✅ PASS: Root status is online/running.")
    else:
        print(f"  ❌ FAIL: Expected 200/online/running, got Status={code}, Response={data}")
        failed_tests += 1

def test_quotes_crud():
    global failed_tests
    print("\nTest 2: POST /api/quotes (Create Quote)")
    headers = {"X-User-Email": "broker@dispatch.owera.ca"}
    quote_payload = {
        "customer_id": 1,
        "origin": "Chicago, IL",
        "destination": "Houston, TX",
        "weight_lbs": 42000.0,
        "pickup_date": "2026-07-01T08:00:00Z",
        "dimensions": "48x48x60",
        "freight_class": "92.5",
        "hazmat": False,
        "accessorials": "Liftgate Needed"
    }
    
    code, data = make_request(
        url=f"{api_url}/api/quotes",
        method="POST",
        headers=headers,
        body=quote_payload
    )
    
    if code != 200:
        print(f"  ❌ FAIL: Expected 200, got Status={code}, Response={data}")
        failed_tests += 1
        return None
        
    quote_id = data.get("id")
    if quote_id:
        print(f"  ✅ PASS: Created quote with ID: {quote_id}")
    else:
        print(f"  ❌ FAIL: Quote ID not found in response: {data}")
        failed_tests += 1
        return None

    # Test 3: GET /api/quotes/{id} (Retrieve Quote)
    print(f"\nTest 3: GET /api/quotes/{quote_id} (Retrieve Quote)")
    code, get_data = make_request(
        url=f"{api_url}/api/quotes/{quote_id}",
        method="GET",
        headers=headers
    )
    if code == 200 and get_data.get("id") == quote_id:
        print("  ✅ PASS: Successfully retrieved the correct quote.")
    else:
        print(f"  ❌ FAIL: Failed to retrieve quote, got Status={code}, Response={get_data}")
        failed_tests += 1

    # Test 4: GET /api/quotes (List Quotes)
    print("\nTest 4: GET /api/quotes (List All Quotes)")
    code, list_data = make_request(
        url=f"{api_url}/api/quotes",
        method="GET",
        headers=headers
    )
    if code == 200 and isinstance(list_data, list):
        found = any(q.get("id") == quote_id for q in list_data)
        if found:
            print(f"  ✅ PASS: Deployed list API successfully contains quote {quote_id}.")
        else:
            print(f"  ❌ FAIL: Created quote {quote_id} not found in listed quotes.")
            failed_tests += 1
    else:
        print(f"  ❌ FAIL: Failed to list quotes, got Status={code}, Response={list_data}")
        failed_tests += 1

    # Test 5: POST /api/quotes/{id}/upload-url (S3 Pre-signed URL)
    print(f"\nTest 5: POST /api/quotes/{quote_id}/upload-url (Generate S3 Presigned URL)")
    code, upload_data = make_request(
        url=f"{api_url}/api/quotes/{quote_id}/upload-url?filename=cargo_photo.jpg",
        method="POST",
        headers=headers
    )
    if code == 200 and "upload_url" in upload_data and "asset_url" in upload_data:
        print("  ✅ PASS: Successfully generated S3 pre-signed upload URL.")
        print(f"    Asset Destination URL: {upload_data.get('asset_url')}")
    else:
        print(f"  ❌ FAIL: Expected pre-signed URL response, got Status={code}, Response={upload_data}")
        failed_tests += 1

# Execute tests
test_root()
test_quotes_crud()

print("\n--- Test Run Summary ---")
if failed_tests == 0:
    print("🎉 ALL TESTS PASSED SUCCESSFULLY! The live API Gateway, Lambda, S3, and DynamoDB stack are fully functional.")
    sys.exit(0)
else:
    print(f"❌ {failed_tests} TESTS FAILED. Please check logs and stack configuration.")
    sys.exit(1)
