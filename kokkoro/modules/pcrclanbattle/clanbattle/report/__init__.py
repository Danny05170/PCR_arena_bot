'''
該插件由 HoshinoBot 群友提供
以下是作者相關信息：

倚欄待月——基礎代碼編寫
明見——背景圖片與字體提供
qq3193377836
魔法の書——增強顯示效果
'''

from io import BytesIO
import os
import math

import pandas as pd
import numpy as np
import datetime


import matplotlib.pyplot as plt

from PIL import Image, ImageFont, ImageDraw
from matplotlib import font_manager as fm

from .data_source import get_data, get_person, get_time


from kokkoro.common_interface import KokkoroBot, EventInterface
from kokkoro.service import Service
from kokkoro.util import FreqLimiter
from kokkoro import R
import kokkoro

from .. import sv
from ..battlemaster import BattleMaster

FONT_PATH = kokkoro.config.FONT_PATH["msyh"]

_time_limit = 30*60
_lmt = FreqLimiter(_time_limit)

b_constellations = ["摩羯","水瓶","雙魚","白羊","金牛","雙子","巨蟹","獅子","處女","天秤","天蠍","射手"] #國服的（預測）

background1 = R.img('priconne/公會離職報告模板.jpg')
background2 = R.img('priconne/公會本期報告模板.jpg')

REPORT_RESIGN = 0
REPORT_NORMAL = 1
REPORT_UNDECLARED = -1

sv = Service('clanbattle-report')

@sv.on_fullmatch(('離職報告', 'retire-report'))
async def send_resign_report(bot:KokkoroBot, event:EventInterface):
    uid = event.get_author_id()
    nickname = event.get_author().get_nick_name()
    gid = event.get_group_id()
    report = gen_report(gid, uid, nickname, type=REPORT_RESIGN)
    await bot.kkr_send(event, report)


@sv.on_fullmatch(('會戰報告', 'clanbattle-report'))
async def send_normal_report(bot:KokkoroBot, event:EventInterface):
    uid = event.get_author_id()
    nickname = event.get_author().get_nick_name()
    gid = event.get_group_id()
    report = gen_report(gid, uid, nickname, type=REPORT_NORMAL)
    await bot.kkr_send(event, report)

#@sv.on_fullmatch(('出刀時間統計','.出刀時間統計','.出刀時間統計'))


def add_text(img: Image,text:str,textsize:int,font=FONT_PATH,textfill='white',position:tuple=(0,0)):
    #textsize 文字大小
    #font 字體，默認微軟雅黑
    #textfill 文字顏色，默認白色
    #position 文字偏移（0,0）位置，圖片左上角為起點
    img_font = ImageFont.truetype(font=font,size=textsize)
    draw = ImageDraw.Draw(img)
    draw.text(xy=position,text=text,font=img_font,fill=textfill)
    return img

def gen_report(gid, uid, nickname, type=REPORT_UNDECLARED, kpi=False):

    if type not in (REPORT_RESIGN,REPORT_NORMAL):
        return "類型錯誤！"
    if not kpi:
        if not _lmt.check(uid):
            return f'每{math.ceil(_time_limit/60)}分鐘僅能生成一次報告'
        _lmt.start_cd(uid)

    year,month = get_ym()
    constellation = b_constellations[month-1]

    try:
        clanname, challenges = get_person(gid,uid,year,month)
    except Exception as e:
        return f"出現錯誤: {str(e)}\n請聯系開发組調教。"
    if challenges.shape[0] == 0:
        return "您沒有參加本次公會戰。請再接再厲！"

    total_chl = 0
    miss_chl = 0
    damage_to_boss: list = [0 for i in range(5)]
    times_to_boss: list = [0 for i in range(5)]
    truetimes_to_boss: list = [0 for i in range(5)]
    total_damage = 0

    for idx,chl in challenges.iterrows():
        total_damage += chl['dmg']
        times_to_boss[chl['boss']-1] += 1
        # FIXME: 目前版本離職報告直接忽略尾刀與補償刀的傷害，計算boss均傷時，僅計算普通刀
        if chl['flag'] == BattleMaster.NORM:
            damage_to_boss[chl['boss']-1] += chl['dmg']
            truetimes_to_boss[chl['boss']-1] += 1
        # 尾刀與補償刀僅計算一刀的刀數
        # 因此忽略尾刀即可
        if not BattleMaster.has_damage_kind_for(chl['flag'], BattleMaster.LAST):
            total_chl += 1
        if chl['dmg'] == 0:
        	miss_chl += 1

    avg_day_damage = int(total_damage/6)
    df=pd.DataFrame({'a':damage_to_boss,'b':truetimes_to_boss})
    result=(df.a/df.b).replace(np.inf,0).fillna(0)
    avg_boss_damage = list(result)
    if total_chl >= 18:
        disable_chl = 0
        attendance_rate = 100
    else:
        disable_chl = 18 - total_chl
        attendance_rate = round(total_chl/18*100,2)

    #日期轉字符串
    year=str(year)
    month=str(month)
    
    #設置中文字體
    plt.rcParams['font.family'] = ['Microsoft YaHei']
    x = [f'{x}王' for x in range(1,6)]
    y = times_to_boss
    plt.figure(figsize=(4.3,2.8))
    ax = plt.axes()

    #設置標簽大小
    plt.tick_params(labelsize=15)

    #設置y軸不顯示刻度
    plt.yticks([])

    #繪制刀數柱狀圖
    recs = ax.bar(x,y,width=0.618,color=['#fd7fb0','#ffeb6b','#7cc6f9','#9999ff','orange'],alpha=0.4)

    #刪除邊框
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #設置數量顯示
    for i in range(0,5):
        rec = recs[i]
        h = rec.get_height()
        plt.text(rec.get_x()+0.1, h, f'{int(times_to_boss[i])}刀',fontdict={"size":12})
    buf = BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=120)
    bar_img1 = Image.open(buf)
    #清空圖
    plt.clf()

    x = [f'{x}王' for x in range(1,6)]
    y = avg_boss_damage
    plt.figure(figsize=(4.3,2.8))
    ax = plt.axes()

    #設置標簽大小
    plt.tick_params(labelsize=15)

    #設置y軸不顯示刻度
    plt.yticks([])

    #繪制均傷柱狀圖
    recs = ax.bar(x,y,width=0.618,color=['#fd7fb0','#ffeb6b','#7cc6f9','#9999ff','orange'],alpha=0.4)

    #刪除邊框
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)

    #設置數量顯示
    for i in range(0,5):
        rec = recs[i]
        h = rec.get_height()
        plt.text(rec.get_x(), h, f'{int(avg_boss_damage[i]/10000)}萬',fontdict={"size":12})

    buf = BytesIO()
    plt.savefig(buf, format='png', transparent=True, dpi=120)
    bar_img2 = Image.open(buf)

    #將餅圖和柱狀圖粘貼到模板圖,mask參數控制alpha通道，括號的數值對是偏移的坐標
    current_folder = os.path.dirname(__file__)
    img = background1.open() if type==REPORT_RESIGN else background2.open()

    img.paste(bar_img1, (580,950), mask=bar_img1.split()[3])
    img.paste(bar_img2, (130,950), mask=bar_img2.split()[3])

    #添加文字到img
    row1 = f'''
    {total_chl}

    {disable_chl}

    {total_damage}
    '''
    row2 = f'''
    {attendance_rate}%

    {miss_chl}

    {avg_day_damage}
    '''
    
    add_text(img, row1, position=(400,620), textsize=35, textfill='black')
    add_text(img, row2, position=(850,620), textsize=35, textfill='black')
    add_text(img, year, position=(355,438), textsize=40, textfill='black')
    add_text(img, month, position=(565,438), textsize=40, textfill='black')
    add_text(img, constellation, position=(710,438), textsize=40, textfill='black')
    if len(clanname) <= 7:
        add_text(img, clanname, position=(300+(7-len(clanname))/2*40, 515), textsize=40, textfill='black')
    else:
        add_text(img, clanname, position=(300+(10-len(clanname))/2*30, 520), textsize=30, textfill='black')
    add_text(img, nickname, position=(280,365), textsize=35, textfill='white')
    
    plt.close('all')
    return img

async def send_time_dist(bot: KokkoroBot, event: EventInterface,uid=0):
    gid = event.get_group_id()
    year,month = get_ym()
  
    try:
        name,times = get_time(gid,year,month,uid)
    except Exception as e:
        await bot.kkr_send(event, f"出現錯誤: {str(e)}\n請聯系開发組調教。")
        return

    plt.rcParams['axes.unicode_minus']=False
    prop = fm.FontProperties(fname=FONT_PATH)
    prop.set_size('large')
    fig,ax = plt.subplots(figsize=(12,6),facecolor='white')
    ax.set_xlabel('時間',fontproperties=prop)
    ax.set_ylabel('刀數',fontproperties=prop)
    ax.set_title(f'{name}{year}年{month}月會戰出刀時間統計',fontproperties=prop)
    ax.set_xlim((0-0.5,24))
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    colors=(['#808080']*6)+(['#9bc5af']*6)+(['#c54731']*6)+(['#3a4a59']*6)
    plt.xticks(range(24),fontproperties=prop)
    plt.bar(range(24),times,color=colors)
    
    await bot.kkr_send(event, fig)
    plt.close()

def get_ym():
    now = datetime.datetime.now()
    year = now.year
    month = now.month
    day = now.day
    if day < 20:
        month -= 1
    if month == 0:
        year -= 1
        month = 12
    return year,month
