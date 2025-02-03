# test_web_tools.py
import asyncio
import json
from datetime import datetime
from typing import List, Dict
import os
from dotenv import load_dotenv
from orcs.tools.web_tools_v2 import enhanced_web_search

# Load environment variables (make sure you have BRAVE_SEARCH_API_KEY in your .env)
load_dotenv()

class WebToolTester:
    def __init__(self):
        self.test_queries = [
            {
                "query": "Tesla Model Y specifications",
                "num_results": 3,
                "fetch_content": True
            },
            {
                "query": "restaurants in Palo Alto open now",
                "num_results": 3,
                "fetch_content": True
            },
            {
                "query": "latest movie showtimes AMC",
                "num_results": 3,
                "fetch_content": True
            }
        ]
        
    async def run_test_query(self, query: str, num_results: int, fetch_content: bool) -> Dict:
        """Run a single test query and return results with timing"""
        try:
            print(f"\nTesting query: '{query}'")
            start_time = datetime.now()
            
            results = await enhanced_web_search(
                query=query,
                num_results=num_results,
                fetch_content=fetch_content
            )
            
            duration = (datetime.now() - start_time).total_seconds()
            
            # Process results for logging
            test_results = {
                'query': query,
                'duration_seconds': duration,
                'total_results_found': results.total_results,
                'results_fetched': len(results.results),
                'timestamp': datetime.now().isoformat(),
                'results': []
            }
            
            # Add details for each result
            for result in results.results:
                result_data = {
                    'url': result.url,
                    'title': result.title,
                    'source': result.source,
                    'summary_length': len(result.summary),
                    'content_length': len(result.content),
                    'relevance_score': result.relevance_score,
                    'error': result.error if result.error else None
                }
                test_results['results'].append(result_data)
                
            print(f"✓ Query completed in {duration:.2f} seconds")
            print(f"  Found {results.total_results} total results")
            print(f"  Fetched {len(results.results)} results with content")
            
            return test_results
            
        except Exception as e:
            error_msg = f"Error testing query '{query}': {str(e)}"
            print(f"✗ {error_msg}")
            return {
                'query': query,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }

    async def run_all_tests(self) -> List[Dict]:
        """Run all test queries and return results"""
        all_results = []
        
        for test_case in self.test_queries:
            result = await self.run_test_query(**test_case)
            all_results.append(result)
            
            # Add a small delay between tests
            await asyncio.sleep(2)
            
        return all_results

    def save_results(self, results: List[Dict], output_file: str):
        """Save test results to a JSON file"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")
        
    def print_summary(self, results: List[Dict]):
        """Print a summary of test results"""
        print("\nTest Summary:")
        print("-" * 50)
        
        total_duration = 0
        total_successful = 0
        
        for result in results:
            if 'error' in result:
                status = "✗"
                message = f"Failed - {result['error']}"
            else:
                status = "✓"
                total_duration += result['duration_seconds']
                total_successful += 1
                message = f"{result['results_fetched']} results in {result['duration_seconds']:.2f}s"
                
            print(f"{status} Query: '{result['query']}'")
            print(f"   {message}")
            
            if 'results' in result:
                print("   Content statistics:")
                for i, res in enumerate(result['results'], 1):
                    print(f"   [{i}] {res['source']}: {res['content_length']} chars")
                    if res['error']:
                        print(f"       Error: {res['error']}")
            print()
            
        if total_successful > 0:
            avg_duration = total_duration / total_successful
            print(f"Average successful query duration: {avg_duration:.2f} seconds")
        
        print(f"Success rate: {total_successful}/{len(results)}")

async def main():
    # Check for API key
    if not os.getenv('BRAVE_SEARCH_API_KEY'):
        print("Error: BRAVE_SEARCH_API_KEY not found in environment variables")
        return
        
    print("Starting Enhanced Web Tools Test")
    print("=" * 50)
    
    # Initialize and run tests
    tester = WebToolTester()
    results = await tester.run_all_tests()
    
    # Save and display results
    tester.save_results(results, 'web_tool_test_results.json')
    tester.print_summary(results)

if __name__ == "__main__":
    asyncio.run(main())