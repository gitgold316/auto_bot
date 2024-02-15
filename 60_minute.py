import asyncio
import aiohttp
from datetime import datetime
from telegram import Bot
import logging

# Upbit API 키 설정
upbit_api_key = ""
upbit_api_secret = ""
upbit_headers = {
    'Authorization': f'Bearer {upbit_api_key}',
}

# 로깅 설정
logging.basicConfig(filename='telegram_bot.log', level=logging.INFO)


async def send_telegram_message(bot, chat_id, market, candle_date, interval_str, percentage_change, open_price2,
                                average_price, close_price2, volume_status, chart_url):
    message = (
        f"종목: {market}\n"
        f"날짜: {candle_date}\n"
        f"기준봉: {interval_str}({percentage_change:.2f}%)\n"
        f"시가: {open_price2} / 평균가: {average_price} / 종가: {close_price2}\n"
        f"기타: {volume_status}\n"
        f"차트 링크: {chart_url}\n"
    )

    # 텔레그램 봇 메시지 전송
    try:
        await bot.send_message(chat_id=chat_id, text=message)
        # 로깅
        logging.info(f"메시지 전송: {message}")
    except Exception as e:
        print(f"메시지 전송 중 에러 발생: {e}")
        # 로깅
        logging.error(f"메시지 전송 중 에러 발생: {e}")
        raise  # 예외를 다시 발생시켜서 중단을 확인하기 쉽게 합니다.


async def fetch_data(url, params):
    jwt_token = ""
    headers = {'Authorization': f'Bearer {jwt_token}'}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()  # HTTP 오류 발생시 예외 발생
            return await response.json()


async def main():
    # 봇 인스턴스 생성
    telegram_bot_token = ""
    chat_id = ""
    bot_instance = Bot(token=telegram_bot_token)

    # 기준봉 종류
    candle_intervals = ['minutes/60']

    # 모든 원화 시장의 티커 리스트 가져오기
    markets_url = 'https://api.upbit.com/v1/market/all'
    markets_params = {'isDetails': 'false'}
    # 대기 시간 추가 (예: 0.5초)
    await asyncio.sleep(0.5)

    try:
        markets_data = await fetch_data(markets_url, markets_params)

        krw_markets = [market['market'] for market in markets_data if market['market'].startswith('KRW')]

        for interval in candle_intervals:
            # 각 봉별로 조회
            endpoint = f'https://api.upbit.com/v1/candles/{interval}'

            # 각 티커별로 종가 조회
            for market in krw_markets:
                params = {
                    'market': market,
                    'count': 2  # 바로전 캔들 가져오기
                }
                data = await fetch_data(endpoint, params)

                if len(data) == 2:
                    pre_candle = data[0]
                    previous_candle = data[1]
                    # 변수에 시가값/종가값 저장
                    open_price = '{:.2f}'.format(float(str(previous_candle['opening_price'])))
                    close_price = '{:.2f}'.format(float(str(previous_candle['trade_price'])))
                    average_price = '{:,.2f}'.format((float(open_price) + float(close_price)) / 2)
                    open_price2 = '{:,.2f}'.format(float(str(previous_candle['opening_price'])))
                    close_price2 = '{:,.2f}'.format(float(str(previous_candle['trade_price'])))
                    await asyncio.sleep(0.5)
                    # 날짜
                    candle_date_iso = previous_candle['candle_date_time_kst']
                    candle_date = datetime.strptime(candle_date_iso, "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d / %H:%M:%S")

                    # 상승률 계산
                    percentage_change = ((previous_candle['trade_price'] - previous_candle['opening_price']) /
                                         previous_candle['opening_price']) * 100

                    if previous_candle['trade_price'] > pre_candle['trade_price'] and pre_candle[
                        'candle_acc_trade_volume'] > previous_candle['candle_acc_trade_volume'] / 2:
                        volume_status = "거래량주의"
                    else:
                        volume_status = ""

                    # 상승률이 8% 이상인 경우에만 출력
                    if percentage_change >= 8:
                        # 기준봉
                        interval_minutes = abs(
                            (datetime.strptime(previous_candle['candle_date_time_kst'], "%Y-%m-%dT%H:%M:%S") -
                             datetime.strptime(data[-2]['candle_date_time_kst'],
                                               "%Y-%m-%dT%H:%M:%S")).total_seconds() / 60)
                        # interval_str이 1440이면 '일봉'으로, 그렇지 않으면 분봉으로 설정
                        interval_str = '일봉' if interval_minutes == 1440 else f"{int(interval_minutes)}분봉"

                        # Upbit 차트 링크 생성
                        chart_url = f'https://www.upbit.com/exchange?code=CRIX.UPBIT.{market}&interval={interval}'

                        # 대기 시간 추가 (예: 0.5초)
                        await asyncio.sleep(0.5)

                        # 메시지 전송
                        await send_telegram_message(bot_instance, chat_id, market, candle_date, interval_str,
                                                    percentage_change, open_price2, average_price, close_price2,
                                                    volume_status, chart_url)
    except Exception as e:
        print(f"예외 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
