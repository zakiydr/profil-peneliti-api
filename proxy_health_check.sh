# #!/bin/bash

# # Script to check and rotate proxies periodically
# # Put this file in your project root and make it executable with: chmod +x proxy_health_check.sh

# # Parameters
# PROXY_CHECK_INTERVAL=3600  # Check proxy health every hour
# API_ENDPOINT="http://localhost:8001/goscholar/refresh-proxies/"

# echo "Starting proxy health check service..."

# while true; do
#     echo "$(date): Checking proxy health and refreshing list..."
    
#     # Call the API endpoint to refresh proxies
#     RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $API_ENDPOINT)
    
#     if [ "$RESPONSE" == "200" ]; then
#         echo "$(date): Proxy refresh successful"
#     else
#         echo "$(date): Proxy refresh failed with code $RESPONSE"
#     fi
    
#     # Wait for next check interval
#     echo "Next check in $PROXY_CHECK_INTERVAL seconds"
#     sleep $PROXY_CHECK_INTERVAL
# done