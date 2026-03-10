import requests

API_URL = "http://127.0.0.1:8000/api/v2/dashboard/products/update-prices/"


def send_products(products):

    r = requests.post(API_URL, json=products)

    print("status:", r.status_code)
