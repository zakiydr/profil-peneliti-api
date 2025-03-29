import random
import requests
from functools import wraps
import time

from scholarly import scholarly, ProxyGenerator
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json

from fp.fp import FreeProxy

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core import serializers

@api_view(['POST'])
def set_free_proxies(request):
    """
    Set free proxies for scholarly requests.
    
    Attempts to set up a working proxy from free sources.
    Returns a success message if successful, or an error response if not.
    """
    try:
        attempts = 0
        max_attempts = 5  # Set a maximum number of attempts to avoid infinite loops
        
        while attempts < max_attempts:
            pg = ProxyGenerator()
            # proxy = FreeProxy(country_id=["SG", "US"], https=True).get()
            proxy_is_set = pg.FreeProxies()
            
            if proxy_is_set:
                scholarly.use_proxy(pg)
                return Response(
                    {"success": True, "message": "New proxies are set!"}, 
                    status=status.HTTP_200_OK
                )
            
            attempts += 1
            # Add small delay between attempts
            time.sleep(random.uniform(0.5, 1.5))
        
        # If we've exhausted all attempts
        return Response(
            {"success": False, "message": "Failed to set proxies after multiple attempts."}, 
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
            
    except Exception as e:
        return Response(
            {"success": False, "error": str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
# @rotate_proxy_decorator
def get_authors(request):
    author_name = request.GET.get('author')
    limit = request.GET.get('limit', 10)  
    page = request.GET.get('page', 1)
    
    try:
        limit = int(limit)
        page = int(page)
    except (TypeError, ValueError):
        return Response(
            {"error": "Invalid limit or page parameter"}, 
            status=status.HTTP_400_BAD_REQUEST
        )
        
    try:
        if not author_name:
            return Response(
                {"error": "Search parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        search_query = scholarly.search_author(author_name)
        
        authors = []
        # Add random delay between fetching results to mimic human behavior
        for author in search_query:
            authors.append(author)
            if len(authors) >= limit * page:
                break
            time.sleep(random.uniform(0.5, 2.0))

        paginator = Paginator(authors, limit)

        try:
            current_page = paginator.page(page)
        except PageNotAnInteger:
            current_page = paginator.page(1)
        except EmptyPage:
            current_page = paginator.page(paginator.num_pages)

        response_data = {
            "count": len(authors),
            "total_pages": paginator.num_pages,
            "current_page": page,
            "next_page": current_page.next_page_number() if current_page.has_next() else None,
            "previous_page": current_page.previous_page_number() if current_page.has_previous() else None,
            "authors": current_page.object_list
        }
        
        # Use safer serialization to handle potential circular references
        try:
            json_dumps = json.dumps(response_data)
            json_data = json.loads(json_dumps)
        except TypeError:
            # Fallback for non-serializable data
            simplified_data = {
                "count": len(authors),
                "total_pages": paginator.num_pages,
                "current_page": page,
                "next_page": current_page.next_page_number() if current_page.has_next() else None,
                "previous_page": current_page.previous_page_number() if current_page.has_previous() else None,
                "authors": [
                    {k: v for k, v in author.items() if isinstance(v, (str, int, float, bool, type(None)))}
                    for author in current_page.object_list
                ]
            }
            json_data = simplified_data

        return Response(json_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
# @rotate_proxy_decorator
def get_authors_compact(request):
    try:
        author_name = request.GET.get('author')

        if not author_name:
            return Response(
                {"error": "Search parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        search_query = scholarly.search_author(author_name)

        authors = []
        for author in search_query:
            authors.append(author)
            if len(authors) >= 10:
                break
            # Add small random delay between fetches
            time.sleep(random.uniform(0.5, 1.5))

        response_data = {
            "authors": authors
        }

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
# @rotate_proxy_decorator
def get_author_by_name(request):
    # Proxy Wrap
    # pg = ProxyGenerator()
    # proxy = FreeProxy(country_id=["SG".]).get()
    # pg.SingleProxy(http=)
    # scholarly.use_proxy(pg)
    try:
        author = request.GET.get('author')

        if not author:
            return Response(
                {"error": "Search parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        search_query = scholarly.search_author(author)
        
        result = scholarly.fill(next(search_query))

        return Response(result, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )        
        
@api_view(["GET"])
# @rotate_proxy_decorator
def get_author_by_id(request, id):
    try:
        if not id:
            return Response({"error": f'Scholar ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        author = scholarly.search_author_id(id)
        author_detail = scholarly.fill(author)
        
        return Response(author_detail, status=status.HTTP_200_OK) 
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET"])
# @rotate_proxy_decorator
def get_author_detail(request, id):
    try:
        if not id:
            return Response({"error": f'Scholar ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        author = scholarly.search_author_id(id)
        author_detail = scholarly.fill(author)
        
        # Fetch publications with rate limiting
        publications = []
        pub_generator = scholarly.search_pubs(author['name'])
        
        for pub in pub_generator:
            publications.append(pub)
            # Add random delay between publication fetches
            time.sleep(random.uniform(1.0, 3.0))
            
            # Limit the number of publications to prevent long-running requests
            if len(publications) >= 50:
                break
        
        # Combine author details with publications
        response_data = {
            'author_info': author_detail,
            'publications': publications
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
@api_view(["GET"])
# @rotate_proxy_decorator
def get_pub_detail(request, query):
    try:
        pub_query = scholarly.search_pubs(query)
        
        # Get the first publication
        try:
            pub = next(pub_query)
            # Add delay to mimic human behavior
            time.sleep(random.uniform(1.0, 2.0))
            
            # Fill publication details
            pub_detail = scholarly.fill(pub)
            
            return Response(pub_detail, status=status.HTTP_200_OK)
        except StopIteration:
            return Response({"error": "No publications found"}, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# The commented out get_pub_detail function with citations can be improved as follows:
'''
@api_view(["GET"])
# @rotate_proxy_decorator
def get_pub_detail_with_citations(request, query):
    try:
        # Search for publications matching the query
        pub_query = scholarly.search_pubs(query)
        
        # Get the first publication from the search results
        try:
            pub = next(pub_query)
        except StopIteration:
            return Response({"error": "No publications found"}, status=status.HTTP_404_NOT_FOUND)
            
        # Fill in the details of the publication
        pub_detail = scholarly.fill(pub)
        
        # Retrieve publications that have cited the publication with rate limiting
        citations = []
        citations_generator = scholarly.citedby(pub_detail)
        
        # Process each citing publication and fill in details
        for citation in citations_generator:
            # Add random delay between citation fetches
            time.sleep(random.uniform(1.5, 3.0))
            
            try:
                filled_citation = scholarly.fill(citation)
                citations.append(filled_citation)
            except Exception as citation_error:
                # Log the error but continue with other citations
                print(f"Error fetching citation details: {str(citation_error)}")
            
            # Limit the number of citations to prevent long-running requests
            if len(citations) >= 100:
                break
        
        # Group citations by publication year (if available)
        citations_by_year = {}
        for citation in citations:
            # Attempt to get the publication year from the 'bib' field
            year = citation.get("bib", {}).get("pub_year")
            if year:
                citations_by_year.setdefault(year, []).append(citation)
        
        # Sort the dictionary by year
        sorted_citations_by_year = {year: citations_by_year[year] for year in sorted(citations_by_year)}
        
        # Construct the response data
        result = {
            "pub_detail": pub_detail,
            "citations_by_year": sorted_citations_by_year,
            "total_citations": len(citations)
        }
        
        return Response(result, status=status.HTTP_200_OK)
    except Exception as e:
        # Return the exception message in the response in case of an error
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
'''