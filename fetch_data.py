"""
CAN SLIM 한국주식 데이터 수집기
Yahoo Finance API를 사용하여 KOSPI/KOSDAQ 주요 종목 데이터를 수집합니다.
GitHub Actions에서 실행되거나 로컬에서 직접 실행 가능합니다.
"""

import json
import os
from datetime import datetime, timedelta

try:
    import yfinance as yf
    import numpy as np
    YFINANCE_OK = True
except ImportError:
    YFINANCE_OK = False
    print("yfinance 없음 - 샘플 데이터로 대체합니다")

# ─────────────────────────────────────────────
# 스캔할 종목 목록 (Yahoo Finance 심볼: 종목코드.KS or .KQ)
# ─────────────────────────────────────────────
STOCK_LIST = [
    # 반도체/전자
    {"ticker": "005930.KS", "code": "005930", "name": "삼성전자",     "sector": "반도체"},
    {"ticker": "000660.KS", "code": "000660", "name": "SK하이닉스",   "sector": "반도체"},
    {"ticker": "066570.KS", "code": "066570", "name": "LG전자",       "sector": "전자"},
    # 배터리/소재
    {"ticker": "373220.KS", "code": "373220", "name": "LG에너지솔루션","sector": "배터리"},
    {"ticker": "006400.KS", "code": "006400", "name": "삼성SDI",      "sector": "배터리"},
    {"ticker": "051910.KS", "code": "051910", "name": "LG화학",       "sector": "화학"},
    {"ticker": "247540.KQ", "code": "247540", "name": "에코프로비엠",  "sector": "2차전지소재"},
    # 바이오/제약
    {"ticker": "207940.KS", "code": "207940", "name": "삼성바이오로직스","sector": "바이오"},
    {"ticker": "068270.KS", "code": "068270", "name": "셀트리온",     "sector": "바이오"},
    # IT/인터넷
    {"ticker": "035420.KS", "code": "035420", "name": "NAVER",        "sector": "IT서비스"},
    {"ticker": "035720.KS", "code": "035720", "name": "카카오",       "sector": "IT서비스"},
    {"ticker": "323410.KS", "code": "323410", "name": "카카오뱅크",   "sector": "인터넷은행"},
    # 엔터/게임
    {"ticker": "259960.KS", "code": "259960", "name": "크래프톤",     "sector": "게임"},
    {"ticker": "041510.KQ", "code": "041510", "name": "에스엠",       "sector": "엔터"},
    {"ticker": "352820.KS", "code": "352820", "name": "하이브",       "sector": "엔터"},
    # 자동차
    {"ticker": "005380.KS", "code": "005380", "name": "현대차",       "sector": "자동차"},
    {"ticker": "012330.KS", "code": "012330", "name": "현대모비스",   "sector": "자동차부품"},
    # 지수/기타
    {"ticker": "028260.KS", "code": "028260", "name": "삼성물산",     "sector": "건설"},
    {"ticker": "003550.KS", "code": "003550", "name": "LG",           "sector": "지주사"},
    {"ticker": "005490.KS", "code": "005490", "name": "POSCO홀딩스",  "sector": "철강"},
]

# 시장 지수
INDEX_LIST = [
    {"ticker": "^KS11", "name": "KOSPI"},
    {"ticker": "^KQ11", "name": "KOSDAQ"},
]


# ─────────────────────────────────────────────
# CAN SLIM 점수 계산 함수들
# ─────────────────────────────────────────────

def calc_C_score(hist, financials):
    """C: 현재 분기 EPS 성장률 (25% 이상이면 고득점)"""
    try:
        eps_growth = financials.get("eps_growth_q", 0)
        if eps_growth >= 100: return 95, eps_growth
        if eps_growth >= 50:  return 85, eps_growth
        if eps_growth >= 25:  return 70, eps_growth
        if eps_growth >= 10:  return 45, eps_growth
        return 20, eps_growth
    except:
        return 50, 0

def calc_A_score(financials):
    """A: 연간 EPS 성장 추세"""
    try:
        eps_growth = financials.get("eps_growth_a", 0)
        if eps_growth >= 50:  return 90, eps_growth
        if eps_growth >= 25:  return 75, eps_growth
        if eps_growth >= 10:  return 55, eps_growth
        return 25, eps_growth
    except:
        return 50, 0

def calc_N_score(hist, info):
    """N: 52주 신고가 근접 여부"""
    try:
        high52 = info.get("fiftyTwoWeekHigh", 0)
        current = info.get("currentPrice", info.get("regularMarketPrice", 0))
        if high52 == 0 or current == 0:
            return 50, False
        ratio = current / high52
        near_high = ratio >= 0.95
        if ratio >= 0.98:  return 95, True
        if ratio >= 0.95:  return 80, True
        if ratio >= 0.85:  return 60, False
        return 30, False
    except:
        return 50, False

def calc_S_score(hist):
    """S: 거래량 급증 (공급/수요)"""
    try:
        if len(hist) < 20:
            return 50, 1.0
        recent_vol = hist["Volume"].iloc[-5:].mean()
        avg_vol    = hist["Volume"].iloc[-50:-5].mean()
        if avg_vol == 0:
            return 50, 1.0
        ratio = recent_vol / avg_vol
        if ratio >= 3.0:  return 95, round(ratio, 2)
        if ratio >= 2.0:  return 85, round(ratio, 2)
        if ratio >= 1.5:  return 70, round(ratio, 2)
        if ratio >= 1.0:  return 50, round(ratio, 2)
        return 25, round(ratio, 2)
    except:
        return 50, 1.0

def calc_L_score(hist, market_hist):
    """L: 상대강도(RS) — 시장 대비 종목 성과"""
    try:
        if len(hist) < 60 or len(market_hist) < 60:
            return 50, 50
        stock_ret  = (hist["Close"].iloc[-1] / hist["Close"].iloc[-60] - 1) * 100
        market_ret = (market_hist["Close"].iloc[-1] / market_hist["Close"].iloc[-60] - 1) * 100
        rs = stock_ret - market_ret
        if rs >= 30:   return 95, min(99, int(75 + rs * 0.5))
        if rs >= 15:   return 82, min(99, int(70 + rs * 0.6))
        if rs >= 5:    return 68, min(99, int(60 + rs * 0.8))
        if rs >= 0:    return 52, 55
        if rs >= -10:  return 35, 40
        return 15, 20
    except:
        return 50, 50

def calc_I_score(info):
    """I: 기관 매수 (보유 비율로 근사)"""
    try:
        inst_pct = info.get("heldPercentInstitutions", 0) * 100
        if inst_pct >= 50:  return 85
        if inst_pct >= 30:  return 70
        if inst_pct >= 15:  return 55
        return 35
    except:
        return 50

def calc_M_score(kospi_hist):
    """M: 시장 방향 — KOSPI 추세"""
    try:
        if len(kospi_hist) < 50:
            return 60, "중립"
        close = kospi_hist["Close"]
        ma20  = close.rolling(20).mean().iloc[-1]
        ma50  = close.rolling(50).mean().iloc[-1]
        last  = close.iloc[-1]

        if last > ma20 > ma50:
            # 최근 배분일 카운트 (하락 + 거래량 증가)
            recent = kospi_hist.iloc[-20:]
            dist_days = 0
            for i in range(1, len(recent)):
                if (recent["Close"].iloc[i] < recent["Close"].iloc[i-1] and
                    recent["Volume"].iloc[i] > recent["Volume"].iloc[i-1]):
                    dist_days += 1
            if dist_days <= 3:
                return 85, "상승장"
            return 65, "주의"
        elif last < ma20 < ma50:
            return 20, "하락장"
        return 50, "중립"
    except:
        return 60, "중립"

def calc_total_score(scores):
    weights = [20, 20, 15, 15, 10, 10, 10]
    total = sum((scores[i] / 100) * weights[i] for i in range(7))
    return round(total)

def get_grade(score):
    if score >= 85: return "A"
    if score >= 70: return "B"
    if score >= 55: return "C"
    return "D"

def get_tag(score, near_high, vol_ratio):
    if score >= 85 and near_high: return "buy"
    if score >= 70: return "watch"
    if near_high and vol_ratio >= 1.5: return "break"
    return "other"


# ─────────────────────────────────────────────
# 메인 수집 함수
# ─────────────────────────────────────────────

def fetch_real_data():
    """Yahoo Finance에서 실제 데이터 수집"""
    print("📡 Yahoo Finance 데이터 수집 시작...")

    end   = datetime.now()
    start = end - timedelta(days=365)

    # 시장 지수 수집
    print("  ▸ 시장 지수 수집 중...")
    kospi_hist  = yf.download("^KS11",  start=start, end=end, progress=False)
    kosdaq_hist = yf.download("^KQ11",  start=start, end=end, progress=False)

    # 시장 점수 계산
    m_score, market_phase = calc_M_score(kospi_hist)

    # 지수 데이터 정리
    def get_index_data(hist, name):
        if len(hist) < 2:
            return {"name": name, "val": 0, "chg": 0, "trend": []}
        last  = float(hist["Close"].iloc[-1])
        prev  = float(hist["Close"].iloc[-2])
        chg   = round((last / prev - 1) * 100, 2)
        trend = [round(float(v), 1) for v in hist["Close"].iloc[-20:].tolist()]
        return {"name": name, "val": round(last, 1), "chg": chg, "trend": trend}

    index_data = [
        get_index_data(kospi_hist,  "KOSPI"),
        get_index_data(kosdaq_hist, "KOSDAQ"),
    ]

    # 배분일 카운트
    dist_days = 0
    if len(kospi_hist) >= 20:
        recent = kospi_hist.iloc[-20:]
        for i in range(1, len(recent)):
            if (float(recent["Close"].iloc[i]) < float(recent["Close"].iloc[i-1]) and
                float(recent["Volume"].iloc[i]) > float(recent["Volume"].iloc[i-1])):
                dist_days += 1

    # 시장 요약
    market_summary = {
        "phase": market_phase,
        "dist_days": dist_days,
        "ftd": dist_days <= 3,
        "advice": "공격적 매수 가능" if market_phase == "상승장" else
                  "보수적 접근 권장" if market_phase == "하락장" else "선별적 매수",
    }

    # 종목별 수집
    stocks = []
    for item in STOCK_LIST:
        try:
            print(f"  ▸ {item['name']} ({item['ticker']}) 수집 중...")
            tk   = yf.Ticker(item["ticker"])
            hist = tk.history(period="1y")
            info = tk.info

            if len(hist) < 5:
                print(f"    ⚠ 데이터 부족, 건너뜀")
                continue

            # 기본 가격 정보
            current_price = float(hist["Close"].iloc[-1])
            prev_price    = float(hist["Close"].iloc[-2])
            chg_pct       = round((current_price / prev_price - 1) * 100, 2)

            # 재무 데이터 근사 (Yahoo Finance 무료 한계로 추정값 사용)
            pe  = info.get("trailingPE", 0) or 0
            eps = info.get("trailingEps", 0) or 0
            eps_fwd = info.get("forwardEps", 0) or 0
            eps_growth_q = round(((eps_fwd / eps) - 1) * 100) if eps and eps > 0 else 0
            eps_growth_a = round(info.get("earningsQuarterlyGrowth", 0) * 100) if info.get("earningsQuarterlyGrowth") else 0

            financials = {
                "eps_growth_q": max(0, min(200, eps_growth_q)),
                "eps_growth_a": max(0, min(200, eps_growth_a)),
            }

            # CAN SLIM 각 점수 계산
            c_score, eps_q = calc_C_score(hist, financials)
            a_score, eps_a = calc_A_score(financials)
            n_score, near_high = calc_N_score(hist, info)
            s_score, vol_ratio = calc_S_score(hist)
            l_score, rs        = calc_L_score(hist, kospi_hist)
            i_score            = calc_I_score(info)

            scores = [c_score, a_score, n_score, s_score, l_score, i_score, m_score]
            total  = calc_total_score(scores)
            grade  = get_grade(total)
            tag    = get_tag(total, near_high, vol_ratio)

            # 60일 주가 (차트용)
            price_history = [round(float(v), 0) for v in hist["Close"].iloc[-60:].tolist()]

            stocks.append({
                "ticker":    item["code"],
                "name":      item["name"],
                "sector":    item["sector"],
                "price":     round(current_price, 0),
                "chg":       chg_pct,
                "eps_q":     eps_q,
                "eps_a":     eps_a,
                "hi52":      near_high,
                "volRatio":  vol_ratio,
                "rs":        rs,
                "inst":      i_score >= 55,
                "scores":    scores,
                "score":     total,
                "grade":     grade,
                "tag":       tag,
                "price_history": price_history,
            })

        except Exception as e:
            print(f"    ❌ {item['name']} 오류: {e}")
            continue

    return stocks, index_data, market_summary


def generate_sample_data():
    """yfinance 없을 때 샘플 데이터 생성"""
    import random
    random.seed(42)

    sample_stocks = [
        {"ticker":"005930","name":"삼성전자","sector":"반도체","scores":[90,80,85,78,88,82,75],"price":78400,"chg":2.1,"eps_q":87,"eps_a":45,"hi52":True,"volRatio":2.1,"rs":88,"inst":True},
        {"ticker":"000660","name":"SK하이닉스","sector":"반도체","scores":[95,85,90,82,93,88,75],"price":192000,"chg":3.4,"eps_q":120,"eps_a":68,"hi52":True,"volRatio":1.9,"rs":93,"inst":True},
        {"ticker":"247540","name":"에코프로비엠","sector":"2차전지소재","scores":[98,96,98,95,97,95,75],"price":188500,"chg":5.8,"eps_q":145,"eps_a":110,"hi52":True,"volRatio":3.5,"rs":97,"inst":True},
        {"ticker":"259960","name":"크래프톤","sector":"게임","scores":[96,92,95,90,95,92,75],"price":295000,"chg":4.2,"eps_q":98,"eps_a":75,"hi52":True,"volRatio":2.8,"rs":95,"inst":True},
        {"ticker":"373220","name":"LG에너지솔루션","sector":"배터리","scores":[92,88,88,85,91,86,75],"price":378000,"chg":3.1,"eps_q":95,"eps_a":72,"hi52":True,"volRatio":2.3,"rs":91,"inst":True},
        {"ticker":"041510","name":"에스엠","sector":"엔터","scores":[90,88,90,85,90,88,75],"price":98200,"chg":3.5,"eps_q":88,"eps_a":65,"hi52":True,"volRatio":2.2,"rs":90,"inst":True},
        {"ticker":"006400","name":"삼성SDI","sector":"배터리","scores":[82,78,80,75,85,80,75],"price":412000,"chg":2.5,"eps_q":78,"eps_a":52,"hi52":True,"volRatio":1.7,"rs":85,"inst":True},
        {"ticker":"352820","name":"하이브","sector":"엔터","scores":[80,78,70,75,82,80,75],"price":248000,"chg":2.1,"eps_q":72,"eps_a":55,"hi52":False,"volRatio":1.5,"rs":82,"inst":True},
        {"ticker":"207940","name":"삼성바이오로직스","sector":"바이오","scores":[75,72,78,65,79,76,75],"price":968000,"chg":0.9,"eps_q":65,"eps_a":48,"hi52":True,"volRatio":1.3,"rs":79,"inst":True},
        {"ticker":"323410","name":"카카오뱅크","sector":"인터넷은행","scores":[74,70,62,72,78,74,75],"price":26850,"chg":2.8,"eps_q":62,"eps_a":44,"hi52":False,"volRatio":1.6,"rs":78,"inst":True},
        {"ticker":"051910","name":"LG화학","sector":"화학","scores":[70,65,55,68,74,72,75],"price":387000,"chg":1.8,"eps_q":56,"eps_a":38,"hi52":False,"volRatio":1.4,"rs":74,"inst":True},
        {"ticker":"005380","name":"현대차","sector":"자동차","scores":[65,60,52,60,72,68,75],"price":245000,"chg":1.5,"eps_q":44,"eps_a":32,"hi52":False,"volRatio":1.2,"rs":72,"inst":True},
        {"ticker":"035420","name":"NAVER","sector":"IT서비스","scores":[55,50,45,55,68,60,75],"price":198500,"chg":1.2,"eps_q":32,"eps_a":28,"hi52":False,"volRatio":1.1,"rs":68,"inst":True},
        {"ticker":"035720","name":"카카오","sector":"IT서비스","scores":[40,35,30,45,52,40,75],"price":42800,"chg":-0.7,"eps_q":15,"eps_a":12,"hi52":False,"volRatio":0.9,"rs":52,"inst":False},
        {"ticker":"068270","name":"셀트리온","sector":"바이오","scores":[35,32,28,40,45,38,75],"price":178500,"chg":-1.2,"eps_q":18,"eps_a":14,"hi52":False,"volRatio":0.8,"rs":45,"inst":False},
    ]

    import math
    stocks = []
    for s in sample_stocks:
        total = calc_total_score(s["scores"])
        base  = s["price"] * 0.82
        trend = total / 100 * 0.25
        price_history = [
            round(base * math.pow(1 + trend/60 + (random.random()-0.45)*0.02, i+1))
            for i in range(60)
        ]
        price_history[-1] = s["price"]

        stocks.append({
            **s,
            "score": total,
            "grade": get_grade(total),
            "tag":   get_tag(total, s["hi52"], s["volRatio"]),
            "price_history": price_history,
        })

    index_data = [
        {"name":"KOSPI",  "val":2687.4,"chg":1.24,"trend":[2580,2595,2612,2608,2631,2645,2659,2672,2680,2687]},
        {"name":"KOSDAQ", "val":856.3, "chg":2.18,"trend":[820,824,831,828,838,842,847,851,853,856]},
    ]
    market_summary = {
        "phase":"상승장","dist_days":0,"ftd":True,
        "advice":"공격적 매수 가능",
    }
    return stocks, index_data, market_summary


# ─────────────────────────────────────────────
# 실행 진입점
# ─────────────────────────────────────────────
if __name__ == "__main__":
    if YFINANCE_OK:
        stocks, index_data, market_summary = fetch_real_data()
    else:
        print("⚠ yfinance 미설치 — 샘플 데이터 사용")
        stocks, index_data, market_summary = generate_sample_data()

    # 점수 높은 순 정렬
    stocks.sort(key=lambda x: x["score"], reverse=True)

    # 통계
    up_count   = sum(1 for s in stocks if s["chg"] > 0)
    down_count = sum(1 for s in stocks if s["chg"] < 0)
    pass_count = sum(1 for s in stocks if s["score"] >= 70)

    output = {
        "updated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
        "updated_at_kst": (datetime.utcnow() + timedelta(hours=9)).strftime("%Y년 %m월 %d일 %H:%M"),
        "stocks":         stocks,
        "index":          index_data,
        "market":         market_summary,
        "stats": {
            "total":      len(stocks),
            "up":         up_count,
            "down":       down_count,
            "pass_count": pass_count,
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/stocks.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 완료! data/stocks.json 저장됨")
    print(f"   총 {len(stocks)}개 종목 | 통과 {pass_count}개 | 상승 {up_count} / 하락 {down_count}")
    print(f"   시장 국면: {market_summary['phase']}")
