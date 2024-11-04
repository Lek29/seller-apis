import io
import logging.config
import os
import re
import zipfile
from environs import Env

import pandas as pd
import requests

logger = logging.getLogger(__file__)


def get_product_list(last_id, client_id, seller_token):
    """Получить список товаров магазина озон.

        Args:
            last_id (str): Идентификатор последнего товара в предыдущем запросе.
            client_id (str): Идентификатор клиента для API Ozon.
            seller_token (str): Токен продавца для API Ozon.

        Returns:
            dict: список товаров и методанные

        Raises:
            requests.exceptions.HTTPError: Если запрос к API не удался.

        Example:
            >>> last_id = ""
            >>> client_id = "your_client_id"
            >>> seller_token = "your_seller_token"
            >>> product_list = get_product_list(last_id, client_id, seller_token)
            product_list['result']

    """
    url = "https://api-seller.ozon.ru/v2/product/list"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {
        "filter": {
            "visibility": "ALL",
        },
        "last_id": last_id,
        "limit": 1000,
    }
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    response_object = response.json()
    return response_object.get("result")


def get_offer_ids(client_id, seller_token):
    """Получить артикулы товаров магазина озон.

        Args:
            client_id (str): Идентификатор клиента для API Ozon.
            seller_token (str): Токен продавца для API Ozon.

        Returns:
            list: Список артикулов товаров.

        Raises:
            requests.exceptions.HTTPError: Если запрос к API не удался.

        Examples:
             >>> client_id = "your_client_id"
            >>> seller_token = "your_seller_token"
            >>> offer_ids = get_offer_ids(client_id, seller_token)
            ["ABC123", "XYZ789", ...]

    """
    last_id = ""
    product_list = []
    while True:
        some_prod = get_product_list(last_id, client_id, seller_token)
        product_list.extend(some_prod.get("items"))
        total = some_prod.get("total")
        last_id = some_prod.get("last_id")
        if total == len(product_list):
            break
    offer_ids = []
    for product in product_list:
        offer_ids.append(product.get("offer_id"))
    return offer_ids


def update_price(prices: list, client_id, seller_token):
    '''Обновить цены товаров.

        Args:
            prices (list): Список цен товаров.
            client_id (str): Идентификатор клиента для API Ozon.
            seller_token (str): Токен продавца для API Ozon.

        Returns:
            dict: Ответ от API Ozon после обновления цен.

        Raises:
            requests.exceptions.HTTPError: Если запрос к API не удался.

        Example:
        >>> client_id = "your_client_id"
        >>> seller_token = "your_seller_token"
        >>> response = update_price(prices, client_id, seller_token)
        response
    '''
    url = "https://api-seller.ozon.ru/v1/product/import/prices"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"prices": prices}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def update_stocks(stocks: list, client_id, seller_token):
    """Обновить остатки.

    Args:
        stocks (list): Список остатков товаров.
        client_id (str): Идентификатор клиента для API Ozon.
        seller_token (str): Токен продавца для API Ozon.

    Returns:
        dict: Ответ от API Ozon после обновления остатков.

    Raises:
        requests.exceptions.HTTPError: Если запрос к API не удался.

    Example:
        >>> stocks = [
                 {
                     "offer_id": "PH11042",
                    "product_id": 313455276,
                    "stock": 100,
                    "warehouse_id": 22142605386000
                 }
        ]
        >>> client_id = "your_client_id"
        >>> seller_token = "your_seller_token"
        >>> response = update_stocks(stocks, client_id, seller_token)
        response
    """
    url = "https://api-seller.ozon.ru/v1/product/import/stocks"
    headers = {
        "Client-Id": client_id,
        "Api-Key": seller_token,
    }
    payload = {"stocks": stocks}
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def download_stock():
    """Скачать файл ostatki с сайта casio.

        Returns:
            list: Список остатков часов

        Raises:
            requests.exceptions.HTTPError: Если запрос к сайту Casio не удался.

        Example:
            >>> watch_remnants = download_stock()
            watch_remnants
    """
    casio_url = "https://timeworld.ru/upload/files/ostatki.zip"
    session = requests.Session()
    response = session.get(casio_url)
    response.raise_for_status()
    with response, zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        archive.extractall(".")

    excel_file = "ostatki.xls"
    watch_remnants = pd.read_excel(
        io=excel_file,
        na_values=None,
        keep_default_na=False,
        header=17,
    ).to_dict(orient="records")
    os.remove("./ostatki.xls")
    return watch_remnants


def create_stocks(watch_remnants, offer_ids):
   '''Создать список остатков товаров для обновления на маркетплейсе.
   
        Args:
             watch_remnants (list): Список остатков часов.
            
        Returns:
            offer_ids (list): Список артикулов товаров, загруженных на маркетплейс.

        Raises:
            ValueError: Если в списке `watch_remnants` или `offer_ids` содержатся некорректные данные.

        Example:
             >>> stocks = create_stocks(watch_remnants, offer_ids)
            stocks
   '''
    stocks = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            count = str(watch.get("Количество"))
            if count == ">10":
                stock = 100
            elif count == "1":
                stock = 0
            else:
                stock = int(watch.get("Количество"))
            stocks.append({"offer_id": str(watch.get("Код")), "stock": stock})
            offer_ids.remove(str(watch.get("Код")))
    # Добавим недостающее из загруженного:
    for offer_id in offer_ids:
        stocks.append({"offer_id": offer_id, "stock": 0})
    return stocks


def create_prices(watch_remnants, offer_ids):
    ''''Создать список цен товаров для обновления на маркетплейсе.

        Args:
             watch_remnants (list): Список остатков часов
             offer_ids (list): Список артикулов товаров, загруженных на маркетплейс.

        Returns:
             list: Список цен товаров

        Example:
            >>> offer_ids = ["ABC123", "XYZ789", "DEF456"]
            >>> prices = create_prices(watch_remnants, offer_ids)
            prices
    '''
    prices = []
    for watch in watch_remnants:
        if str(watch.get("Код")) in offer_ids:
            price = {
                "auto_action_enabled": "UNKNOWN",
                "currency_code": "RUB",
                "offer_id": str(watch.get("Код")),
                "old_price": "0",
                "price": price_conversion(watch.get("Цена")),
            }
            prices.append(price)
    return prices


def price_conversion(price: str) -> str:
    ''''Преобразовать из цены со значением после точки, в цену без значения после точки.

        Args:
            price (str) : Строка содержащая занчение в формате 00.00

        Return:
            Строка содержащая значение в формате 00. Без символов и пробелов

        Example:
            >>> price_conversion("5'990.00 руб.")
            '5990'
            >>> price_conversion("789 руб")
            '789'
    '''

    return re.sub("[^0-9]", "", price.split(".")[0])


def divide(lst: list, n: int):
    """Разделить список lst на части по n элементов.

         Args:
            lst (list): Исходный список, который нужно разделить.
            n (int): Количество элементов в каждой части.

         Yields:
            list: Часть исходного списка, содержащая n элементов.

        Example:
            >>> lst = [1, 2, 3, 4, 5, 6, 7, 8, 9]
            >>> n = 3
            >>> for part in divide(lst, n):
                print(part)
            [1, 2, 3]
            [4, 5, 6]
            [7, 8, 9]
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


async def upload_prices(watch_remnants, client_id, seller_token):
    '''Асинхронно загрузить цены товаров на маркетплейс.

         Args:
            watch_remnants (list): Список остатков часов.

            client_id (str): Идентификатор клиента для API маркетплейса.
            seller_token (str): Токен продавца для API маркетплейса.

         Returns:
            list: Список цен товаров.

        Raises:
            requests.exceptions.HTTPError: Если запрос к API не удался.

        Example:
            >>> client_id = "your_client_id"
            >>> seller_token = "your_seller_token"
            >>> prices = await upload_prices(watch_remnants, client_id, seller_token)
            prices
    '''

    offer_ids = get_offer_ids(client_id, seller_token)
    prices = create_prices(watch_remnants, offer_ids)
    for some_price in list(divide(prices, 1000)):
        update_price(some_price, client_id, seller_token)
    return prices


async def upload_stocks(watch_remnants, client_id, seller_token):
    ''' Асинхронно загрузить остатки товаров на маркетплейс.

        Args:
            watch_remnants (list): Список остатков часов.
            client_id (str): Идентификатор клиента для API маркетплейса.
            seller_token (str): Токен продавца для API маркетплейса.

        Returns:
            tuple: Кортеж из двух списков:
                - Список остатков товаров с ненулевым количеством.
                - Полный список остатков товаров.

        Raises:
            requests.exceptions.HTTPError: Если запрос к API не удался.

        Example:
            >>> client_id = "your_client_id"
            >>> seller_token = "your_seller_token"
            >>> not_empty, stocks = await upload_stocks(watch_remnants, client_id, seller_token)
            not_empty
            stocks
    '''
    offer_ids = get_offer_ids(client_id, seller_token)
    stocks = create_stocks(watch_remnants, offer_ids)
    for some_stock in list(divide(stocks, 100)):
        update_stocks(some_stock, client_id, seller_token)
    not_empty = list(filter(lambda stock: (stock.get("stock") != 0), stocks))
    return not_empty, stocks


def main():
   ''' Основная функция для обновления цен и остатков товаров на маркетплейсе.

        Raises:
            requests.exceptions.ReadTimeout: Если превышено время ожидания запроса.
            requests.exceptions.ConnectionError: Если произошла ошибка соединения.
            Exception: Если произошла другая ошибка.

        Example:
             main()
    '''
    env = Env()
    seller_token = env.str("SELLER_TOKEN")
    client_id = env.str("CLIENT_ID")
    try:
        offer_ids = get_offer_ids(client_id, seller_token)
        watch_remnants = download_stock()
        # Обновить остатки
        stocks = create_stocks(watch_remnants, offer_ids)
        for some_stock in list(divide(stocks, 100)):
            update_stocks(some_stock, client_id, seller_token)
        # Поменять цены
        prices = create_prices(watch_remnants, offer_ids)
        for some_price in list(divide(prices, 900)):
            update_price(some_price, client_id, seller_token)
    except requests.exceptions.ReadTimeout:
        print("Превышено время ожидания...")
    except requests.exceptions.ConnectionError as error:
        print(error, "Ошибка соединения")
    except Exception as error:
        print(error, "ERROR_2")


if __name__ == "__main__":
    main()
