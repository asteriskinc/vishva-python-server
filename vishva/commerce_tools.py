# commerce_tools.py

from typing import Dict, List, Optional
import requests
from dataclasses import dataclass

@dataclass
class WebContent:
    """Simple container for web page content"""
    url: str
    html: str
    source_site: str

def retrieve_page_content(url: str) -> WebContent:
    """
    Retrieve raw HTML content from a URL
    """
    try:
        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        return WebContent(
            url=url,
            html=response.text,
            source_site=url.split('/')[2]  # Get domain name
        )
    except Exception as e:
        print(f"Error retrieving content from {url}: {str(e)}")
        return None

def analyze_shopping_results(search_results: List[Dict], retrieved_content: List[WebContent]) -> Dict:
    """
    Analyze search results and their corresponding content
    Returns structured analysis that the agent can use
    """
    return {
        'search_results': search_results,
        'retrieved_content': [
            {
                'url': content.url,
                'source_site': content.source_site,
                'content': content.html
            }
            for content in retrieved_content if content
        ]
    }

def compare_product_pages(contents: List[WebContent]) -> Dict:
    """
    Prepare content from multiple product pages for comparison
    """
    return {
        'pages': [
            {
                'url': content.url,
                'source_site': content.source_site,
                'content': content.html
            }
            for content in contents if content
        ]
    }