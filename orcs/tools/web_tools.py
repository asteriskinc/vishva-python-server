# orcs/tools/web_tools.py
import os
from typing import Dict, List, Optional, Any, Tuple, Set
from pydantic import BaseModel
import aiohttp
import asyncio
import urllib.parse
from bs4 import BeautifulSoup
from ..tool_manager import tool_registry
import logging
import random
import time
from collections import defaultdict
import async_timeout
from aiohttp_retry import RetryClient, ExponentialRetry
from playwright.async_api import async_playwright, Browser, BrowserContext
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Playwright browser and context pool lazily
_browser: Optional[Browser] = None
_context_pool: List[BrowserContext] = []
_context_pool_lock = asyncio.Lock()
_max_contexts = 3  # Maximum number of browser contexts to keep in pool

# Track domain request times for adaptive throttling
_domain_request_times: Dict[str, List[float]] = defaultdict(list)
_domain_request_window = 60  # 1 minute window for rate tracking
_min_request_delay = 0.5  # Minimum delay between requests to same domain
_max_request_delay = 5.0  # Maximum delay between requests to same domain

# Enhanced circuit breaker tracking
class DomainHealth:
    def __init__(self):
        self.failures = 0
        self.timeout_until = 0
        self.error_types: Dict[str, int] = defaultdict(int)
        self.last_success = 0
        self.consecutive_failures = 0
        self.total_requests = 0
        self.success_rate = 1.0

_domain_health: Dict[str, DomainHealth] = defaultdict(DomainHealth)
_domain_failure_threshold = 3
_domain_failure_timeout = 300  # 5 minutes
_domain_success_reset_time = 3600  # 1 hour - time after which to reset failure counts on success

def _categorize_error(error: Exception) -> str:
    """Categorize error types for more intelligent handling."""
    error_str = str(error).lower()
    if isinstance(error, asyncio.TimeoutError) or 'timeout' in error_str:
        return 'timeout'
    elif '403' in error_str or 'forbidden' in error_str:
        return 'forbidden'
    elif '429' in error_str or 'too many requests' in error_str:
        return 'rate_limit'
    elif '404' in error_str or 'not found' in error_str:
        return 'not_found'
    elif '5' in error_str and ('00' in error_str or 'server error' in error_str):
        return 'server_error'
    elif 'ssl' in error_str or 'certificate' in error_str:
        return 'ssl_error'
    elif 'connection' in error_str:
        return 'connection_error'
    return 'unknown'

def _update_domain_health(domain: str, success: bool, error: Optional[Exception] = None):
    """Update domain health metrics and determine if circuit breaker should trip."""
    health = _domain_health[domain]
    current_time = time.time()
    health.total_requests += 1
    
    if success:
        # On success, potentially reset failure counts if it's been long enough
        if current_time - health.last_success > _domain_success_reset_time:
            health.failures = max(0, health.failures - 1)
            health.consecutive_failures = 0
            health.error_types.clear()
        health.last_success = current_time
        health.consecutive_failures = 0
    else:
        health.failures += 1
        health.consecutive_failures += 1
        if error:
            error_type = _categorize_error(error)
            health.error_types[error_type] += 1
            
            # Adjust circuit breaker behavior based on error type
            if error_type in {'forbidden', 'rate_limit'}:
                # More aggressive backoff for these error types
                health.timeout_until = current_time + (_domain_failure_timeout * 2)
            elif error_type in {'server_error', 'timeout'}:
                # Standard backoff
                health.timeout_until = current_time + _domain_failure_timeout
            elif error_type == 'not_found':
                # Don't trigger circuit breaker for 404s
                health.failures = max(0, health.failures - 1)
    
    # Update success rate
    health.success_rate = 1 - (health.failures / max(health.total_requests, 1))
    
    # Determine if circuit breaker should trip
    should_trip = (
        health.consecutive_failures >= _domain_failure_threshold or
        health.success_rate < 0.5 or
        any(count >= 2 for error_type, count in health.error_types.items() 
            if error_type in {'forbidden', 'rate_limit'})
    )
    
    if should_trip and health.timeout_until < current_time:
        health.timeout_until = current_time + _domain_failure_timeout

def _is_circuit_open(domain: str) -> bool:
    """Check if circuit breaker is open for a domain."""
    health = _domain_health[domain]
    return time.time() < health.timeout_until

async def get_browser() -> Browser:
    """Get or create a browser instance with stealth optimizations."""
    global _browser
    if _browser is None:
        playwright = await async_playwright().start()
        _browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--disable-site-isolation-trials',
            ]
        )
    return _browser

async def get_browser_context() -> BrowserContext:
    """Get a browser context from the pool or create a new one."""
    async with _context_pool_lock:
        if _context_pool:
            return _context_pool.pop()
        
        browser = await get_browser()
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=random.choice(USER_AGENTS),
            locale='en-US',
            timezone_id='America/New_York',
            permissions=['geolocation'],
            java_script_enabled=True,
            bypass_csp=True,
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'sec-ch-ua': '"Chromium";v="92", " Not A;Brand";v="99"',
                'sec-ch-ua-mobile': '?0',
                'Upgrade-Insecure-Requests': '1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
        )
        
        # Add stealth scripts
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)
        
        return context

async def release_context(context: BrowserContext):
    """Release a browser context back to the pool or close it if pool is full."""
    async with _context_pool_lock:
        if len(_context_pool) < _max_contexts:
            _context_pool.append(context)
        else:
            await context.close()

def calculate_adaptive_delay(domain: str) -> float:
    """Calculate adaptive delay based on recent request history."""
    current_time = time.time()
    recent_requests = [t for t in _domain_request_times[domain] 
                      if current_time - t < _domain_request_window]
    _domain_request_times[domain] = recent_requests
    
    if not recent_requests:
        return _min_request_delay
    
    request_rate = len(recent_requests) / _domain_request_window
    # Exponential backoff based on request rate
    delay = min(_min_request_delay * (2 ** request_rate), _max_request_delay)
    return delay + random.uniform(0, 1)  # Add jitter

async def _fetch_with_javascript(url: str) -> Optional[str]:
    """Fetch webpage content using Playwright for JavaScript-rendered pages."""
    domain = urllib.parse.urlparse(url).netloc
    delay = calculate_adaptive_delay(domain)
    await asyncio.sleep(delay)
    
    context = await get_browser_context()
    try:
        page = await context.new_page()
        
        # Add random mouse movements and scrolling
        await page.evaluate("""
            () => {
                const randomMove = () => {
                    const x = Math.floor(Math.random() * window.innerWidth);
                    const y = Math.floor(Math.random() * window.innerHeight);
                    window.dispatchEvent(new MouseEvent('mousemove', { clientX: x, clientY: y }));
                };
                setInterval(randomMove, 1000);
            }
        """)
        
        # Navigate with timeout and wait for network idle
        await page.goto(url, wait_until='networkidle', timeout=30000)
        
        # Random scrolling behavior
        await page.evaluate("""
            () => {
                const maxScroll = Math.max(document.body.scrollHeight, 2000);
                const scrollSteps = Math.floor(Math.random() * 5) + 3;
                for (let i = 0; i < scrollSteps; i++) {
                    const pos = Math.floor(Math.random() * maxScroll);
                    window.scrollTo(0, pos);
                }
            }
        """)
        
        # Wait for common content selectors with random delays
        for selector in ['article', '.article-body', '.post-content', 'main', 'body']:
            try:
                await page.wait_for_selector(selector, timeout=5000)
                await asyncio.sleep(random.uniform(0.5, 2.0))
                break
            except:
                continue
        
        content = await page.content()
        await page.close()
        
        # Process content
        try:
            from trafilatura import extract
            extracted = extract(content, include_links=False)
            if extracted:
                return extracted
        except ImportError:
            pass
        
        soup = BeautifulSoup(content, 'html.parser')
        for selector in ['div.ad-container', 'aside', 'footer', 'nav', 'script', 'style']:
            for element in soup.select(selector):
                element.decompose()
        
        main_content = soup.select_one('article, .article-body, .post-content, main') or soup.body
        return ' '.join(main_content.stripped_strings) if main_content else None
        
    except Exception as e:
        logger.warning(f"Failed to fetch with JavaScript for {url}: {str(e)}")
        return None
    finally:
        await release_context(context)
        _domain_request_times[domain].append(time.time())

def _is_likely_javascript_rendered(html: str, content: Optional[str]) -> bool:
    """Check if the page is likely to be JavaScript rendered."""
    if not content or not content.strip():
        return True
        
    # Common patterns that indicate JS rendering
    js_patterns = [
        r'<div\s+id="__next">\s*</div>',  # Next.js
        r'<div\s+id="root">\s*</div>',     # React
        r'<div\s+id="app">\s*</div>',      # Vue
        r'<noscript>.*?enable JavaScript.*?</noscript>',
        r'data-react',
        r'ng-app',
        r'vue-app'
    ]
    
    return any(re.search(pattern, html, re.IGNORECASE) for pattern in js_patterns)

USER_AGENTS = [
    'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 13_2_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/13.0.3 Mobile/15E148 Safari/604.1'
]

# Response Models
class SearchResult(BaseModel):
    """Model for a single search result with content"""
    title: str
    url: str
    snippet: str
    source: str
    content: Optional[str] = None
    relevance_score: float = 1.0

class WebSearchMetrics(BaseModel):
    """Model for tracking search performance metrics"""
    total_time: float
    search_time: float
    content_fetch_time: float
    successful_fetches: int
    failed_fetches: int
    failed_domains: Dict[str, int]

class WebSearchResponse(BaseModel):
    """Model for web search results with content"""
    results: List[SearchResult]
    query: str
    total_results: int
    metrics: Optional[WebSearchMetrics] = None

class DistanceResult(BaseModel):
    """Model for distance calculation results"""
    origin: str
    destination: str
    distance: Optional[str] = None
    duration: Optional[str] = None
    status: str
    error: Optional[str] = None

class NavigationStep(BaseModel):
    """Model for a single navigation step"""
    instruction: str
    distance: float
    duration: float
    mode: str

class NavigationResponse(BaseModel):
    """Model for navigation directions"""
    steps: List[NavigationStep]
    total_distance: float
    total_duration: float
    start_location: str
    end_location: str
    transport_mode: str

# Track failed domains for circuit breaking
_domain_failures = defaultdict(int)
_domain_failure_threshold = 3
_domain_failure_timeout = 300  # 5 minutes

def _get_random_headers() -> Dict[str, str]:
    """Generate random headers for each request"""
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': random.choice([
            'https://www.google.com/',
            'https://www.bing.com/',
            'https://www.duckduckgo.com/'
        ]),
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1'
    }

async def _fetch_webpage_content(url: str, session: RetryClient, semaphore: asyncio.Semaphore) -> Optional[str]:
    """Helper function to fetch and extract content from a webpage with improved error handling."""
    domain = urllib.parse.urlparse(url).netloc
    
    # Circuit breaker check
    if _is_circuit_open(domain):
        logger.warning(f"Circuit breaker active for domain: {domain}")
        return None
    
    async with semaphore:
        error = None
        try:
            async with async_timeout.timeout(20):
                async with session.get(url, headers=_get_random_headers()) as response:
                    if response.status == 200:
                        html = await response.text()
                        
                        # First try regular extraction
                        try:
                            from trafilatura import extract
                            content = extract(html, include_links=False)
                            if content and not _is_likely_javascript_rendered(html, content):
                                _update_domain_health(domain, True)
                                return content
                        except ImportError:
                            pass
                        
                        # Try BeautifulSoup if trafilatura didn't work
                        if not content:
                            soup = BeautifulSoup(html, 'html.parser')
                            for selector in ['div.ad-container', 'aside', 'footer', 'nav', 'script', 'style']:
                                for element in soup.select(selector):
                                    element.decompose()
                            
                            main_content = soup.select_one('article, .article-body, .post-content, main') or soup.body
                            content = ' '.join(main_content.stripped_strings) if main_content else None
                        
                        # If content is empty or likely JS-rendered, try with Playwright
                        if _is_likely_javascript_rendered(html, content):
                            logger.info(f"Detected JavaScript-rendered content for {url}, using Playwright")
                            js_content = await _fetch_with_javascript(url)
                            if js_content:
                                _update_domain_health(domain, True)
                                return js_content
                        
                        if content:
                            _update_domain_health(domain, True)
                            return content
                    
                    error = ValueError(f"HTTP {response.status}")
                    _update_domain_health(domain, False, error)
                    return None

        except Exception as e:
            error = e
            logger.warning(f"Failed to fetch {url}: {str(e)}")
            _update_domain_health(domain, False, e)
            return None

async def _perform_brave_search(session: aiohttp.ClientSession, query: str, num_results: int) -> Tuple[List[dict], int]:
    """Execute the Brave search API call and return results."""
    api_key = os.getenv('BRAVE_SEARCH_API_KEY')
    if not api_key:
        raise ValueError("BRAVE_SEARCH_API_KEY not found in environment variables")

    brave_search_url = 'https://api.search.brave.com/res/v1/web/search'
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': api_key
    }
    params = {
        'q': query,
        'count': min(num_results, 20),
        'search_lang': 'en',
        'safesearch': 'moderate',
        'extra_snippets': 'true',
        'format': 'json'
    }

    async with session.get(brave_search_url, headers=headers, params=params) as response:
        if response.status != 200:
            error_text = await response.text()
            raise ValueError(f"Brave Search API returned status {response.status}: {error_text}")
        
        search_data = await response.json()
        results = search_data.get('web', {}).get('results', [])
        total_results = search_data.get('web', {}).get('total_results', 0)
        return results, total_results

async def cleanup_browser():
    """Cleanup function to close the browser when done."""
    global _browser
    if _browser:
        await _browser.close()
        _browser = None

@tool_registry.register(description="Perform a web search using Brave Search API")
async def web_search(
    query: str,
    num_results: int = 5,
    fetch_content: bool = True,
    max_concurrent_fetches: int = 10
) -> WebSearchResponse:
    """
    Perform a web search using Brave Search API and optionally fetch content from results.
    Now with improved concurrency control and performance monitoring.
    """
    start_time = time.time()
    search_start = time.time()
    metrics = {
        'successful_fetches': 0,
        'failed_fetches': 0
    }

    try:
        logger.info(f"Performing web search: {query}")
        
        # Create a single connector and session to be reused for all requests
        connector = aiohttp.TCPConnector(
            ssl=False,
            ttl_dns_cache=300,
            limit=max_concurrent_fetches  # Match connector limit with concurrency
        )
        retry_options = ExponentialRetry(attempts=3)
        
        async with RetryClient(
            connector=connector,
            retry_options=retry_options
        ) as session:
            # Perform the search
            search_results, total_results = await _perform_brave_search(session, query, num_results)
            search_time = time.time() - search_start
            
            # Create search result objects with improved relevance scoring
            processed_results = [
                SearchResult(
                    title=result['title'],
                    url=result['url'],
                    snippet=result.get('description', ''),
                    source=urllib.parse.urlparse(result['url']).netloc,
                    relevance_score=result.get('score', 1.0 - (i * 0.05))
                )
                for i, result in enumerate(search_results)
            ]
            
            # Fetch content if requested with concurrency control
            if fetch_content:
                content_start = time.time()
                semaphore = asyncio.Semaphore(max_concurrent_fetches)
                
                tasks = [
                    _fetch_webpage_content(result.url, session, semaphore)
                    for result in processed_results
                ]
                contents = await asyncio.gather(*tasks)
                
                for result, content in zip(processed_results, contents):
                    if content:
                        result.content = content
                        metrics['successful_fetches'] += 1
                        logger.debug(f"Content fetched for {result.url}")
                    else:
                        metrics['failed_fetches'] += 1
                
                content_time = time.time() - content_start
            else:
                content_time = 0

        total_time = time.time() - start_time
        search_metrics = WebSearchMetrics(
            total_time=total_time,
            search_time=search_time,
            content_fetch_time=content_time,
            successful_fetches=metrics['successful_fetches'],
            failed_fetches=metrics['failed_fetches'],
            failed_domains=dict(_domain_failures)
        )

        logger.info(f"Search completed in {total_time:.2f}s with {len(processed_results)} results")
        return WebSearchResponse(
            results=processed_results,
            query=query,
            total_results=total_results,
            metrics=search_metrics
        )

    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise ValueError(f"Search failed: {str(e)}")
    finally:
        # Cleanup browser if it was used
        await cleanup_browser()


# Distance Matrix Tool
@tool_registry.register(description="Calculate distance and duration between locations")
async def get_distance_matrix(
    origin: str,
    destination: str,
    api_key: Optional[str] = None
) -> DistanceResult:
    """
    Calculate distance and duration between two locations using Google Distance Matrix API.
    
    Args:
        origin: Starting location
        destination: Ending location
        api_key: Google Maps API key (optional, will use environment variable if not provided)
    
    Returns:
        DistanceResult containing distance and duration information
    """
    try:
        # Get API key from environment if not provided
        api_key = api_key or os.getenv('GOOGLE_MAPS_API_KEY')
        if not api_key:
            raise ValueError("Google Maps API key not provided")
        
        # URL encode the addresses
        origin_encoded = urllib.parse.quote(origin)
        destination_encoded = urllib.parse.quote(destination)
        
        # Prepare API request
        url = 'https://maps.googleapis.com/maps/api/distancematrix/json'
        params = {
            'origins': origin,
            'destinations': destination,
            'key': api_key
        }
        
        # Make async request
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if data['status'] == 'OK' and data['rows'][0]['elements'][0]['status'] == 'OK':
                    element = data['rows'][0]['elements'][0]
                    return DistanceResult(
                        origin=origin,
                        destination=destination,
                        distance=element['distance']['text'],
                        duration=element['duration']['text'],
                        status='OK'
                    )
                else:
                    return DistanceResult(
                        origin=origin,
                        destination=destination,
                        status='ERROR',
                        error=f"API Error: {data['status']}"
                    )
                    
    except Exception as e:
        return DistanceResult(
            origin=origin,
            destination=destination,
            status='ERROR',
            error=str(e)
        )

# Navigation Tool (uses distance matrix)
@tool_registry.register(description="Get navigation directions between locations")
async def get_directions(
    start_location: str,
    end_location: str,
    transport_mode: str = "driving",
    api_key: Optional[str] = None
) -> NavigationResponse:
    """
    Generate navigation directions between two locations.
    
    Args:
        start_location: Starting location
        end_location: Destination location
        transport_mode: Mode of transport (driving, walking, cycling)
        api_key: Google Maps API key (optional)
    
    Returns:
        NavigationResponse containing route information
    """
    # Get distance information first
    distance_result = await get_distance_matrix(start_location, end_location, api_key)
    
    if distance_result.status == 'OK':
        # Convert distance and duration to float values for calculations
        try:
            distance_value = float(distance_result.distance.split()[0])
            duration_value = float(distance_result.duration.split()[0])
        except (ValueError, AttributeError):
            distance_value = 0.0
            duration_value = 0.0
            
        # Create navigation steps (simplified for now)
        steps = [
            NavigationStep(
                instruction=f"Navigate from {start_location} to {end_location}",
                distance=distance_value,
                duration=duration_value,
                mode=transport_mode
            )
        ]
        
        return NavigationResponse(
            steps=steps,
            total_distance=distance_value,
            total_duration=duration_value,
            start_location=start_location,
            end_location=end_location,
            transport_mode=transport_mode
        )
    else:
        raise ValueError(f"Failed to get directions: {distance_result.error}")