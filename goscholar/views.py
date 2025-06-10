import random
import time
import json
import requests
import logging
import os
import threading
from threading import local

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from scholarly import scholarly, ProxyGenerator
from scholarly._proxy_generator import MaxTriesExceededException, DOSException # Import specific exceptions

# Import our custom proxy manager
# from .proxy_decorator import direct_proxy_rotation
# from .proxy_rotator import proxy_rotator 

# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_LIMIT = 10
DEFAULT_PAGE = 1
MAX_AUTHORS = 50
MAX_PUBLICATIONS = 50
MAX_CITATIONS = 100

# --- Helper function to setup a proxy from the GitHub list ---
def setup_rayobyte_proxy():
    """
    Configures scholarly to use your specific Rayobyte residential proxy credentials.
    Returns True on success, False on failure.
    """
    # IMPORTANT: For production, move these to environment variables or Django settings.
    proxy_user = os.getenv("RAYOBYTE_USER", "zakinomercy_gmail_com")
    proxy_pass = os.getenv("RAYOBYTE_PASS", "carpediem")
    proxy_host = os.getenv("RAYOBYTE_HOST", "la.residential.rayobyte.com")
    proxy_port = os.getenv("RAYOBYTE_PORT", "8000")

    if not all([proxy_user, proxy_pass, proxy_host]):
        logger.error("Rayobyte proxy credentials are not fully configured.")
        return False
        
    # Construct the full proxy URL - fixed format
    proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
    
    logger.info(f"Attempting to use Rayobyte proxy at {proxy_host}:{proxy_port}")

    try:
        pg = ProxyGenerator()
        
        # Use the correct method name and parameters
        pg.SingleProxy(http=proxy_url, https=proxy_url)
        
        # Configure scholarly with the proxy
        scholarly.use_proxy(pg)
        
        # Test the proxy with a simple query
        test_query = scholarly.search_author("test")
        
        logger.info("Scholarly successfully configured with Rayobyte proxy.")
        return True
            
    except Exception as e:
        logger.error(f"Proxy setup failed: {e}", exc_info=True)
        return False



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

@api_view(["GET"])
def get_author_by_name(request):
    """
    Get detailed information for a single author by name.
    Enhanced with better error handling and anti-detection measures.
    """
    author_name = request.GET.get('author')
    if not author_name:
        return Response(
            {"error": "Author parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Setup proxy
    if not setup_rayobyte_proxy():
        logger.warning("Proxy setup failed, attempting without proxy...")
        # Optionally try without proxy as fallback
        # scholarly.use_proxy(None)

    try:
        logger.info(f"Searching for author '{author_name}'...")
        
        # # Add delay before search
        # add_random_delay()
        
        # Perform search with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                search_query = scholarly.search_author(author_name)
                author_result = next(search_query, None)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                logger.warning(f"Search attempt {attempt + 1} failed, retrying...")
                time.sleep(random.uniform(2, 5))

        if author_result is None:
            logger.warning(f"No author found for '{author_name}'")
            return Response(
                {"error": "No author found matching the search criteria"},
                status=status.HTTP_404_NOT_FOUND
            )

        logger.info(f"Found author: {author_result.get('name', 'N/A')}. Filling details...")
        
        # Add delay before filling details
        add_random_delay()
        
        # Fill author details with retry logic
        for attempt in range(max_retries):
            try:
                filled_author = scholarly.fill(author_result)
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                logger.warning(f"Fill attempt {attempt + 1} failed, retrying...")
                time.sleep(random.uniform(3, 7))
        
        # Clean up sensitive data before returning
        response_data = dict(filled_author)
        
        return Response(response_data, status=status.HTTP_200_OK)

    except MaxTriesExceededException:
        logger.error("MaxTriesExceededException: Requests are being blocked by Google")
        return Response(
            {"error": "Request blocked by Google. Please try again later or check proxy configuration."},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    except Exception as e:
        error_msg = str(e).lower()
        
        # Handle specific HTTP errors
        if "403" in error_msg or "forbidden" in error_msg:
            logger.error("HTTP 403: Access forbidden by Google")
            return Response(
                {"error": "Access forbidden. Google may be blocking requests. Try again later."},
                status=status.HTTP_403_FORBIDDEN
            )
        elif "429" in error_msg or "too many requests" in error_msg:
            logger.error("HTTP 429: Too many requests")
            return Response(
                {"error": "Rate limit exceeded. Please wait before making another request."},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        elif "timeout" in error_msg:
            logger.error("Request timeout")
            return Response(
                {"error": "Request timed out. Please try again."},
                status=status.HTTP_408_REQUEST_TIMEOUT
            )
        else:
            logger.exception(f"Unexpected error for author '{author_name}'")
            return Response(
                {'error': f"An unexpected error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    finally:
        # Always clean up proxy settings
        try:
            scholarly.use_proxy(None)
        except:
            pass

@api_view()
def get_author_by_name_with_proxy(request):
    """
    Get detailed information for a single author by name.
    
    Query Parameters:
        author (str): Name of the author to search
    Returns:
        Response: Detailed author information
    """
    author_name = request.GET.get('author')
    if not author_name:
        return Response(
            {"error": "Author parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Fetch an HTTP proxy list
    # IMPORTANT: Change this URL to the actual URL of an HTTP proxy list
    http_proxy_list_url = 'https://raw.githubusercontent.com/monosans/proxy-list/refs/heads/main/proxies/http.txt' # EXAMPLE URL
    proxies = []
    try:
        response = requests.get(http_proxy_list_url, timeout=10)
        if response.status_code == 200:
            # Assuming format is host:port
            proxies = [line.strip() for line in response.text.split('\n') if line.strip() and ':' in line]
            logger.info(f"Successfully fetched {len(proxies)} HTTP proxies.")
        else:
            logger.warning(f"Failed to fetch HTTP proxy list: {response.status_code}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching HTTP proxy list: {e}")

    pg = ProxyGenerator()
    proxy_configured = False
    current_proxy_url = "None"

    if proxies:
        selected_proxy = random.choice(proxies)
        # Format as an HTTP proxy URL
        # Ensure the proxy list provides HTTP proxies, not HTTPS-only proxies for this scheme
        http_proxy_url = f"http://{selected_proxy}" # Assumes proxies are host:port
        # If proxies require user/pass: http_proxy_url = f"http://user:pass@{selected_proxy}"
        current_proxy_url = http_proxy_url
        logger.info(f"Attempting to use HTTP proxy: {http_proxy_url}")
        
        # For HTTP proxies, you provide the same URL for both http and https parameters
        # if the proxy supports tunneling HTTPS requests (most do).
        # Scholarly/httpx will use the HTTP proxy for HTTPS traffic via the CONNECT method.
        success = pg.SingleProxy(http=http_proxy_url, https=http_proxy_url) 
        
        if success:
            scholarly.use_proxy(pg, pg) # Force usage
            logger.info(f"Successfully configured scholarly to use HTTP proxy: {http_proxy_url}")
            proxy_configured = True
        else:
            logger.warning(f"Failed to set up HTTP proxy {http_proxy_url} in ProxyGenerator. Proceeding without proxy.")
            scholarly.use_proxy(None)
    else:
        logger.warning("No HTTP proxies available from the list. Proceeding without proxy.")
        scholarly.use_proxy(None)

    try:
        #... (rest of the scholarly search logic as in the previous improved example)...
        logger.info(f"Searching for author '{author_name}'...")
        search_query = scholarly.search_author(author_name)
        author_result = next(search_query, None)
        
        if author_result is None:
            logger.info(f"No author found matching '{author_name}' from initial search.")
            return Response(
                {"error": "No author found matching the search criteria"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        logger.info(f"Found author: {author_result.get('name', 'N/A')}. Filling details...")
        filled_author = scholarly.fill(author_result)
        return Response(filled_author, status=status.HTTP_200_OK)

    except MaxTriesExceededException as e:
        logger.error(f"Scholarly MaxTriesExceededException for '{author_name}'. Proxy: {current_proxy_url}. Error: {e}", exc_info=True)
        return Response(
            {'error': f"Failed to retrieve author details after multiple tries (MaxTriesExceededException). Google Scholar may be blocking the proxy or IP. Details: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE 
        )
    except DOSException as e:
        logger.error(f"Scholarly DOSException for '{author_name}'. Proxy: {http_proxy_list_url if proxy_configured else 'None'}. Error: {e}", exc_info=True)
        return Response(
            {'error': f"Failed to retrieve author details due to perceived DOS attack (DOSException). Details: {str(e)}"},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    except StopIteration: # Should be caught by next(search_query, None) check now
        logger.warning(f"No author found for '{author_name}' (StopIteration).")
        return Response(
            {"error": "No author found matching the search criteria"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.exception(f"An unexpected error occurred retrieving author details for '{author_name}'. Proxy: {http_proxy_list_url if proxy_configured else 'None'}. Error: {str(e)}")
        return Response(
            {'error': f"An unexpected error occurred: {str(e)}"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    finally:
        # It's good practice to reset proxy settings if they are global,
        # especially in a server environment, to avoid interference between requests.
        # However, scholarly.use_proxy modifies global state within the scholarly module.
        # If each request sets its own proxy, this might be okay, but be mindful.
        # For true isolation, you might need to run scholarly operations in separate processes
        # or use a forked version of scholarly that allows instance-based proxy configuration.
        # For now, we'll assume each API call reconfigures as needed.
        pass

                
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