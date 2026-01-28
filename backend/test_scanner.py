"""
Test the accessibility scanner
"""

import asyncio
import json
from app.scanner import scan_url


async def test_scan():
    """Test scanning a real website"""
    
    # Test URLs
    test_urls = [
        "https://www.gov.il",  # Government site (should have accessibility)
        "https://example.com",  # Simple site
    ]
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Scanning: {url}")
        print(f"{'='*60}\n")
        
        try:
            results = await scan_url(url, standard="IL_5568", locale="he")
            
            # Print summary
            print(f"Scan ID: {results['scan_id']}")
            print(f"Score: {results['score']}/100")
            print(f"\nSummary:")
            print(f"  Total issues: {results['summary']['total_issues']}")
            print(f"  Critical: {results['summary']['critical']}")
            print(f"  Serious: {results['summary']['serious']}")
            print(f"  Moderate: {results['summary']['moderate']}")
            print(f"  Minor: {results['summary']['minor']}")
            
            print(f"\nLegal Risk:")
            print(f"  Level: {results['legal_risk']['level_he']}")
            print(f"  Estimated fine: {results['legal_risk']['estimated_fine']}")
            print(f"  Recommendation: {results['legal_risk']['recommendation_he']}")
            
            print(f"\nCoverage:")
            print(f"  Total automated: {results['coverage']['automated_total']}")
            
            # Save full results
            filename = f"test_results_{url.replace('https://', '').replace('/', '_')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"\nFull results saved to: {filename}")
            
        except Exception as e:
            print(f"ERROR: {str(e)}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("Starting accessibility scanner test...")
    asyncio.run(test_scan())
    print("\nTest complete!")
