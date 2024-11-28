from datetime import timedelta, datetime
import time

from math import floor, log10

from tinkoff.invest import AsyncClient
from tinkoff.invest.constants import INVEST_GRPC_API_SANDBOX
from tinkoff.invest.schemas import (
    Deviation,
    GetTechAnalysisRequest,
    IndicatorInterval,
    CandleInterval,
    CandleSource,
    IndicatorType,
    Smoothing,
    TypeOfPrice,
)
from tinkoff.invest.utils import decimal_to_quotation, now

class TinvestAPI:
    def __init__(self, token):
        self.token = token

    # Пеобразование тин-чисел в флоат
    def tinNumberConnector(self, units, nano):
        if nano < 0:
            nano = abs(nano)
        if nano == 0:
            return float(units)
        return units + nano * 10**-(floor(log10(nano))+1)

    # Получение всех опционов
    async def tinGetOptionsAll(self):
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                all_options = await client.instruments.options()
                return all_options
        except Exception as e:
            print(
                f"Тип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None

    # Получение списка всех акций
    async def tinGetSharesAll(self):
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                exchange_shares_array = await client.instruments.shares()
                return exchange_shares_array.instruments
        except Exception as e:
            print(
                f"Тип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None

    # Получение всех валют
    async def tinGetCurrencyAll(self):
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                exchange_currency_array = await client.instruments.currencies()
                return exchange_currency_array.instruments
        except Exception as e:
            print(
                f"Тип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None

    # Получение последней цены по инструменту
    async def tinGetLastPrice(self, figi='FIGI', instrument_id="UID"):
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                last_prices_array = await client.market_data.get_last_prices(
                    figi={figi}, instrument_id={instrument_id}
                )
                return last_prices_array.last_prices
        except Exception as e:
            print(
                f"Тип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None
