# orcs/tools/enhanced_web_tools.py
from typing import List, Dict, Optional, Any
from pydantic import BaseModel
import aiohttp
import asyncio
import urllib.parse
import json
import os
import logging
from datetime import datetime
from ..tool_manager import tool_registry
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai import MemoryAdaptiveDispatcher, CrawlerMonitor, DisplayMode, CrawlResult

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Response Models
class WebContent(BaseModel):
    """Model for processed web content"""
    url: str
    title: str
    summary: str
    content: str
    source: str
    relevance_score: float = 1.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}

class EnhancedWebSearchResponse(BaseModel):
    """Model for enhanced web search results with content"""
    results: List[WebContent]
    query: str
    total_results: int


class ContentProcessor:
    """Process and extract content from crawl results"""
    
    @staticmethod
    def extract_main_content(result: CrawlResult) -> Dict[str, Any]:
        """Extract main content and metadata from crawl result"""
        processed = {
            'content': '',
            'title': '',
            'metadata': {},
            'links': {
                'internal': [],
                'external': []
            }
        }
        
        # First try to use markdown content if available
        if result.markdown:
            if isinstance(result.markdown, str):
                processed['content'] = result.markdown
            else:
                # Handle MarkdownGenerationResult type
                processed['content'] = result.markdown.markdown
        # Fallback to extracted_content if available
        elif result.extracted_content:
            processed['content'] = result.extracted_content
        # Last resort: cleaned_html if available
        elif result.cleaned_html:
            processed['content'] = result.cleaned_html
            
        # Process links - they're already categorized in the result
        if result.links:
            processed['links'] = result.links
            
        # Extract metadata
        processed['metadata'] = result.metadata if result.metadata else {}
        
        # Try to get title from metadata
        if result.metadata and 'title' in result.metadata:
            processed['title'] = result.metadata['title']
        # Fallback to trying to extract from HTML
        elif result.html:
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(result.html, 'html.parser')
                title_tag = soup.find('title')
                if title_tag:
                    processed['title'] = title_tag.text.strip()
            except Exception:
                pass
        
        # Add additional metadata from the result
        if result.status_code:
            processed['metadata']['status_code'] = result.status_code
        if result.redirected_url:
            processed['metadata']['redirected_url'] = result.redirected_url
                
        return processed

class WebCrawler:
    """Enhanced web crawler using Crawl4AI"""
    
    def __init__(self):
        self.browser_config = BrowserConfig(
            headless=True,
            viewport_width=1920,
            viewport_height=1080,
            verbose=False
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
        
        self.content_processor = ContentProcessor()

    async def crawl_url(self, url: str) -> Dict[str, Any]:
        """Crawl a single URL and return processed content"""
        try:
            logger.info(f"Crawling URL: {url}")
            start_time = datetime.now()
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                result = await crawler.arun(
                    url=url,
                    config=self.run_config
                )
                
            if not result.success:
                return {
                    'success': False,
                    'error': result.error_message or "Unknown error occurred",
                    'url': url
                }
                
            # Process the result
            processed_content = self.content_processor.extract_main_content(result)
            
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully crawled {url} in {duration:.2f} seconds")
            
            return {
                'success': True,
                'url': result.url,
                'content': processed_content['content'],
                'title': processed_content['title'],
                'links': processed_content['links'],
                'metadata': {
                    **processed_content['metadata'],
                    'duration': duration,
                    'content_length': len(processed_content['content'])
                }
            }
            
        except Exception as e:
            error_msg = f"Error crawling {url}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'url': url
            }

    async def crawl_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Crawl multiple URLs using the dispatcher"""
        try:
            logger.info(f"Starting batch crawl for {len(urls)} URLs")
            
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                try:
                    results = await asyncio.wait_for(
                        crawler.arun_many(
                            urls=urls,
                            config=self.run_config,
                            dispatcher=self.dispatcher
                        ),
                        timeout=180  # 3 minutes timeout per batch
                    )
                except asyncio.TimeoutError:
                    raise Exception("Batch crawl timed out after 3 minutes")
            
            processed_results = []
            for result in results:
                if result.success:
                    processed_content = self.content_processor.extract_main_content(result)
                    processed_results.append({
                        'success': True,
                        'url': result.url,
                        'content': processed_content['content'],
                        'title': processed_content['title'],
                        'links': processed_content['links'],
                        'metadata': processed_content['metadata']
                    })
                else:
                    processed_results.append({
                        'success': False,
                        'error': result.error_message,
                        'url': result.url
                    })
            
            return processed_results
            
        except Exception as e:
            error_msg = f"Batch crawl failed: {str(e)}"
            logger.error(error_msg)
            return [{
                'success': False,
                'error': error_msg,
                'url': url
            } for url in urls]

# Initialize global crawler instance
crawler = WebCrawler()

@tool_registry.register(description="Enhanced web search with content crawling")
async def enhanced_web_search(
    query: str,
    num_results: int = 5,
    fetch_content: bool = True
) -> EnhancedWebSearchResponse:
    """
    Perform a web search using Brave Search API and crawl the results for detailed content.
    
    Args:
        query: Search query string
        num_results: Number of results to return (max 10)
        fetch_content: Whether to fetch and crawl content from result URLs
    """
    try:
        logger.info(f"Performing enhanced web search: {query}")

        # Get search results from Brave
        brave_search_url = 'https://api.search.brave.com/res/v1/web/search'
        headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip',
            'X-Subscription-Token': os.getenv('BRAVE_SEARCH_API_KEY')
        }
        params = {
            'q': query,
            'count': min(num_results, 10),
            'search_lang': 'en',
            'safesearch': 'moderate',
            'extra_snippets': 'true',
            'format': 'json'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(brave_search_url, headers=headers, params=params) as response:
                if response.status != 200:
                    raise ValueError(f"Brave Search API returned status {response.status}")
                search_data = await response.json()

        if 'web' not in search_data or 'results' not in search_data['web']:
            raise ValueError("No search results found")

        # Extract URLs to crawl
        urls_to_crawl = [
            result['url'] for result in search_data['web']['results']
        ]

        # Crawl URLs if content fetching is enabled
        enhanced_results = []
        if fetch_content and urls_to_crawl:
            crawl_results = await crawler.crawl_batch(urls_to_crawl)
            
            # Match crawled content with search results
            for search_result, crawl_result in zip(search_data['web']['results'], crawl_results):
                if crawl_result['success']:
                    enhanced_results.append(WebContent(
                        url=crawl_result['url'],
                        title=crawl_result['title'] or search_result['title'],
                        summary=search_result.get('description', ''),
                        content=crawl_result['content'],
                        source=urllib.parse.urlparse(crawl_result['url']).netloc,
                        relevance_score=1.0,
                        metadata=crawl_result['metadata']
                    ))
                else:
                    # Fallback to search result if crawl failed
                    enhanced_results.append(WebContent(
                        url=search_result['url'],
                        title=search_result['title'],
                        summary=search_result.get('description', ''),
                        content="",
                        source=urllib.parse.urlparse(search_result['url']).netloc,
                        relevance_score=0.5,
                        error=crawl_result.get('error'),
                        metadata={}
                    ))
        else:
            # Just use search results if content fetching is disabled
            enhanced_results = [
                WebContent(
                    url=result['url'],
                    title=result['title'],
                    summary=result.get('description', ''),
                    content="",
                    source=urllib.parse.urlparse(result['url']).netloc,
                    relevance_score=1.0 - (i * 0.1),
                    metadata={}
                )
                for i, result in enumerate(search_data['web']['results'])
            ]

        return EnhancedWebSearchResponse(
            results=enhanced_results,
            query=query,
            total_results=search_data['web'].get('total_results', len(enhanced_results))
        )

    except Exception as e:
        logger.error(f"Enhanced web search failed: {str(e)}")
        raise ValueError(f"Enhanced web search failed: {str(e)}")