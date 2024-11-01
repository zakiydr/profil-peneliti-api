from .proxy import set_proxy
from scholarly import scholarly
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Initialize proxy settings
# set_proxy()

@api_view(["GET"])
def get_authors(request):
    try:
        author_name = request.GET.get('author')
        if not author_name:
            return Response(
                {"error": "Author parameter is required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Set up proxy before searching
        # if not set_proxy():
        #     return Response(
        #         {"error": "Failed to set up proxy connection"}, 
        #         status=status.HTTP_503_SERVICE_UNAVAILABLE
        #     )
        try:
            search_query = scholarly.search_author(author_name)
            authors = []
            limit = int(request.GET.get('limit'))
            
            for i, author in enumerate(search_query):
                if i >= limit:
                    break
                authors.append(author)

            return Response({
                "authors": authors,
                "count": len(authors)
            }, status=status.HTTP_200_OK)

        except StopIteration:
            return Response({
                "authors": [],
                "message": "No authors found"
            }, status=status.HTTP_404_NOT_FOUND)
            
    except Exception as e:
        return Response(
            {'error': f'Unexpected error: {str(e)}'}, 
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
        