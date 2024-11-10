from .proxy import set_proxy
from scholarly import scholarly
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger



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
        
        # for author in search_query:
        #     authors.append(author)

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

        return Response(response_data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response(
            {'error': str(e)}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

        
@api_view(["GET"])
def get_author_by_id(request, id):
    try:
        author = scholarly.search_author_id(id)
        author_detail = scholarly.fill(author)
        if not id:
            return Response({"error": f'Scholar ID is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(author_detail, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({"error": f'Unexpected error: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        