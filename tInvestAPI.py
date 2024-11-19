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
    def format_T_num_in_float(self, units, nano):
        if nano < 0:
            nano = abs(nano)
        if nano == 0:
            return float(units)
        return units + nano * 10**-(floor(log10(nano))+1)

    # Получение всех опционов
    async def show_options(self):
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
