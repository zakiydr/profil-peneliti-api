import random
import time
import json
import requests
import logging
import threading

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from scholarly import scholarly, ProxyGenerator

# Import our custom proxy manager
# from .proxy import DirectProxyManager, direct_proxy_rotation

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_LIMIT = 10
DEFAULT_PAGE = 1
MAX_AUTHORS = 50
MAX_PUBLICATIONS = 50
MAX_CITATIONS = 100

# API Views
import requests
import time

proxy_lock = threading.Lock()
_proxy_cache = {'list': [], 'timestamp': 0, 'ttl_seconds': 300}

def get_proxy_list():
    """
    Fetches a list of proxies from the provided URL, caches results,
    and formats them for scholarly (adds http:// prefix).

    Returns:
        list: List of proxies in http://IP:PORT format
    """
    global _proxy_cache
    url = "https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/http.txt"

    # Check cache
    if time.time() - _proxy_cache['timestamp'] < _proxy_cache['ttl_seconds']:
        print("Using cached proxy list.")
        return _proxy_cache['list']

    print("Fetching new proxy list...")
    try:
        response = requests.get(url, timeout=10) # Add a timeout
        response.raise_for_status()

        proxies = []

        for line in response.text.splitlines():
            cleaned_line = line.strip()
            if not cleaned_line:
                continue

            # Assume proxies from this list are HTTP/HTTPS and add the prefix
            # The original code only added IP:PORT lines, sticking to that pattern:
            if ':' in cleaned_line and len(cleaned_line.split(':')) == 2:
                 # Add http:// prefix required by requests/scholarly
                 formatted_proxy = f"http://{cleaned_line}"
                 proxies.append(formatted_proxy)
            # You might add logic here to handle other protocols if the source changes,
            # but for this specific source, IP:PORT + http:// is the most likely.

        # Update cache
        _proxy_cache['list'] = proxies
        _proxy_cache['timestamp'] = time.time()
        print(f"Fetched {len(proxies)} proxies.")
        return proxies

    except requests.exceptions.RequestException as e: # Catch specific request exceptions
        print(f"Error fetching proxy list: {e}")
        # Return cached list if available, otherwise empty
        if _proxy_cache['list']:
             print("Returning stale cached proxy list due to fetch error.")
             return _proxy_cache['list']
        return []
    except Exception as e:
        print(f"An unexpected error occurred while processing proxy list: {e}")
        return []    
    
@api_view(['GET'])
# @direct_proxy_rotation
def get_authors(request):
    """
    Search for authors by name with pagination.
    
    Query Parameters:
        author (str): Name of the author to search
        limit (int, optional): Number of results per page, default=10
        page (int, optional): Page number, default=1
        
    Returns:
        Response: Paginated list of authors
    """
    author_name = request.GET.get('author')
    
    # Validate required parameters
    if not author_name:
        return Response(
            {"error": "Author parameter is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Parse and validate pagination parameters
    try:
        limit = int(request.GET.get('limit', DEFAULT_LIMIT))
        page = int(request.GET.get('page', DEFAULT_PAGE))
        
        if limit < 1 or page < 1:
            raise ValueError("Limit and page must be positive integers")
    except (TypeError, ValueError) as e:
        return Response(
            {"error": f"Invalid pagination parameters: {str(e)}"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
        
    # Perform author search
    search_query = scholarly.search_author(author_name)
    
    authors = []
    for author in search_query:
        authors.append(author)
        if len(authors) >= limit * page:
            break
        # DirectProxyManager.add_random_delay(0.5, 2.0)

    # Handle pagination
    paginator = Paginator(authors, limit)

    try:
        current_page = paginator.page(page)
    except PageNotAnInteger:
        current_page = paginator.page(1)
    except EmptyPage:
        if paginator.num_pages > 0:
            current_page = paginator.page(paginator.num_pages)
        else:
            return Response(
                {"error": "No results found"},
                status=status.HTTP_404_NOT_FOUND
            )

    # Prepare response
    response_data = {
        "count": len(authors),
        "total_pages": paginator.num_pages,
        "current_page": page,
        "next_page": current_page.next_page_number() if current_page.has_next() else None,
        "previous_page": current_page.previous_page_number() if current_page.has_previous() else None,
        "authors": current_page.object_list
    }
    
    return Response(response_data, status=status.HTTP_200_OK)
        
@api_view(['GET'])
# @direct_proxy_rotation
def get_authors_compact(request):
    """
    Get a compact list of authors by name (limited to 10 results).
    
    Query Parameters:
        author (str): Name of the author to search
        
    Returns:
        Response: List of authors
    """
    author_name = request.GET.get('author')

    if not author_name:
        return Response(
            {"error": "Author parameter is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )

    search_query = scholarly.search_author(author_name)

    authors = []
    for author in search_query:
        authors.append(author)
        if len(authors) >= 10:
            break
        # DirectProxyManager.add_random_delay(0.5, 1.5)

    if not authors:
        return Response(
            {"message": "No authors found matching the search criteria"}, 
            status=status.HTTP_404_NOT_FOUND
        )

    response_data = {"authors": authors}
    return Response(response_data, status=status.HTTP_200_OK)
        
# ... (imports remain the same)
# Use the improved get_proxy_list from above
# from .utils import get_proxy_list # Assuming you put get_proxy_list in a utils file

@api_view(['GET'])
def get_author_by_name(request):
    author_name = request.GET.get('author')
    
    proxies = get_proxy_list() or [None]
    random.shuffle(proxies)
    
    for i, proxy in enumerate(proxies[:5]):
        try:
            with proxy_lock:
                pg = ProxyGenerator()
                if proxy and pg.SingleProxy(http=proxy, https=proxy):
                    scholarly.use_proxy(pg)
                else:
                    scholarly.use_proxy(None)
                
                # Perform search operations
                search_query = scholarly.search_author(author_name)
                author = next(search_query)
                return Response(scholarly.fill(author))
        
        except Exception as e:
            logger.error(f"Attempt {i+1} failed: {str(e)}")
            time.sleep(0.5 * (i+1))  # Progressive delay
        
        finally:
            scholarly.use_proxy(None)

    return Response({"error": "All proxies failed"}, status=500)
        
@api_view(["GET"])
# @direct_proxy_rotation
def get_author_by_id(request, id):
    """
    Get author information by Scholar ID.
    
    Args:
        id (str): Google Scholar ID
        
    Returns:
        Response: Detailed author information
    """
    if not id:
        return Response(
            {"error": "Scholar ID is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    author = scholarly.search_author_id(id)
    if not author:
        return Response(
            {"error": "No author found with the provided ID"}, 
            status=status.HTTP_404_NOT_FOUND
        )
        
    author_detail = scholarly.fill(author)
    return Response(author_detail, status=status.HTTP_200_OK) 
    
@api_view(["GET"])
# @direct_proxy_rotation
def get_author_detail(request, id):
    """
    Get detailed author information including publications by Scholar ID.
    
    Args:
        id (str): Google Scholar ID
        
    Returns:
        Response: Author information and publications
    """
    if not id:
        return Response(
            {"error": "Scholar ID is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    author = scholarly.search_author_id(id)
    if not author:
        return Response(
            {"error": "No author found with the provided ID"}, 
            status=status.HTTP_404_NOT_FOUND
        )
        
    author_detail = scholarly.fill(author)
    
    # Fetch publications with rate limiting
    publications = []
    try:
        pub_generator = scholarly.search_pubs(author['name'])
        
        for pub in pub_generator:
            publications.append(pub)
            # Add random delay between publication fetches
            # DirectProxyManager.add_random_delay(1.0, 3.0)
            
            # Limit the number of publications
            if len(publications) >= MAX_PUBLICATIONS:
                break
    except Exception as pub_error:
        logger.warning(f"Error fetching publications: {str(pub_error)}")
        # Continue with partial results
    
    # Combine author details with publications
    response_data = {
        'author_info': author_detail,
        'publications': publications,
        'publication_count': len(publications)
    }
    
    return Response(response_data, status=status.HTTP_200_OK)
    
@api_view(["GET"])
# @direct_proxy_rotation
def get_pub_detail(request, query):
    """
    Get detailed information for a publication by search query.
    
    Args:
        query (str): Publication search query
        
    Returns:
        Response: Publication details
    """
    if not query:
        return Response(
            {"error": "Publication query is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
        
    pub_query = scholarly.search_pubs(query)
    
    try:
        pub = next(pub_query)
        # Add delay to mimic human behavior
        # DirectProxyManager.add_random_delay(1.0, 2.0)
        
        # Fill publication details
        pub_detail = scholarly.fill(pub)
        return Response(pub_detail, status=status.HTTP_200_OK)
    except StopIteration:
        return Response(
            {"error": "No publications found matching the query"}, 
            status=status.HTTP_404_NOT_FOUND
        )

@api_view(["GET"])
# @direct_proxy_rotation
def get_pub_detail_with_citations(request, query):
    """
    Get detailed information for a publication with its citations.
    
    Args:
        query (str): Publication search query
        
    Returns:
        Response: Publication details with citations
    """
    if not query:
        return Response(
            {"error": "Publication query is required"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
        
    # Search for publications matching the query
    pub_query = scholarly.search_pubs(query)
    
    # Get the first publication from the search results
    try:
        pub = next(pub_query)
    except StopIteration:
        return Response(
            {"error": "No publications found matching the query"}, 
            status=status.HTTP_404_NOT_FOUND
        )
        
    # Fill in the details of the publication
    pub_detail = scholarly.fill(pub)
    
    # Retrieve publications that have cited the publication with rate limiting
    citations = []
    citations_by_year = {}
    
    try:
        citations_generator = scholarly.citedby(pub_detail)
        
        # Process each citing publication and fill in details
        for citation in citations_generator:
            # Add random delay between citation fetches
            # DirectProxyManager.add_random_delay(1.5, 3.0)
            
            try:
                filled_citation = scholarly.fill(citation)
                citations.append(filled_citation)
                
                # Group by year if available
                year = filled_citation.get("bib", {}).get("pub_year")
                if year:
                    citations_by_year.setdefault(year, []).append(filled_citation)
            except Exception as citation_error:
                # Log the error but continue with other citations
                logger.warning(f"Error fetching citation details: {str(citation_error)}")
            
            # Limit the number of citations
            if len(citations) >= MAX_CITATIONS:
                break
                
    except Exception as e:
        logger.warning(f"Error fetching citations: {str(e)}")
        # Continue with partial results
    
    # Sort the dictionary by year
    sorted_citations_by_year = {year: citations_by_year[year] 
                               for year in sorted(citations_by_year.keys())}
    
    # Construct the response data
    result = {
        "publication_details": pub_detail,
        "citations_by_year": sorted_citations_by_year,
        "total_citations": len(citations)
    }
    
    return Response(result, status=status.HTTP_200_OK)