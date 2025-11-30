#!/usr/bin/env python3
"""Direct test of portfolio service without Azure Functions"""

import asyncio
import os
import sys

# Add the parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Settings
from app.services.portfolio_service import PortfolioService

async def test_capabilities():
    """Test getting capabilities"""
    print("\n" + "="*80)
    print("Testing Capabilities")
    print("="*80)
    
    settings = Settings()
    service = PortfolioService(settings)
    
    capabilities = await service.get_capabilities()
    
    print(f"\nFound {len(capabilities)} capabilities:")
    for i, name in enumerate(capabilities.keys(), 1):
        print(f"  {i:2d}. {name}")
    
    return capabilities

async def test_generate_review():
    """Test generating a case review"""
    print("\n" + "="*80)
    print("Testing Generate Review")
    print("="*80)
    
    case_description = """I saw a 65-year-old man presenting with chest pain. He described the pain as crushing and radiating to his left arm. The pain started 30 minutes ago while he was gardening. 
    
On examination, he was sweaty and anxious. BP 150/95, HR 102, regular. Heart sounds normal, chest clear. I performed an ECG which showed ST elevation in leads II, III, aVF. 

I immediately gave him 300mg aspirin and GTN spray. Called 999 for blue light ambulance. Stayed with patient monitoring observations until paramedics arrived. Handed over to paramedics with ECG and clinical summary.

Patient taken to hospital. Later received discharge summary - he had successful PCI to RCA and is recovering well."""
    
    selected_capabilities = [
        "Clinical management",
        "Decision-making and diagnosis",
        "Communicating and consulting"
    ]
    
    print(f"\nCase description length: {len(case_description)} chars")
    print(f"Selected capabilities: {selected_capabilities}")
    print("\nGenerating review... (this may take 10-30 seconds)\n")
    
    settings = Settings()
    service = PortfolioService(settings)
    
    try:
        result = await service.generate_case_review(
            case_description=case_description,
            selected_capabilities=selected_capabilities
        )
        
        print("\n✅ SUCCESS!")
        print(f"\nCase Title: {result.case_title}")
        print("\n" + "="*80)
        print("Generated Review Content:")
        print("="*80)
        print(result.review_content)
        print("\n" + "="*80)
        
        return result
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

async def main():
    print("\n" + "="*80)
    print("🧪 CASEFORGE LOCAL DIRECT TEST")
    print("="*80)
    print("Testing updated generate review with new RCGP framework")
    print("="*80)
    
    # Test 1: Capabilities
    capabilities = await test_capabilities()
    
    # Test 2: Generate Review
    result = await test_generate_review()
    
    if result:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed")

if __name__ == "__main__":
    asyncio.run(main())

