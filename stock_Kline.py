import requests
import json
import time
from multiprocessing import Pool

requests.packages.urllib3.disable_warnings()

query = {
    'resolution': 'D',
    'from': str(time.time()-23000000)[0:10],
    'to': str(time.time())[0:10]
}

getKlineHeader = {
    'accept': '*/*',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'referer': 'https://histock.tw/stock/tchart.aspx',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/85.0.4183.102 Safari/537.36'
}

getAllStockHeader = {
    'Host': 'www.cmoney.tw',
    'Accept': 'application/json, text/javascript, */*; q=0.01',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.106 Safari/537.36',
    'X-Requested-With': 'XMLHttpRequest',
    'Referer': '',
    'Accept-Encoding': 'gzip, deflate',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
    'Cookie': '',
    'Connection': 'keep-alive'
}

getallStockQuery = {
    'action': 'GetAllStockData',
    'cmkey': ''
}


def getCmKey():
    getAllStockHeader['Referer'] = 'https://www.cmoney.tw/finance/f00025.aspx?s=3515'
    url = "https://www.cmoney.tw/finance/f00025.aspx?s=3515"
    res = requests.get(url, verify=False)
    cmkey = str(res.text)
    # 獲取cmKey
    cmkey = cmkey[cmkey.find('<a href=\'/finance/f00025.aspx?s=3515\' cmkey=') +
                  45:cmkey.find('>個股概覽</a>  </li></ul> </li><li>技術分析')-1]
    getallStockQuery['cmkey'] = cmkey


def getAllStock(pool):
    print("取得所有股票代碼")
    urls = []
    getAllStockHeader['Referer'] = 'http://www.cmoney.tw/finance/f00025.aspx'
    r = requests.get('http://www.cmoney.tw/finance/ashx/mainpage.ashx',
                     params=getallStockQuery, headers=getAllStockHeader, verify=False)
    allStock = r.json()
    print("開始搜尋")
    for stock in allStock:
        if (stock['CommKey'].isdigit()):
            if (len(urls) < 10):
                urls.append(stock['CommKey'])
            else:
                pool.map(getKline, urls)
                urls = []

# 判斷紅黑K
def checkRedBlackK(data):
    # 紅K return true
    if (data['c'] > data['o']):
        return True
    return False

# 月線計算
def monthlyLine(data, day):
    total = 0
    for i in range(20) :
        total += data['c'][len(data['c'])-day-i]
    return total / 20

# 判斷上升趨勢
def checkUp(data, day):
    todayData = monthlyLine(data, day)
    threeDaysAgoData = monthlyLine(data, day+3)
    # 斜率（今天月線價格－三天前月線價格）÷ 三天前月線價格 > 2.3%
    if ((todayData-threeDaysAgoData)/threeDaysAgoData >= 0.023):
        return True
    return False

# 紅K吞噬黑k
def redEatBlack(id, data, day):
    lastKline = {}
    secLastKline = {}
    # 最後一條K
    lastKline['o'] = data['o'][len(data['o'])-day]
    lastKline['c'] = data['c'][len(data['c'])-day]
    lastKline['h'] = data['h'][len(data['h'])-day]
    lastKline['l'] = data['l'][len(data['l'])-day]
    lastKline['v'] = data['v'][len(data['v'])-day]
    # 倒數第二條K
    secLastKline['o'] = data['o'][len(data['o'])-day-1]
    secLastKline['c'] = data['c'][len(data['c'])-day-1]
    secLastKline['h'] = data['h'][len(data['h'])-day-1]
    secLastKline['l'] = data['l'][len(data['l'])-day-1]
    secLastKline['v'] = data['v'][len(data['v'])-day-1]
    if (checkRedBlackK(secLastKline) and not checkRedBlackK(lastKline) and secLastKline['o'] < lastKline['c']
            and secLastKline['c'] > lastKline['o'] and lastKline['v'] > 2000):
        print(id, lastKline, secLastKline)

# 流星(看跌)
def metor(id, data, day):
    # 規則:
    # 1.下影線幾乎沒有(<0.3%)
    # 2.實體k非常小，黑k(開盤價-收盤價)/開盤價<0.6%，紅k反之
    # 3.上影線大於實體k三倍以上
    # 基準K
    lastKline = {}
    lastKline['o'] = data['o'][len(data['o'])-day]
    lastKline['c'] = data['c'][len(data['c'])-day]
    lastKline['h'] = data['h'][len(data['h'])-day]
    lastKline['l'] = data['l'][len(data['l'])-day]
    lastKline['v'] = data['v'][len(data['v'])-day]
    # 量沒到就不考慮
    if (lastKline['v'] < 1000): return
    # 實體K高
    entityH = max(lastKline['o'],lastKline['c'])
    # 實體k低
    entityL = min(lastKline['o'],lastKline['c'])
    # 最高
    highest = lastKline['h']
    # 最低
    lowest = lastKline['l']
    if ( (entityL - lowest) / entityL < 0.003 and (entityH - entityL) / entityH < 0.006 and (highest - entityH) > ( entityH - entityL) * 3):
        print(id)

def getKline(id):
    query['symbol'] = id
    try:
        r = requests.get('https://histock.tw/Stock/tv/udf.asmx/history',
                         params=query, headers=getKlineHeader, verify=False)
        data = json.loads(r.text)
        # 當天 = 1，昨天 = 2...
        day = 1
        # [o]開、[h]高、[l]低、[c]收、[v]量
        if(data['s'] == 'ok' and len(data['o']) > 50 and checkUp(data, day)):
            redEatBlack(id, data, day)
    except Exception as e:
        print(id, data, e)


if __name__ == '__main__':
    pool = Pool()
    getCmKey()
    getAllStock(pool)
    pool.close()
    pool.join()
