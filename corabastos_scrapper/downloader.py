import requests
from datetime import datetime
from pathlib import Path

BASE_URL = "https://corabastos.com.co/wp-content/uploads"


def format_date(date: int) -> str:
    if date < 10:
        return f'0{date}'
    return str(date)


def download_today_pdf():

    today = datetime.now().strftime("%Y%m%d")
    year = datetime.now().year
    month = datetime.now().month
    filename = f"Boletin_diario_{today}-sn.pdf"

    url = f'{BASE_URL}/{year}/{format_date(month)}/{filename}'
    print(url)

    folder = Path("newsletters")
    folder.mkdir(exist_ok=True)

    file_path = folder / filename

    if file_path.exists():
        return file_path
    
    r = requests.get(url)

    if r.status_code == 200:

        with open(file_path, "wb") as f:
            f.write(r.content)

        return file_path

    return None
