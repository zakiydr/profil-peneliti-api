import random
import requests
from functools import wraps

from scholarly import scholarly
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
import json

from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView

from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core import serializers

class GoogleLogin(SocialLoginView):
    adapter_class = GoogleOAuth2Adapter
    client_class = OAuth2Client

@api_view(['GET'])
def get_current_user(request):
    if request.user.is_authenticated:
        user = {
            'email': request.user.email,
            'name': f"{request.user.first_name} {request.user.last_name}",
            'profile_picture': request.user.profile_picture
        }
        return Response(user)
    return Response({'error': 'Not authenticated'}, status=401)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data["refresh_token"]
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(status=204)
        except Exception as e:
            return Response({'error': str(e)}, status=400)



@api_view(['GET'])
# @rotate_proxy
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