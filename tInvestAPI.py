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
        try:
            if nano < 0:
                nano = abs(nano)
            if nano == 0:
                return float(units)
            return units + nano * 10**-(floor(log10(nano))+1)
        except Exception as e:
            print(
                f"Падение в  'tinNumberConnector'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None

    # Получение всех опционов
    async def tinGetOptionsAll(self):
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                all_options = await client.instruments.options()
                return all_options.instruments
        except Exception as e:
            print(
                f"Падение в  'tinGetOptionsAll'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
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
                f"Падение в  'tinGetSharesAll'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
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
                f"Падение в  'tinGetCurrencyAll'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
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
                f"Падение в  'tinGetLastPrice'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None

    # Запрос истории свечей
    async def tinGetHistoryCandles(self, period, figi='FIGI', instrument_id='UID', slot='interval'):
        """
        FIGI - figi инструмента,
        UID - uid инструмента,
        slot - интервал, для унификации передаетсяя как значение из словаря,
        period - глубина запроса исторических свечей, для унификации задается в часах.
        """
        dict_slot = {
            '1_MIN': CandleInterval.CANDLE_INTERVAL_1_MIN,
            '5_MIN': CandleInterval.CANDLE_INTERVAL_5_MIN,
            '15_MIN': CandleInterval.CANDLE_INTERVAL_15_MIN,
            '1_HOUR': CandleInterval.CANDLE_INTERVAL_HOUR,
            '1_DAY': CandleInterval.CANDLE_INTERVAL_DAY,
            '2_MIN': CandleInterval.CANDLE_INTERVAL_2_MIN,
            '3_MIN': CandleInterval.CANDLE_INTERVAL_3_MIN,
            '10_MIN': CandleInterval.CANDLE_INTERVAL_10_MIN,
            '30_MIN': CandleInterval.CANDLE_INTERVAL_30_MIN,
            '2_HOUR': CandleInterval.CANDLE_INTERVAL_2_HOUR,
            '4_HOUR': CandleInterval.CANDLE_INTERVAL_4_HOUR,
            'WEEK': CandleInterval.CANDLE_INTERVAL_WEEK,
            'MONTH': CandleInterval.CANDLE_INTERVAL_MONTH,
        }
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                historical_candles = await client.market_data.get_candles(
                    figi=figi,
                    from_=now() - timedelta(hours=period),
                    to=now(),
                    interval=dict_slot[slot],
                    instrument_id=instrument_id,
                    candle_source_type=CandleSource.CANDLE_SOURCE_UNSPECIFIED
                )
                return historical_candles.candles
        except Exception as e:
            print(
                f"Падение в  'tinGetHistoryCandles'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None

    # Получение стакана по инструменту
    async def tinGetOrderBook(self, depth, figi='FIGI', instrument_id="UID"):
        try:
            async with AsyncClient(self.token,
                                   target=INVEST_GRPC_API_SANDBOX) as client:
                order_book = await client.market_data.get_order_book(
                    figi=figi, instrument_id=instrument_id, depth=depth
                )
                return order_book
        except Exception as e:
            print(
                f"Падение в  'tinGetOrderBook'\nТип исключения: {type(e).__name__}, сообщение: {str(e)}"
            )
            return None
