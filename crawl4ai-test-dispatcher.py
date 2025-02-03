import asyncio
import json
from datetime import datetime
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai import MemoryAdaptiveDispatcher, CrawlerMonitor, DisplayMode
from typing import List, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DispatcherTester:
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            verbose=True
        )
        
        self.run_config = CrawlerRunConfig(
            excluded_tags=["nav", "footer", "header", "aside"],
            exclude_external_links=True,
            cache_mode=CacheMode.BYPASS,
            stream=False
        )
        
        self.dispatcher = MemoryAdaptiveDispatcher(
            memory_threshold_percent=85.0,
            check_interval=2.0,
            max_session_permit=3,
            monitor=CrawlerMonitor(
                display_mode=DisplayMode.DETAILED
            )
        )

        self.test_urls = [
            "https://arcprize.org/guide",
            "https://www.tesla.com/modely",
            "https://wiki.python.org/moin/Generators",
            "https://www.reddit.com/r/reactjs/comments/1iebz9f/what_does_a_frontend_framework_like_react/",
            "https://github.com/apekshik/apekshik-personal-website-2",
            "https://www.opentable.com/r/indo-restaurant-and-lounge-palo-alto"
        ]

    def extract_title_from_metadata(self, result) -> str:
        """Extract title from metadata or other sources in the result"""
        if result.metadata and isinstance(result.metadata, dict):
            return result.metadata.get('title', '')
        return ''

    async def test_single_url(self, url: str) -> Dict:
        """Test crawling a single URL and return results"""
        try:
            logger.info(f"Crawling: {url}")
            start_time = datetime.now()
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    config=self.run_config
                )
                
            duration = (datetime.now() - start_time).total_seconds()
            
            if not result.success:
                raise Exception(result.error_message or "Unknown error occurred")

            # Extract available data from result
            crawl_results = {
                'url': result.url,
                'status': 'success',
                'duration_seconds': duration,
                'content_length': len(result.markdown) if result.markdown else 0,
                'metadata': result.metadata or {},
                'links_found': len(result.links.get('internal', [])) + len(result.links.get('external', [])) if result.links else 0,
                'has_content': bool(result.markdown),
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"✓ Successfully crawled {url} in {duration:.2f} seconds")
            return crawl_results
            
        except Exception as e:
            error_msg = f"Error crawling {url}: {str(e)}"
            logger.error(error_msg)
            return {
                'url': url,
                'status': 'error',
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }

    async def test_batch_crawl(self, urls: List[str]) -> List[Dict]:
        """Test crawling multiple URLs using the dispatcher"""
        try:
            logger.info(f"\nStarting batch crawl test with {len(urls)} URLs")
            start_time = datetime.now()
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                try:
                    results = await asyncio.wait_for(
                        crawler.arun_many(
                            urls=urls,
                            config=self.run_config,
                            dispatcher=self.dispatcher
                        ),
                        timeout=180
                    )
                except asyncio.TimeoutError:
                    raise Exception("Batch crawl timed out after 3 minutes")
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Batch crawl completed in {duration:.2f} seconds")
            
            # Process results
            processed_results = []
            for result in results:
                if result.success:
                    # Log the entire result structure for debugging
                    logger.debug(f"Raw result for {result.url}: {vars(result)}")
                    
                    processed_results.append({
                        'url': result.url,
                        'status': 'success',
                        'content_length': len(result.markdown) if result.markdown else 0,
                        'links_found': (
                            len(result.links.get('internal', [])) + 
                            len(result.links.get('external', []))
                        ) if result.links else 0,
                        'has_content': bool(result.markdown),
                        'metadata': result.metadata or {}
                    })
                else:
                    processed_results.append({
                        'url': result.url,
                        'status': 'error',
                        'error': result.error_message or "Unknown error"
                    })
            
            return processed_results
            
        except Exception as e:
            error_msg = f"Batch crawl failed: {str(e)}"
            logger.error(error_msg)
            return [{
                'url': url,
                'status': 'error',
                'error': error_msg
            } for url in urls]

    def save_results(self, results: List[Dict], output_file: str):
        """Save test results to a JSON file"""
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        logger.info(f"Results saved to: {output_file}")

    def print_summary(self, results: List[Dict]):
        """Print a summary of test results"""
        print("\nCrawl Summary:")
        print("-" * 60)
        
        successful = [r for r in results if r['status'] == 'success']
        failed = [r for r in results if r['status'] == 'error']
        
        print(f"Total URLs tested: {len(results)}")
        print(f"Successful crawls: {len(successful)}")
        print(f"Failed crawls: {len(failed)}")
        
        if successful:
            avg_content_length = sum(r['content_length'] for r in successful) / len(successful)
            avg_links = sum(r['links_found'] for r in successful) / len(successful)
            print(f"\nAverage content length: {avg_content_length:.0f} characters")
            print(f"Average links found: {avg_links:.1f}")
        
        print("\nDetailed Results:")
        print("-" * 60)
        for result in results:
            status = "✓" if result['status'] == 'success' else "✗"
            url = result['url']
            if result['status'] == 'success':
                print(f"{status} {url}")
                print(f"   Content: {result['content_length']} chars")
                print(f"   Links: {result['links_found']}")
                if result.get('metadata'):
                    print(f"   Metadata: {json.dumps(result['metadata'], indent=2)}")
            else:
                print(f"{status} {url}")
                print(f"   Error: {result['error']}")
            print()

async def main():
    # Initialize tester
    tester = DispatcherTester()
    logger.info("Starting Crawl4AI Dispatcher Test")
    
    # Test URLs in small batches
    batch_size = 2  # Reduced batch size
    all_results = []
    
    for i in range(0, len(tester.test_urls), batch_size):
        batch = tester.test_urls[i:i + batch_size]
        logger.info(f"\nTesting batch {i//batch_size + 1} ({len(batch)} URLs)")
        
        results = await tester.test_batch_crawl(batch)
        all_results.extend(results)
        
        # Delay between batches
        await asyncio.sleep(5)
    
    # Save and display results
    tester.save_results(all_results, 'dispatcher_test_results.json')
    tester.print_summary(all_results)

if __name__ == "__main__":
    asyncio.run(main())