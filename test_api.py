import requests
import json

BASE_URL = "https://caseforge2025a.azurewebsites.net/api"  # Azure Functions default port

def test_capabilities():
    response = requests.get(f"{BASE_URL}/capabilities")
    print("\n=== Testing Capabilities Endpoint ===")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_generate_review():
    payload = {
        "case_description": "A 45-year-old patient presented with chest pain and shortness of breath. Initial examination revealed elevated blood pressure and irregular heart rhythm. ECG showed ST elevation.",
        "selected_capabilities": ["Clinical Knowledge and Skills", "Communication Skills"]
    }
    
    response = requests.post(f"{BASE_URL}/generate-review", json=payload)
    print("\n=== Testing Generate Review Endpoint ===")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_improve_review():
    payload = {
        "original_case": """Brief Description: A 45-year-old patient presented with chest pain.
        
        Capability: Clinical Knowledge and Skills
        Demonstrated thorough assessment.
        
        Reflection: The case was handled well.
        
        Learning needs identified from this event: Need to review ECG interpretation.""",
        "improvement_prompt": "Add more details about the clinical examination",
        "selected_capabilities": ["Clinical Knowledge and Skills"]
    }
    
    response = requests.post(f"{BASE_URL}/improve-review", json=payload)
    print("\n=== Testing Improve Review Endpoint ===")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))

def test_improve_section():
    payload = {
        "section_type": "reflection",
        "section_content": "The case was handled well.",
        "improvement_prompt": "Add more details about the clinical examination",
        "capability_name": "Clinical Knowledge and Skills"
    }

    response = requests.post(f"{BASE_URL}/improve-section", json=payload)
    print("\n=== Testing Improve Section Endpoint ===")
    print(f"Status: {response.status_code}")
    print(json.dumps(response.json(), indent=2))


if __name__ == "__main__":
    # Uncomment the tests you want to run
    
    #test_capabilities()
    #test_generate_review()
    #test_improve_review() 
    test_improve_section()