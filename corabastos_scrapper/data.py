from downloader import download_today_pdf
from parser import extract_products
from sender import send_products
import json

def main():

    pdf = download_today_pdf()

    if not pdf:
        print("No hay boletín nuevo")
        return

    products = extract_products(pdf)

    print("productos encontrados:", len(products))
    data = json.dumps(products, indent=4, ensure_ascii=False)
    print("productos encontrados:", data)
    send_products(products)


if __name__ == "__main__":
    main()
