import re
from pypdf import PdfReader

pattern = re.compile(
    r"^\d+\s+\d+\.\s+(.*?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\w+)\s+(Subio|Bajo|Estable)$"
)

CATEGORIES = [
    "FRUTAS",
    "HORTALIZAS",
    "TUBERCULOS Y RAICES",
    "GRANOS Y PROCESADOS",
    "PESCADOS Y MARISCOS",
    "CARNICOS",
    "POLLO",
    "LACTEOS"
]


def split_category_product(text):

    for cat in CATEGORIES:
        if text.startswith(cat):
            category = cat
            product = text[len(cat):].strip()
            return category, product

    return None, text


def extract_products(pdf_path):

    reader = PdfReader(pdf_path)
    products = []

    for page in reader.pages:

        text = page.extract_text()
        if not text:
            continue

        for line in text.split("\n"):

            match = pattern.search(line)

            if not match:
                continue

            raw_text = match.group(1)

            category, name = split_category_product(raw_text)

            products.append({
                "category": category,
                "name": name,
                "price_extra": int(match.group(2)),
                "price_primera": int(match.group(3)),
                "quantity": int(match.group(4)),
                "unit": match.group(5),
                "variation": match.group(6),
            })

    return products



# import re
# from pypdf import PdfReader
#
# pattern = re.compile(
#     r"^\d+\s+\d+\.\s+(.*?)\s+(\d+)\s+(\d+)\s+(\d+)\s+(.+?)\s+(Subio|Bajo|Estable)$"
# )
#
# CATEGORIES = [
#     "FRUTAS",
#     "HORTALIZAS",
#     "GRANOS Y PROCESADOS",
#     "PESCADOS Y MARISCOS",
#     "CARNICOS",
#     "POLLO",
# ]
#
#
# def clean_product_name(text):
#     for cat in CATEGORIES:
#         if text.startswith(cat):
#             return text[len(cat):].strip()
#     return text
#
#
# def extract_products(pdf_path):
#
#     reader = PdfReader(pdf_path)
#     products = []
#
#     for page in reader.pages:
#
#         text = page.extract_text()
#         if not text:
#             continue
#
#         for line in text.split("\n"):
#
#             match = pattern.search(line)
#
#             if not match:
#                 continue
#
#             raw_name = match.group(1)
#
#             price_extra = int(match.group(2))
#             price_primera = int(match.group(3))
#             quantity = int(match.group(4))
#             unit = match.group(5)
#             variation = match.group(6)
#
#             name = clean_product_name(raw_name)
#
#             products.append(
#                 {
#                     "name": name,
#                     "price_extra": price_extra,
#                     "price_primera": price_primera,
#                     "quantity": quantity,
#                     "unit": unit,
#                     "variation": variation,
#                 }
#             )
#
#     return products
#


# import re
# from pypdf import PdfReader
#
# UNITS = {
#     "KILO",
#     "CAJA",
#     "CANASTILLA",
#     "BOLSA",
#     "BULTO",
#     "DOCENA",
#     "ATADO",
#     "ROLLO",
#     "TONELADA",
# }
#
# def extract_product_name(line: str) -> str:
#
#     text = line.split("$")[0].strip()
#
#     words = text.split()
#
#     name_parts = []
#
#     for word in words:
#
#         if re.match(r"\d+", word):
#             break
#
#         if word in UNITS:
#             break
#
#         name_parts.append(word)
#
#     return " ".join(name_parts)
#
# def extract_products(pdf_path):
#
#     reader = PdfReader(pdf_path)
#     products = []
#
#
#
#     for i in range(0, 4):
#         page = reader.pages[i]
#         text = page.extract_text()
#
#
#         if not text:
#             continue
#         for line in text.split("."):
#
#             if "$" not in line:
#                 continue
#
#             parts = line.split(".")
#
#             if len(parts) < 4:
#                 continue
#
#             precio_extra = parts[1].split()[0]
#             precio_primera = parts[2].split()[0]
#             precio_unidad = parts[3].split()[0]
#             variacion = parts[3].split()[-1]
#
#             products.append({
#                 "name": extract_product_name(line),
#                 "price_extra": int(precio_extra),
#                 "price_primera": int(precio_primera),
#                 "price": int(precio_unidad),
#                 "variation": variacion
#             })
#
#     return products
