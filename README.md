# 실행 방법
usage: price_alert.py [-h] [--percentage PERCENTAGE] [--intervals [INTERVALS ...]]

options:
  -h, --help            show this help message and exit
  --percentage PERCENTAGE
                        알림 기준 퍼센티지
  --intervals [INTERVALS ...]
                        기준봉 종류 리스트

## 실행 예시
```shell
python price_alert.py --percentage 8 --intervals 'minutes/240' 'minutes/30'
```

## interval 단위 crontab 실행 예시
"day" interval은 아직 미구현 상태이므로 추가 구현 필요!!

```shell
0 0 * * * python3 /var/autobot/price_alert.py --percentage 8 --intervals days/1
0 * * * * python3 /var/autobot/price_alert.py --percentage 4 --intervals minutes/60
0,30 * * * * python3 /var/autobot/price_alert.py --percentage 2 --intervals minutes/30
0 0,4,8,12,16,20 * * * python3 /var/autobot/price_alert.py --percentage 6 --intervals minutes/240
```