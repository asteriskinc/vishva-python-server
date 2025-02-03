import asyncio
import json
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig
from typing import List, Dict
import argparse

class Crawl4AITester:
    def __init__(self):
        self.browser_config = BrowserConfig(
            # Configure browser settings
            headless=True,  # Run in headless mode
            viewport_width=1920,
            viewport_height=1080,
        )
        
        self.run_config = CrawlerRunConfig(
            # Configure crawl behavior
            excluded_tags=["nav", "footer"],
            exclude_external_links=True,
        )

    async def crawl_url(self, url: str) -> Dict:
        """Crawl a single URL and return results"""
        try:
            print(f"\nCrawling: {url}")
            start_time = datetime.now()
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    config=self.run_config
                )
                
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            # Extract key metrics and content
            crawl_results = {
                'url': url,
                'status': 'success',
                'duration_seconds': duration,
                'content_length': len(result.markdown),
                'links_found': len(result.links) if result.links else 0,
                'markdown_sample': result.markdown[:500] + '...' if result.markdown else None,
                'timestamp': end_time.isoformat()
            }
            
            print(f"✓ Successfully crawled {url} in {duration:.2f} seconds")
            return crawl_results
            
        except Exception as e:
            print(f"✗ Error crawling {url}: {str(e)}")
            return {
                'url': url,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def crawl_multiple_urls(self, urls: List[str]) -> List[Dict]:
        """Crawl multiple URLs concurrently"""
        tasks = [self.crawl_url(url) for url in urls]
        return await asyncio.gather(*tasks)

    def save_results(self, results: List[Dict], output_file: str):
        """Save crawl results to a JSON file"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {output_file}")

async def main():
    # Sample URLs to test
    test_urls = [
        "https://www.tesla.com/original-modely",
        "https://www.reddit.com/r/ChainsawMan/comments/1ifl261/is_yoru_actually_naive_or_an_evil_genius_i_find/",
        "https://www.opentable.com/s?dateTime=2025-02-02T19%3A00%3A00&covers=2&latitude=37.443552&longitude=-122.160244&metroId=&originalTerm=palo%20alto%2C%20ca&intentModifiedTerm=&areaId=geohash%3A9q9jh0ms&suggestedSearchName=Palo%20Alto%2C%20Ca&shouldUseLatLongSearch=true&originCorrelationId=6c76a056-135b-4213-b8dc-997c56962079"
        # Add more URLs to test
    ]
    
    # Initialize tester
    tester = Crawl4AITester()
    
    # Crawl URLs
    results = await tester.crawl_multiple_urls(test_urls)
    
    # Save results
    tester.save_results(results, 'crawl_results.json')
    
    # Print summary
    print("\nCrawl Summary:")
    print("-" * 50)
    for result in results:
        status = "✓" if result['status'] == 'success' else "✗"
        url = result['url']
        if result['status'] == 'success':
            print(f"{status} {url}: {result['content_length']} chars, {result['links_found']} links")
        else:
            print(f"{status} {url}: Failed - {result['error']}")

if __name__ == "__main__":
    asyncio.run(main())