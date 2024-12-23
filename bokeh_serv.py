import os
import asyncio
from functools import partial

import pandas as pd

from dotenv import load_dotenv

from bokeh.io import show, curdoc
from bokeh.models import (
AutocompleteInput, Select, ColumnDataSource, DataTable, DateFormatter, TableColumn,
Div, DatePicker, HoverTool, Button
)
from bokeh.events import ButtonClick
from bokeh.layouts import column, row
from bokeh.document import without_document_lock
from bokeh.plotting import figure, curdoc

from tInvestAPI import TinvestAPI


# Токен санбокс т-инвестиции
load_dotenv()
TOKEN_TIN_SanBox = os.getenv("TOKEN_TIN_SanBox")
# Создание объекта для методов тинвест
tin = TinvestAPI(TOKEN_TIN_SanBox)

doc = curdoc()
# С темой для рабочего стола пока не понятно
doc.theme = 'dark_minimal'

df_all_options = pd.DataFrame()
df_all_share_curr = pd.DataFrame()

async def updateBD():
    # В отдельно добавленых тикерах глобалим 
    global df_all_options
    global df_all_share_curr
    print('Начинаю загрузку данных по опционам...')
    # Получение всех опционов и запись их в фрейм
    df_all_options = pd.DataFrame((await tin.tinGetOptionsAll()))
    # Фильтруем по дате(сегодня и на месяц вперед)
    df_all_options = df_all_options[(
        (df_all_options.expiration_date >= pd.to_datetime('today', utc=True))
        & (
            df_all_options.expiration_date <= pd.to_datetime('today', utc=True) + pd.to_timedelta(
                '32 days')
        )
    )]
    print('Загрузил опционы!')
    print('Начинаю загрузку данных по БА...')
    # Получение всех акций и валют и запись их в объединеный фрейм
    df_all_share_curr = pd.concat(
        [(pd.DataFrame(await tin.tinGetSharesAll())), pd.DataFrame(await tin.tinGetCurrencyAll())]
    )
    # Фильтруем по наличаю опционов по позиционному uid
    df_all_share_curr = df_all_share_curr[df_all_share_curr.ticker.isin(set(df_all_options['basic_asset']))]
    print('Загрузил БА!')
    source_BA_with_OPT = ColumnDataSource(df_all_share_curr)
    columns_BA_with_OPT = [
        TableColumn(field='name', title="Название",),
        TableColumn(field='ticker', title="Тикер"),
        TableColumn(field='lot', title="Лотность"),
    ]
    table_BA_with_OPT.source = source_BA_with_OPT
    table_BA_with_OPT.columns = columns_BA_with_OPT
    select_BA.options=list(df_all_share_curr.name)
    print('Всё ок!')
    
# Доп функции для обновления данных в виджетах*********************************************
# Обновление данных в таблице выбранной БА
async def updateTableSelectedBA(name_BA):
    df_for_selected_BA = pd.DataFrame(
        columns=['Название', 'Тикер', 'Цена за акцию', 'Лотность', 'Цена за лот', 'figi', 'uid']
    )
    for i in (df_all_share_curr[df_all_share_curr.name == name_BA]).iterrows():
        price_tin = await tin.tinGetLastPrice(figi=i[1].figi, instrument_id=i[1].uid)
        price = 'н/д'
        price_lot = 'н/д'
        if price_tin != None:
            price = tin.tinNumberConnector(price_tin[0].price.units, price_tin[0].price.nano)
            price_lot = price * i[1].lot
        df_for_selected_BA.loc[i[1].uid] = [
            i[1]['name'], i[1].ticker, price, i[1].lot, price_lot, i[1].figi, i[1].uid
        ]
        source_selected_BA = ColumnDataSource(df_for_selected_BA)
        columns_selected_BA = [
            TableColumn(field='Название', title="Название",),
            TableColumn(field='Тикер', title="Тикер"),
            TableColumn(field='Цена за акцию', title="Цена за акцию"),
            TableColumn(field='Лотность', title="Лотность"),
            TableColumn(field='Цена за лот', title="Цена за лот"),
        ]
        return [source_selected_BA, columns_selected_BA]
# Обновление данных в таблицах опционов на выбранную дату
async def updateTableAllOptDate(name_BA, date_Ex, direction):
    df_table_all_opt_date= pd.DataFrame(
        columns=[
            'Страйк', 'Премия', 'Цена БА', 'Опц. на деньгах', 'Откат премии'
        ]
    )
    # Фильтруем опционы по имени БА, дате исполнения и напрвлению
    for i in (
        df_all_options[
        (
            df_all_options.basic_asset_position_uid == (
                df_all_share_curr[df_all_share_curr.name == name_BA].position_uid.values[0]
            )
        )
        & (df_all_options.expiration_date == date_Ex) & (df_all_options.direction == direction)
        ]
    ).iterrows():
        strike = tin.tinNumberConnector(i[1].strike_price['units'], i[1].strike_price['nano'])
        ba_size = tin.tinNumberConnector(i[1].basic_asset_size['units'], i[1].basic_asset_size['nano'])
        price_BA = table_selected_BA.source.data['Цена за акцию'][0]
        price = 'н/д'
        quantity = 'н/д'
        money_option = 'н/д'
        bonus_rollback = 'н/д'
        order_book = await tin.tinGetOrderBook(depth=1, figi=i[1].uid, instrument_id=i[1].uid)
        if order_book != None:
            # Получение верхней цены в стакане опциона и количество предложений
            if order_book.asks:
                price = tin.tinNumberConnector(
                    order_book.asks[0].price.units, order_book.asks[0].price.nano
                )
                quantity = order_book.asks[0].quantity
                # Расчет "опциона на деньгах" и "отката премии"
                if direction == 2:
                    money_option = strike + price
                    bonus_rollback = price_BA - price
                else:
                    money_option = strike - price
                    bonus_rollback = price_BA + price
        df_table_all_opt_date.loc[i[1]['name']] = [
            strike, price, price_BA, money_option, bonus_rollback
        ]
    if direction == 2:
        source_table_all_opt_date = ColumnDataSource(
            df_table_all_opt_date.sort_values(by='Страйк')
        )
        # Обновление титла над таблицей CALL опционов выбранного БА
        if len(df_table_all_opt_date.loc[:]) == 0:
            title_selected_BA_CALL.text = (
                f'<blockquote><h2>CALL опционы не назначены!<hr>'
            )
        else:
            title_selected_BA_CALL.text = (
                f'<blockquote><h2>CALL опционы "{name_BA}" на {date_Ex:.10}<hr>'
            )
    else:
        source_table_all_opt_date = ColumnDataSource(
            df_table_all_opt_date.sort_values(by='Страйк', ascending=False)
        )
        # Обновление титла над таблицей CALL опционов выбранного БА
        if len(df_table_all_opt_date.loc[:]) == 0:
            title_selected_BA_PUT.text = (
                f'<blockquote><h2>PUT опционы не назначены!<hr>'
            )
        else:
            title_selected_BA_PUT.text = (
                f'<blockquote><h2>PUT опционы "{name_BA}" на {date_Ex:.10}<hr>'
            )
    columns_table_all_opt_date = [
        TableColumn(field='index', title="Название",),
        TableColumn(field='Страйк', title="Страйк"),
        TableColumn(field='Премия', title="Премия"),
        TableColumn(field='Цена БА', title="Цена БА"),
        TableColumn(field='Опц. на деньгах', title="Опц. на деньгах"),
        TableColumn(field='Откат премии', title="Откат премии"),
    ]
    return [source_table_all_opt_date, columns_table_all_opt_date]
# Обновление данных в таблицах выбранных опционов
async def updateTableSelectedOPT(name_OPT, date_Ex):
    df_for_OPT_select = pd.DataFrame(columns=['Данные',])
    # Фильтруем опцион по имени и дате исполнения
    for i in (
        df_all_options[
        (df_all_options.name == name_OPT) & (df_all_options.expiration_date == date_Ex)
        ]
    ).iterrows():
        strike = tin.tinNumberConnector(i[1].strike_price['units'], i[1].strike_price['nano'])
        ba_size = tin.tinNumberConnector(i[1].basic_asset_size['units'], i[1].basic_asset_size['nano'])
        order_book = await tin.tinGetOrderBook(depth=1, figi=i[1].uid, instrument_id=i[1].uid)
        price = 'н/д'
        quantity = 'н/д'
        direction = i[1].direction
        price_BA = 'н/д'
        if order_book != None:
            if order_book.asks:
                price = tin.tinNumberConnector(
                    order_book.asks[0].price.units, order_book.asks[0].price.nano
                )
                quantity = order_book.asks[0].quantity
        # Запрос цены основного БА
        for i1 in (df_all_share_curr[df_all_share_curr.name == select_BA.value]).iterrows():
            price_BA_type_tin = await tin.tinGetLastPrice(figi=i1[1].figi, instrument_id=i1[1].uid)
            if price_BA_type_tin != None:
                price_BA = tin.tinNumberConnector(
                    price_BA_type_tin[0].price.units, price_BA_type_tin[0].price.nano
                )
            lot_BA = i1[1].lot
    df_for_OPT_select.loc['Премия опциона(по стакану)'] = [price]
    df_for_OPT_select.loc['Стоимость БА'] = [price_BA]
    if (direction == 2 and price != 'н/д'):
        df_for_OPT_select.loc['Стоимость БА для опциона "На деньгах"'] = [(strike + price)]
        df_for_OPT_select.loc['Окупаемость опциона(шорт позиция БА)'] = [(price_BA - price)]
    elif (direction == 1 and price != 'н/д'):
        df_for_OPT_select.loc['Стоимость БА для опциона "На деньгах"'] = [(strike - price)]
        df_for_OPT_select.loc['Окупаемость опциона(лонг позиция БА)'] = [(price_BA + price)]
    else:
        df_for_OPT_select.loc['Стоимость БА для опциона "На деньгах"'] = ['н/д']
        df_for_OPT_select.loc['Стоимость БА для окупаемости премии'] = ['н/д']
    df_for_OPT_select.loc['Лотность опциона'] = [i[1].lot]
    df_for_OPT_select.loc['Лотность БА'] = [lot_BA]
    df_for_OPT_select.loc['Количество БА в опционе'] = [ba_size]
    df_for_OPT_select.loc['Соотношение лота БА к лоту опциона'] = [(lot_BA / ba_size)]
    if price != 'н/д':
        df_for_OPT_select.loc['Стоимость премии опциона за лот'] = [(price * ba_size)]
    else:
        df_for_OPT_select.loc['Стоимость премии опциона за лот'] = ['н/д']
    df_for_OPT_select.loc['Количество предложений(по стакану)'] = [quantity]
    df_for_OPT_select.loc['Дата исполнения опциона'] = [i[1].expiration_date]
    source_OPT_select = ColumnDataSource(df_for_OPT_select)
    columns_OPT_select = [
        TableColumn(field='index', title="Свойство",),
        TableColumn(field='Данные', title="Данные",),
    ]
    # Активация кнопкок построения графиков CALL и PUT опциона
    if btn_plotting_BA.disabled:
        if 'н/д' not in [price, quantity, price_BA]:
            if direction == 2:
                btn_plotting_CALL.disabled = False
                # Активация кнопки PUTvsCALL
                if not btn_plotting_PUT.disabled:
                    btn_plotting_PUTvsCALL.disabled = False              
            elif direction == 1:
                btn_plotting_PUT.disabled = False
                # Активация кнопки PUTvsCALL
                if not btn_plotting_CALL.disabled:
                    btn_plotting_PUTvsCALL.disabled = False        
    return [source_OPT_select, columns_OPT_select]
# Обновление данных графикова БА
async def updatePlottingBA():
    # Получение исторических свечей по БА
    candles = await tin.tinGetHistoryCandles(
        8760, figi=table_selected_BA.source.data['figi'][0],
        instrument_id=table_selected_BA.source.data['uid'][0],
        slot='1_DAY'
    )
    # Данные для графика БА
    source_plot_BA = ColumnDataSource(
        dict(
            x = [x.time for x in candles],
            y = [tin.tinNumberConnector(x.close.units, x.close.nano) for x in candles],
            volume = [x.volume for x in candles],   
        )
    )
    # Название для графика
    name_plot = table_selected_BA.source.data['Название'][0]
    return [source_plot_BA, name_plot]

# Корутины для вызова***************************************************************************
# Селекта выбора БА
async def coroutinSelectBA(name):
    # Обновление титла над таблицей БА
    title_selected_BA.text = f'<blockquote><h2>Данные Базового Актива - "{name}"<hr>'
    # Обновление таблицы выбранного БА
    data_table_selected_BA = await updateTableSelectedBA(name)
    table_selected_BA.source = data_table_selected_BA[0]
    table_selected_BA.columns = data_table_selected_BA[1]
    # Обновление таблицы CALL опционов выбранного БА на выбранную дату
    data_table_selected_BA_CALL = await updateTableAllOptDate(name, date_OPT_ex.value, 2)
    table_selected_BA_CALL.source = data_table_selected_BA_CALL[0]
    table_selected_BA_CALL.columns = data_table_selected_BA_CALL[1]
    # Обновление таблицы PUT опционов выбранного БА на выбранную дату
    data_table_selected_BA_PUT = await updateTableAllOptDate(name, date_OPT_ex.value, 1)
    table_selected_BA_PUT.source = data_table_selected_BA_PUT[0]
    table_selected_BA_PUT.columns = data_table_selected_BA_PUT[1]
    # Отключение в случае отсутствия опционов
    # И последующее добавление опционов в селекты выбора опционов
    if len(table_selected_BA_CALL.source.data['index']) == 0:
        select_CALL.disabled = True
    else:
        select_CALL.disabled = False
        select_CALL.options = list(table_selected_BA_CALL.source.data['index'])
    if len(table_selected_BA_PUT.source.data['index']) == 0:
        select_PUT.disabled = True
    else:
        select_PUT.disabled = False
        select_PUT.options = list(table_selected_BA_PUT.source.data['index'])
    # Обнуляем данные в таблице выбранных опционов
    table_CALL_select.source = ColumnDataSource(dict(nos = ['Список опционов обновлен!']))
    table_CALL_select.columns = [TableColumn(field='nos', title="a",)]
    table_PUT_select.source = ColumnDataSource(dict(nos = ['Список опционов обновлен!']))
    table_PUT_select.columns = [TableColumn(field='nos', title="a",)]
    # Активируем кнопку для построения графика БА и обнуляем данные этого графика
    plot_BA.data_source = ColumnDataSource({})
    btn_plotting_BA.disabled = False
    # Обнуляем данные графиков опционов и деактивируем их кнопки
    plot_CALL.data_source = ColumnDataSource({})
    plot_PUT.data_source = ColumnDataSource({})
    plot_PUTvsCALL.data_source = ColumnDataSource({})
    btn_plotting_PUT.disabled = True
    btn_plotting_CALL.disabled = True
    btn_plotting_PUTvsCALL.disabled = True
# Выбора даты испонения опциона
async def coroutinDateOptEx(date_Ex):
    # Обновление таблицы CALL опционов выбранного БА на выбранную дату
    data_table_selected_BA_CALL = await updateTableAllOptDate(select_BA.value, date_Ex, 2)
    table_selected_BA_CALL.source = data_table_selected_BA_CALL[0]
    table_selected_BA_CALL.columns = data_table_selected_BA_CALL[1]
    # Обновление таблицы PUT опционов выбранного БА на выбранную дату
    data_table_selected_BA_PUT = await updateTableAllOptDate(select_BA.value, date_Ex, 1)
    table_selected_BA_PUT.source = data_table_selected_BA_PUT[0]
    table_selected_BA_PUT.columns = data_table_selected_BA_PUT[1]
    # Отключение в случае отсутствия опционов
    # И последующее добавление опционов в селекты выбора опционов
    if len(table_selected_BA_CALL.source.data['index']) == 0:
        select_CALL.disabled = True
    else:
        select_CALL.disabled = False
        select_CALL.options = list(table_selected_BA_CALL.source.data['index'])
    if len(table_selected_BA_PUT.source.data['index']) == 0:
        select_PUT.disabled = True
    else:
        select_PUT.disabled = False
        select_PUT.options = list(table_selected_BA_PUT.source.data['index'])
    # Обнуляем данные в таблице выбранных опционов
    table_CALL_select.source = ColumnDataSource(dict(nos = ['Список опционов обновлен!']))
    table_CALL_select.columns = [TableColumn(field='nos', title="a",)]
    table_PUT_select.source = ColumnDataSource(dict(nos = ['Список опционов обновлен!']))
    table_PUT_select.columns = [TableColumn(field='nos', title="a",)]
# Селекта выбора CALL опциона
async def coroutinSelectCALL(name):
    # Обновление таблицы выбранного CALL опциона
    data_table_CALL_select = await updateTableSelectedOPT(name, date_OPT_ex.value)
    table_CALL_select.source = data_table_CALL_select[0]
    table_CALL_select.columns = data_table_CALL_select[1]
# Селекта выбора PUT опциона
async def coroutinSelectPUT(name):
    # Обновление таблицы выбранного PUT опциона
    data_table_PUT_select = await updateTableSelectedOPT(name, date_OPT_ex.value)
    table_PUT_select.source = data_table_PUT_select[0]
    table_PUT_select.columns = data_table_PUT_select[1]
# Кнопка построения графика БА
async def coroutinBtnPlottingBA():
    # Получение данных для графика
    source_plot_BA = await updatePlottingBA()
    # Обновление и построение графика БА
    plot_BA.data_source=source_plot_BA[0]
    # Добавляем чтоб в ховер подтягивались данные
    plot.line(source=ColumnDataSource())
    # Изменение названия
    plot.title.text = source_plot_BA[1]
    # Деактивируем кнопку построения графика БА до выбора следующего БА
    btn_plotting_BA.disabled = True
# Кнопки построения графиков опционов
async def coroutinBtnPlottingOPT(type_OPT):
    if type_OPT == 'CALL':
        plot_PUTvsCALL.data_source = ColumnDataSource({})
        plot_CALL.data_source = ColumnDataSource(
            dict(
                x = [
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                    table_CALL_select.source.data['Данные'][10],
                    table_CALL_select.source.data['Данные'][10],
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                ],
                y = [
                    table_CALL_select.source.data['Данные'][3],
                    table_CALL_select.source.data['Данные'][2],
                    table_CALL_select.source.data['Данные'][2],
                    table_CALL_select.source.data['Данные'][3],
                    table_CALL_select.source.data['Данные'][3],
                ],
                volume = [
                    select_CALL.value, select_CALL.value, select_CALL.value, select_CALL.value,
                    select_CALL.value
                ],
            )
        )
        plot.line(source=ColumnDataSource())
    elif type_OPT == 'PUT':
        plot_PUTvsCALL.data_source = ColumnDataSource({})
        plot_PUT.data_source = ColumnDataSource(
            dict(
                x = [
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                    table_PUT_select.source.data['Данные'][10],
                    table_PUT_select.source.data['Данные'][10],
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                ],
                y = [
                    table_PUT_select.source.data['Данные'][2],
                    table_PUT_select.source.data['Данные'][3],
                    table_PUT_select.source.data['Данные'][3],
                    table_PUT_select.source.data['Данные'][2],
                    table_PUT_select.source.data['Данные'][2],
                ],
                volume = [
                    select_PUT.value, select_PUT.value, select_PUT.value, select_PUT.value,
                    select_PUT.value
                ],
            )
        )
        plot.line(source=ColumnDataSource())
    elif type_OPT == 'PUTvsCALL':
        volic = (f'{select_PUT.value} vs {select_CALL.value}')
        plot_PUT.data_source = ColumnDataSource({})
        plot_CALL.data_source = ColumnDataSource({})
        plot_PUTvsCALL.data_source = ColumnDataSource(
            dict(
                x = [
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                    table_CALL_select.source.data['Данные'][10],
                    table_CALL_select.source.data['Данные'][10],
                    plot_BA.data_source.data['x'][len(plot_BA.data_source.data['x']) - 1],
                ],
                y = [
                    (table_PUT_select.source.data['Данные'][2] - table_CALL_select.source.data['Данные'][0]),
                    (table_CALL_select.source.data['Данные'][2] + table_PUT_select.source.data['Данные'][0]),
                    (table_CALL_select.source.data['Данные'][2] + table_PUT_select.source.data['Данные'][0]),
                    (table_PUT_select.source.data['Данные'][2] - table_CALL_select.source.data['Данные'][0]),
                    (table_PUT_select.source.data['Данные'][2] - table_CALL_select.source.data['Данные'][0]),
                ],
                volume = [volic, volic, volic, volic, volic]
                 )
        )
        plot.line(source=ColumnDataSource())

# Виджеты****************************************************************************************
# Название таблицы с опционами по которым есть опционы
title_table_all_BA = Div(
    text=(
        '<blockquote><h2>Таблица Базового Актива для которого назначены опционы<hr>'
    ), sizing_mode='stretch_width', margin = (3, 0, 3, 0)
)
# Таблица с данными БА по которым есть опционы
table_BA_with_OPT = DataTable(
    width_policy = 'max', index_header = '№', 
)
# Титл элементов выбора
title_selection_items = Div(
        text=(
            '<blockquote><h2>Выбор Базового Актива и даты исполнения опционов<hr>'
        ), sizing_mode='stretch_width', margin = (3, 0, 3, 0)
)
# Выбор БА
select_BA = Select(
        title="Выберите Базовый актив",
        sizing_mode='stretch_width', 
)
# Выбор даты исполнения опциона
date_OPT_ex = DatePicker(
        title="Выберите дату исполнения опционов",
        value=str(pd.to_datetime('today', utc=True)),
        min_date=str(pd.to_datetime('today', utc=True) - pd.to_timedelta('2 days')),
        max_date=str(pd.to_datetime('today', utc=True) + pd.to_timedelta('36 days')),
        sizing_mode='stretch_width'
)
# Титл таблицы выбранного БА
title_selected_BA = Div(
    text=(
        f'<blockquote><h2>Базовый Актив не выбран!<hr>'
    ),
    sizing_mode='stretch_width', margin = (3, 0, 3, 0)
)
# Таблица с данными БА
table_selected_BA = DataTable(
     sizing_mode='stretch_width', index_position = None, height=50
)
# Титл таблицы CALL опциона выбранного БА
title_selected_BA_CALL = Div(
    text=(f'<blockquote><h2>Базовый Актив не выбран!<hr>'),
    sizing_mode='stretch_width', margin = (3, 0, 3, 0)
)
# Таблица CALL опционнов выбранного БА на выбранную дату
table_selected_BA_CALL = DataTable(
    sizing_mode='stretch_width', index_header = '№', height = 250
)
# Титл таблицы PUT опциона выбранного БА
title_selected_BA_PUT = Div(
    text=(f'<blockquote><h2>Базовый Актив не выбран!<hr>'),
    sizing_mode='stretch_width', margin = (3, 0, 3, 0)
)
# Таблица PUT опционнов выбранного БА на выбранную дату
table_selected_BA_PUT = DataTable(
    sizing_mode='stretch_width', index_header = '№', height = 250
)
# Титл селектов для выбора PUT и CALL опциона
title_selection_OPTs = Div(
    text=f'<blockquote><h2>Выбор опционов<hr>', sizing_mode='stretch_width', margin = (3, 0, 3, 0)
)
# Селекты для выбора опционов
select_CALL = Select(
    title="Выберите CALL опцион", sizing_mode='stretch_width', disabled = True
)
select_PUT = Select(title="Выберите PUT опцион", sizing_mode='stretch_width', disabled = True)
# Таблица с данными CALL опциона
table_CALL_select = DataTable(
     sizing_mode='stretch_width', index_position = None, header_row = False, height = 250
)
# Таблица с данными PUT опциона
table_PUT_select = DataTable(
     sizing_mode='stretch_width', index_position = None, header_row = False, height = 250
)
# Кнопки построения графиков
btn_plotting_BA = Button(
    label='График БА', button_type="success", sizing_mode="stretch_width", disabled=True
)
btn_plotting_CALL = Button(
    label='График CALL', button_type="success", sizing_mode="stretch_width", disabled=True
)
btn_plotting_PUT = Button(
    label='График PUT', button_type="success", sizing_mode="stretch_width", disabled=True
)
btn_plotting_PUTvsCALL = Button(
    label='График PUTvsCALL', button_type="success", sizing_mode="stretch_width", disabled=True
)
# Кнопка сохранения данных по выстановленному опциону
btn_plotting_SAVE = Button(
    label='Сохраниить', button_type="success", sizing_mode="stretch_width", disabled=True
)
# Поле графика
# Панель инструментов
TOOLS = "pan,wheel_zoom,box_zoom,reset, crosshair"
# Данные для изображения в hover
data_in_hover = HoverTool(
    tooltips=[
        ( 'Дата',   '@x{%F}'),
        ( 'Цена',  '@y{%0.2f} руб' ),
        ('Объём', '@volume')
    ],
    formatters={
        '@x': 'datetime',
        '@y': 'printf',
        '@volume': 'printf',
    },
)
# Виджет графика
plot = figure(
    x_axis_type="datetime", sizing_mode="stretch_width", tools=[data_in_hover, TOOLS],
    title = 'Базовый Актив не выбран!'
)
# Экземпляр линейного графика для БА
plot_BA = plot.line(color="yellow", line_width=4,)
# Экземпляр графика CALL опциона
plot_CALL = plot.line(color='green', alpha=0.8, width=2)
# Экземпляр графика PUT опциона
plot_PUT = plot.line(color='red', alpha=0.8, width=2)
# Экземпляр графика PUTvsCALL опциона
plot_PUTvsCALL = plot.line(color='blue', alpha=0.8, width=2)

# Коллбэки****************************************************************************************
# Селекта выбора БА
def callbackSelectBA(attr, old, new):
    # Уведомление по обновлению данных выбранного БА
    title_selected_BA.text = (
        f'<blockquote><h2>Обновление данных Базового Актива - "{new}"...<hr>'
    )
    # Обновление титла для селектов выбора опционов
    title_selection_OPTs.text=(
        f'<blockquote><h2>Выбор опционов - "{new}" на {date_OPT_ex.value:.10}<hr>'
    )
    # Запуск котутины
    doc.add_next_tick_callback(partial(coroutinSelectBA, name=new))
# Выбора даты исполнения опциона
def callbackDateOptEx(attr, old, new):
    # Уведомление о поиске опционов
    title_selected_BA_CALL.text = (
        f'<blockquote><h2>Поиск CALL опционов на {new:.10}...<hr>'
    )
    title_selected_BA_PUT.text = (
        f'<blockquote><h2>Поиск PUT опционов на {new:.10}...<hr>'
    )
    # Обновление титла для селектов выбора опционов
    title_selection_OPTs.text=(
        f'<blockquote><h2>Выбор опционов - "{select_BA.value}" на {new:.10}<hr>'
    )
    # Запуск котутины
    doc.add_next_tick_callback(partial(coroutinDateOptEx, date_Ex=new))
# Выбора CALL опциона
def callbackSelectCALL(attr, old, new):
    doc.add_next_tick_callback(partial(coroutinSelectCALL, name=new))
# Выбора PUT опциона
def callbackSelectPUT(attr, old, new):
    doc.add_next_tick_callback(partial(coroutinSelectPUT, name=new))
# Кнопки построения графика БА
def callbackBtnPlottingBA():
        doc.add_next_tick_callback(partial(coroutinBtnPlottingBA))
# Кнопки построения графика CALL опциона
def callbackBtnPlottingCALL():
    doc.add_next_tick_callback(partial(coroutinBtnPlottingOPT, type_OPT = 'CALL'))
# Кнопки построения графика PUT опциона
def callbackBtnPlottingPUT():
    doc.add_next_tick_callback(partial(coroutinBtnPlottingOPT, type_OPT = 'PUT'))
# Кнопки построения графика PUTvsCALL опционов
def callbackBtnPlottingPUTvsCALL():
    doc.add_next_tick_callback(partial(coroutinBtnPlottingOPT, type_OPT = 'PUTvsCALL'))

# Обработчики событий**************************************************************************
# Селекта выбора БА
select_BA.on_change("value", callbackSelectBA)
# Выбора даты исполнения опциона
date_OPT_ex.on_change("value", callbackDateOptEx)
# Выбора CALL опциона
select_CALL.on_change("value", callbackSelectCALL)
# Выбора PUT опциона
select_PUT.on_change("value", callbackSelectPUT)
# Кнопка построения графика БА
btn_plotting_BA.on_click(callbackBtnPlottingBA)
# Кнопка построения графика CALL опциона
btn_plotting_CALL.on_click(callbackBtnPlottingCALL)
# Кнопка построения графика PUT опциона
btn_plotting_PUT.on_click(callbackBtnPlottingPUT)
# Кнопка построения графика PUTvsCALL опционов
btn_plotting_PUTvsCALL.on_click(callbackBtnPlottingPUTvsCALL)

# Собираем виджеты в корневище*************************************************************
layout = column(
    title_table_all_BA, table_BA_with_OPT,
    row(select_BA, date_OPT_ex, sizing_mode='stretch_width'),
    title_selected_BA, table_selected_BA, title_selected_BA_CALL, table_selected_BA_CALL,
    title_selected_BA_PUT, table_selected_BA_PUT, title_selection_OPTs,
    row(select_CALL, select_PUT, sizing_mode='stretch_width'),
    row(table_CALL_select, table_PUT_select, sizing_mode='stretch_width'),
    row(
        btn_plotting_BA, btn_plotting_CALL, btn_plotting_PUT,
        btn_plotting_PUTvsCALL, btn_plotting_SAVE, sizing_mode="stretch_width"
    ),
    plot,
    sizing_mode='stretch_width'
)

# Запустим один раз для подключени таблиц
doc.add_next_tick_callback(partial(updateBD))

doc.add_root(layout)