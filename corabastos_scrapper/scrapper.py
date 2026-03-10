from downloader import download_today_pdf
from parser import extract_products
from sender import send_products


def main():

    pdf = download_today_pdf()

    if not pdf:
        print("No hay boletín nuevo")
        return

    products = extract_products(pdf)

    print("productos encontrados:", len(products))

    send_products(products)


if __name__ == "__main__":
    main()
