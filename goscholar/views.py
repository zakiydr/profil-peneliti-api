import random
import requests
from functools import wraps

from scholarly import scholarly
from scholarly import ProxyGenerator
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core import serializers

@api_view(['GET'])
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
        
        authors = list(search_query)

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
        
        json_dumps = json.dumps(response_data)
        json_data = json.loads(json_dumps) 

        return Response(json_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        
@api_view(['GET'])
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
def get_author_by_name(request):
    pg = ProxyGenerator()
    pg.FreeProxies()
    scholarly.use_proxy(pg)

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
# @rotate_proxy
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
# @rotate_proxy
def get_author_detail(request, id):
    try:
        if not id:
            return Response({"error": f'Scholar ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        author = scholarly.search_author_id(id)
        author_detail = scholarly.fill(author)
        
        # Fetch publications
        publications = list(scholarly.search_pubs(author['name']))
        
        # Combine author details with publications
        response_data = {
            'author_info': author_detail,
            'publications': publications
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
@api_view(["GET"])
def get_pub_detail(request, query):
    try:
        pub_query = scholarly.search_pubs(query)
        
        pub = next(pub_query)
        
        pub_detail = scholarly.fill(next(pub_query))
        
        return Response(pub, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(exception=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    
# @api_view(["GET"])
# def get_pub_detail(request, query):
#     try:
#         # Search for publications matching the query
#         pub_query = scholarly.search_pubs(query)
#         # Get the first publication from the search results
#         pub = next(pub_query)
#         # Fill in the details of the publication
#         pub_detail = scholarly.fill(pub)
        
#         # Retrieve publications that have cited the publication
#         citations_generator = scholarly.citedby(pub_detail)
        
#         # Process each citing publication and fill in details
#         citations = []
#         for citation in citations_generator:
#             filled_citation = scholarly.fill(citation)
#             citations.append(filled_citation)
        
#         # Group citations by publication year (if available)
#         citations_by_year = {}
#         for citation in citations:
#             # Attempt to get the publication year from the 'bib' field
#             year = citation.get("bib", {}).get("pub_year")
#             if year:
#                 citations_by_year.setdefault(year, []).append(citation)
        
#         # Optionally, sort the dictionary by year
#         sorted_citations_by_year = {year: citations_by_year[year] for year in sorted(citations_by_year)}
        
#         # Construct the response data
#         result = {
#             "pub_detail": pub_detail,
#             "citations_by_year": sorted_citations_by_year
#         }
        
#         return Response(result, status=status.HTTP_200_OK)
#     except Exception as e:
#         # Return the exception message in the response in case of an error
#         return Response({"exception": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
