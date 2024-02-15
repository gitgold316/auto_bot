import asyncio
import aiohttp
from datetime import datetime, timedelta
from telegram import Bot
import logging
import traceback
from typing import List
import argparse


# 로깅 설정
logging.basicConfig(filename='telegram_bot.log', level=logging.INFO)
logger = logging.getLogger(__name__)

# 서버 deny 방지를 위한 호출 interval
sleep_interval = 0.6

# 봇 인스턴스 생성
telegram_bot_token = ""
chat_id = ""
bot_instance = Bot(token=telegram_bot_token)

kst_offset = timedelta(hours=9)

# 알림 메시지 발송 기준 상승률
noti_percentage = 8.0


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
        logger.info(f"메시지 전송: {message}")
    except Exception as e:
        # 로깅 <- 에러 로그를 남길 땐 traceback을 사용해야 trace가 출력 되어 디버깅이 가능
        # <- raise 상황에서 특별하게 예외에 대한 추가 정보를 남길 것이 없을 때는 여기서 로그를 남기지 않는 것이 좋음 (남긴다면 현재 파라미터 정보를 남길것)
        # logger.error(f"메시지 전송 중 에러 발생", traceback.format_exc())
        raise e  # 예외를 다시 발생시켜서 중단을 확인하기 쉽게 합니다. <- 예외를


async def fetch_data(url, params):
    jwt_token = ""
    # headers = {'Authorization': f'Bearer {jwt_token}'}
    # 인증 토큰을 설정하지 않아도 호출 가능함
    headers = {}

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, params=params) as response:
            response.raise_for_status()  # HTTP 오류 발생시 예외 발생
            return await response.json()


async def compute_data(current_data, data, market, interval: str):
    pre_candle = current_data[0]
    previous_candle = data[0]
    # 변수에 시가값/종가값 저장
    open_price = '{:.2f}'.format(float(str(previous_candle['opening_price'])))
    close_price = '{:.2f}'.format(float(str(previous_candle['trade_price'])))
    average_price = '{:,.2f}'.format((float(open_price) + float(close_price)) / 2)
    open_price2 = '{:,.2f}'.format(float(str(previous_candle['opening_price'])))
    close_price2 = '{:,.2f}'.format(float(str(previous_candle['trade_price'])))
    # await asyncio.sleep(0.5)
    # 날짜
    candle_date_iso = previous_candle['candle_date_time_kst']
    candle_date = datetime.strptime(candle_date_iso, "%Y-%m-%dT%H:%M:%S")
    current_date = datetime.utcnow() + kst_offset

    # interval 단위와 숫자를 분리하여 사용
    splt = interval.split("/")
    interval_minutes = 0

    if splt[0] == 'minutes':
        interval_minutes = int(splt[1])

        # candle_date 가 현재 시간에서 interval time의 2배 보다 작다면 API의 데이터가 최신 데이터가 아님
        if candle_date < current_date - timedelta(minutes=int(splt[1])*2):
            logger.debug("최신 데이터 미갱신 - gap : [%s]", (current_date - timedelta(minutes=int(splt[1])*2))-candle_date)
            logger.debug("current : [%s], before : [%s]", current_date, candle_date)
            logger.debug(pre_candle)
            logger.debug(previous_candle)
            return False
    else:
        # interval 단위 추가 시 추가 구현 필요
        raise Exception("Not implemented yet.")

    # 상승률 계산
    percentage_change = ((previous_candle['trade_price'] - previous_candle['opening_price']) /
                         previous_candle['opening_price']) * 100

    if previous_candle['trade_price'] > pre_candle['trade_price'] and pre_candle[
        'candle_acc_trade_volume'] > previous_candle['candle_acc_trade_volume'] / 2:
        volume_status = "거래량주의"
    else:
        volume_status = ""

    logger.debug("상승률 : %f%%, 기준 상승률 : %f%%, 출력 여부 : %s", percentage_change, noti_percentage, (percentage_change >= noti_percentage))

    # 상승률이 기준 상승률 이상인 경우에만 출력
    if percentage_change >= noti_percentage:
        # interval_str이 1440이면 '일봉'으로, 그렇지 않으면 분봉으로 설정
        interval_str = '일봉' if interval_minutes == 1440 else f"{interval_minutes}분봉"

        # Upbit 차트 링크 생성
        chart_url = f'https://www.upbit.com/exchange?code=CRIX.UPBIT.{market}&interval={interval}'

        # 대기 시간 추가 (예: 0.5초)
        # await asyncio.sleep(0.5)

        # 메시지 전송
        await send_telegram_message(bot_instance, chat_id, market, candle_date.strftime("%Y-%m-%d / %H:%M:%S"), interval_str,
                                    percentage_change, open_price2, average_price, close_price2,
                                    volume_status, chart_url)

    return True


async def execute_market(endpoint, market, interval, idx):
    # 1분 retry 대기
    retry_interval = 60.0 * 1
    # 최대 재시도 횟수
    max_retry_cnt = 10
    # 현재 시도 횟수
    count = 0
    # 처리 상태
    status = False

    # 처리 상태가 False 이고 현재 시도 횟수가 최대 재시도 횟수 미만이면 계속 반복 (retry) -> 처리가 잘 되면 바로 탈출
    # -> 재처리 시에는 예상치 못한 버그로 무한 재시도를 방지하기 위해 반드시 최대 횟수를 제한하는 것이 좋음
    while not status and count < max_retry_cnt:
        # Server의 429 오류 방지를 위한 랜덤 delay
        await asyncio.sleep(sleep_interval*idx)

        params = {
            'market': market,
            'count': 1  # 바로전 캔들 가져오기
        }

        # 현재 시간(1분 전) 데이터 조회
        current_data = await fetch_data('https://api.upbit.com/v1/candles/minutes/1', params)

        # interval 기준 이전 데이터 조회 (1건)
        data = await fetch_data(endpoint, params)

        logger.debug("each market current : [%s], before %s : [%s]", current_data, interval, data)

        # 데이터가 모두 조회 되었는지 상태 확인
        status = current_data and data

        # 데이터가 모두 조회 되었으면 처리 시도
        if status:
            # 처리 시도 & 처리 결과 반환
            status = await compute_data(current_data, data, market, interval)

        # 처리가 완료되지 못했을 경우
        if not status:
            # 시도 횟수 증가
            count += 1

            # 재시도를 위해 일정 시간 대기
            await asyncio.sleep(retry_interval)


async def execute_interval(interval, krw_markets):
    # 각 봉별로 조회
    endpoint = f'https://api.upbit.com/v1/candles/{interval}'

    # 각 티커별로 종가 조회 <- 한 건씩 처리가 blocking 되지 않도록 병렬 처리 (하지만 API 서버의 일정 시간 내 호출 횟수 제한으로 인해 병렬 처리 지연이 필요함 : http status 429 발생)
    tasks: List = [execute_market(endpoint, market, interval, idx/2) for idx, market in enumerate(krw_markets)]

    await asyncio.gather(*tasks)


async def main():
    # CLI program argument 처리
    parser = argparse.ArgumentParser()

    parser.add_argument("--percentage", help="알림 기준 퍼센티지", default=8)
    parser.add_argument("--intervals", nargs="*", help="기준봉 종류 리스트", default=['minutes/240'])

    args = parser.parse_args()

    # 기준봉 종류
    candle_intervals = args.intervals

    global noti_percentage
    noti_percentage = float(args.percentage)

    logger.debug("candle_intervals : [%s]", candle_intervals)
    logger.debug("noti_percentage : [%s%%]", noti_percentage)

    # 모든 원화 시장의 티커 리스트 가져오기
    markets_url = 'https://api.upbit.com/v1/market/all'
    markets_params = {'isDetails': 'false'}
    # 대기 시간 추가 (예: 0.5초
    # await asyncio.sleep(0.5)

    try:
        markets_data = await fetch_data(markets_url, markets_params)

        logger.debug("markets_data : [%s]", markets_data)

        krw_markets = [market['market'] for market in markets_data if market['market'].startswith('KRW')]

        # interval이 여러개인 경우 병렬 처리
        tasks: List = [asyncio.ensure_future(execute_interval(interval, krw_markets)) for interval in candle_intervals]

        await asyncio.gather(*tasks)

    except Exception as e:
        logger.error(traceback.format_exc())
        print(f"예외 발생: {e}")


if __name__ == "__main__":
    asyncio.run(main())
