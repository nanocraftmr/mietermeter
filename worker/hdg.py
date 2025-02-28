import requests

def fetch_hdg_data(ip, query_id):
    url = f"http://{ip}/ApiManager.php?action=dataRefresh"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"
    }
    data = {"nodes": query_id}
    
    try:
        response = requests.post(url, headers=headers, data=data, timeout=5)
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        if response.json():
            return response.json()  # Return the JSON data
        else:
            return "No data received from the server."
    except requests.exceptions.Timeout:
        return f"Connection to {ip} timed out."
    except requests.exceptions.RequestException as e:
        return f"Request failed: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"