from .proxy import set_proxy
from scholarly import scholarly
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

# Initialize proxy settings
# set_proxy()

@api_view(["GET"])
def get_authors(request):
    """API endpoint to search for authors on Google Scholar"""
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

        # Search for the author
        try:
            # Get the generator object for author search
            search_query = scholarly.search_author(author_name)
            
            # Get the first few results (adjust limit as needed)
            authors = []
            limit = int(request.GET.get('limit', 5))  # Default to 5 results
            
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