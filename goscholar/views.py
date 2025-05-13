import random
import requests
import time
import json
import logging
from functools import wraps

from scholarly import scholarly, ProxyGenerator
from fp.fp import FreeProxy

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core import serializers

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .proxy_rotator import ensure_scholarly_proxy, handle_scholarly_error, rotate_scholarly_proxy, refresh_proxy_list


# Configure logging
logger = logging.getLogger(__name__)

# Constants
DEFAULT_LIMIT = 10
DEFAULT_PAGE = 1
MAX_AUTHORS = 50
MAX_PUBLICATIONS = 50
MAX_CITATIONS = 100
MAX_PROXY_ATTEMPTS = 5

# Utility functions
def refresh_proxies(request):
    """
    Admin endpoint to force refresh of the proxy list
    
    Returns:
        Response: Status of the refresh operation
    """
    try:
        success = refresh_proxy_list()
        rotate_scholarly_proxy(force=True)
        
        if success:
            return Response(
                {"status": "success", "message": "Proxy list refreshed successfully"}, 
                status=status.HTTP_200_OK
            )
        else:
            return Response(
                {"status": "error", "message": "Failed to refresh proxy list"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    except Exception as e:
        logger.exception(f"Error refreshing proxies: {str(e)}")
        return Response(
            {'error': f"Failed to refresh proxies: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
# API Views
@api_view(['POST'])
def set_free_proxies(request):
    """
    Set free proxies for scholarly requests.
    
    Attempts to set up a working proxy from free sources.
    Returns a success message if successful, or an error response if not.
    """
    try:
        attempts = 0
        
        while attempts < MAX_PROXY_ATTEMPTS:
            pg = ProxyGenerator()
            proxy_is_set = pg.FreeProxies()
            
            if proxy_is_set:
                scholarly.use_proxy(pg)
                logger.info("New proxies successfully set")
                return Response(
                    {"success": True, "message": "New proxies are set!"}, 
                    status=status.HTTP_200_OK
                )
            
            attempts += 1
            add_random_delay(0.5, 1.5)
        
        logger.error("Failed to set proxies after multiple attempts")
        return Response(
            {"success": False, "message": "Failed to set proxies after multiple attempts."}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
            
    except Exception as e:
        logger.exception("Error setting free proxies")
        return Response(
            {"success": False, "error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
# @rotate_proxy_decorator
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
        
    try:
        # Perform author search
        search_query = scholarly.search_author(author_name)
        
        authors = []
        for author in search_query:
            authors.append(author)
            if len(authors) >= limit * page:
                break
            add_random_delay(0.5, 2.0)

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
        
        # Use standard JSON serialization directly in Response
        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"Error retrieving authors: {str(e)}")
        return Response(
            {'error': f"Failed to retrieve authors: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
# @rotate_proxy_decorator
def get_authors_compact(request):
    """
    Get a compact list of authors by name (limited to 10 results).
    
    Query Parameters:
        author (str): Name of the author to search
        
    Returns:
        Response: List of authors
    """
    try:
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
            add_random_delay(0.5, 1.5)

        if not authors:
            return Response(
                {"message": "No authors found matching the search criteria"}, 
                status=status.HTTP_404_NOT_FOUND
            )

        response_data = {"authors": authors}
        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception(f"Error retrieving compact author list: {str(e)}")
        return Response(
            {'error': f"Failed to retrieve authors: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
def get_author_by_name(request):
    """
    Get detailed information for a single author by name.
    
    Query Parameters:
        author (str): Name of the author to search
        refresh_proxies (bool, optional): Force refresh of proxy list before searching
        
    Returns:
        Response: Detailed author information
    """
    try:
        author = request.GET.get('author')
        force_refresh = request.GET.get('refresh_proxies', 'false').lower() == 'true'

        if not author:
            return Response(
                {"error": "Author parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Refresh proxy list if requested
        if force_refresh:
            refresh_proxy_list()
            
        # Ensure proxy is set up
        ensure_scholarly_proxy()
        
        # Try to get author data with proxy rotation and retries
        max_retries = 5  # Increased retries since we have more proxies
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                search_query = scholarly.search_author(author)
                
                try:
                    author_result = next(search_query)
                    result = scholarly.fill(author_result)
                    return Response(result, status=status.HTTP_200_OK)
                except StopIteration:
                    return Response(
                        {"error": "No author found matching the search criteria"}, 
                        status=status.HTTP_404_NOT_FOUND
                    )
            except Exception as e:
                error_message = str(e).lower()
                retry_count += 1
                
                # Determine error type for better handling
                error_type = 'unknown'
                if '403' in error_message or 'forbidden' in error_message:
                    error_type = '403'
                elif 'captcha' in error_message:
                    error_type = 'captcha'
                elif 'timeout' in error_message or 'time out' in error_message:
                    error_type = 'timeout'
                elif 'connection' in error_message:
                    error_type = 'connection'
                
                # Handle error by potentially rotating proxy
                handle_scholarly_error(error_type)
                
                # If we've hit max retries, give up
                if retry_count >= max_retries:
                    logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                    raise
                else:
                    logger.warning(f"Retry {retry_count}/{max_retries} after error: {error_type}")
                    # Add a small delay between retries
                    import time
                    time.sleep(2)

    except Exception as e:
        logger.exception(f"Error retrieving author details by name: {str(e)}")
        return Response(
            {'error': f"Failed to retrieve author details: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(["GET"])
# @rotate_proxy_decorator
def get_author_by_id(request, id):
    """
    Get author information by Scholar ID.
    
    Args:
        id (str): Google Scholar ID
        
    Returns:
        Response: Detailed author information
    """
    try:
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
    except Exception as e:
        logger.exception(f"Error retrieving author by ID {id}: {str(e)}")
        return Response(
            {"error": f"Failed to retrieve author: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(["GET"])
# @rotate_proxy_decorator
def get_author_detail(request, id):
    """
    Get detailed author information including publications by Scholar ID.
    
    Args:
        id (str): Google Scholar ID
        
    Returns:
        Response: Author information and publications
    """
    try:
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
                add_random_delay(1.0, 3.0)
                
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
    except Exception as e:
        logger.exception(f"Error retrieving author details for ID {id}: {str(e)}")
        return Response(
            {"error": f"Failed to retrieve author details: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
@api_view(["GET"])
# @rotate_proxy_decorator
def get_pub_detail(request, query):
    """
    Get detailed information for a publication by search query.
    
    Args:
        query (str): Publication search query
        
    Returns:
        Response: Publication details
    """
    try:
        if not query:
            return Response(
                {"error": "Publication query is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
            
        pub_query = scholarly.search_pubs(query)
        
        try:
            pub = next(pub_query)
            # Add delay to mimic human behavior
            add_random_delay(1.0, 2.0)
            
            # Fill publication details
            pub_detail = scholarly.fill(pub)
            return Response(pub, status=status.HTTP_200_OK)
        except StopIteration:
            return Response(
                {"error": "No publications found matching the query"}, 
                status=status.HTTP_404_NOT_FOUND
            )
            
    except Exception as e:
        logger.exception(f"Error retrieving publication details for query '{query}': {str(e)}")
        return Response(
            {"error": f"Failed to retrieve publication details: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(["GET"])
# @rotate_proxy_decorator
def get_pub_detail_with_citations(request, query):
    """
    Get detailed information for a publication with its citations.
    
    Args:
        query (str): Publication search query
        
    Returns:
        Response: Publication details with citations
    """
    try:
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
                add_random_delay(1.5, 3.0)
                
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
    except Exception as e:
        logger.exception(f"Error retrieving publication details with citations for query '{query}': {str(e)}")
        return Response(
            {"error": f"Failed to retrieve publication citations: {str(e)}"}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )