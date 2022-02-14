from kokkoro.service import BroadcastTag, BroadcastService
import requests
from datetime import datetime, timedelta
from kokkoro import aiorequests, R
from pandas.plotting import table
from matplotlib import pyplot as plt
import pandas as pd 

sv9 = BroadcastService('pcr-arena-reminder-utc9', 
    broadcast_tag=[BroadcastTag.cn_broadcast, BroadcastTag.tw_broadcast], enable_on_default=False, help_='背刺时间提醒(UTC+9)')

sv8 = BroadcastService('pcr-arena-reminder-utc8', 
    broadcast_tag=BroadcastTag.jp_broadcast, 
    enable_on_default=False, help_='背刺时间提醒(UTC+8)')

sv10 = BroadcastService('pcr-arena-reminder-utc10', 
    broadcast_tag=BroadcastTag.rank_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')    

sv11 = BroadcastService('pcr-arena-reminder-utc11', 
    broadcast_tag=BroadcastTag.rank_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')    

sv12 = BroadcastService('pcr-arena-reminder-utc12', 
    broadcast_tag=BroadcastTag.farm_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)') 

sv13 = BroadcastService('pcr-arena-reminder-utc13', 
    broadcast_tag=BroadcastTag.farm_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')     

sv14 = BroadcastService('pcr-arena-reminder-utc14', 
    broadcast_tag=BroadcastTag.farm_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')  

sv15 = BroadcastService('pcr-arena-reminder-utc15', 
    broadcast_tag=BroadcastTag.farm_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')  

sv16 = BroadcastService('pcr-arena-reminder-utc16', 
    broadcast_tag=BroadcastTag.farm_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')  

sv17 = BroadcastService('pcr-arena-reminder-utc17', 
    broadcast_tag=BroadcastTag.farm_broadcast, 
    enable_on_default=True, help_='背刺时间提醒(UTC+9)')                      

#sv14 = BroadcastService('pcr-arena-reminder-utc14', 
  #  broadcast_tag=BroadcastTag.drug_broadcast, 
  #  enable_on_default=True, help_='背刺时间提醒(UTC+9)')      

msg = '主人様、准备好背刺了吗？'

@sv8.scheduled_job('cron', hour='16', minute='17', misfire_grace_time=60*10)
async def pcr_reminder_utc8():
    await sv8.broadcast(msg)

@sv9.scheduled_job('cron', hour='16', minute='17', misfire_grace_time=60*10)
async def pcr_reminder_utc9():
    await sv9.broadcast(msg)

@sv10.scheduled_job('cron', hour='05', minute='15', misfire_grace_time=60*10)
async def pcr_reminder_utc10():
    def hour_rounder(t):
        if t.minute <= 30:
            return (t.replace(second=0, microsecond=0, minute=0, hour=t.hour))
        else:
            return (t.replace(second=0, microsecond=0, minute=30, hour=t.hour))
    url = 'https://api.infedg.xyz/search/rank'
    now = datetime.now()
    date_time = now.strftime("%Y%m%d")
    hour_round = hour_rounder(datetime.now())
    hour_round = hour_round.strftime("%H%M")
    fillname = "tw/4/" + date_time +hour_round
    params = {"filename": fillname,"search": "", "page": 0, "page_limit": 10}
    try:
        r = requests.post(url, json=params).json()['data']
        df = pd.DataFrame.from_dict(r).T
        # set fig size
        fig, ax = plt.subplots(figsize=(18, 3))
        # no axes
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        # no frame
        ax.set_frame_on(False)
        # plot table
        df.style.hide_index()
        tab = table(ax, df, loc="upper right",colLabels=df.keys())
        # set font manually
        tab.auto_set_font_size(True)
        ax.autoscale(enable=True) 
        plt.autoscale()
       # tab.set_fontsize(4)
        await sv10.broadcast(fig)
        plt.close()   
    except:
        await sv10.broadcast(f'https://kyaru.infedg.xyz/tw 沒有{date_time} {hour_round} 數據')         

@sv11.scheduled_job('cron', hour='05', minute='45', misfire_grace_time=60*10)
async def pcr_reminder_utc11():
    def hour_rounder(t):
        if t.minute <= 30:
            return (t.replace(second=0, microsecond=0, minute=0, hour=t.hour))
        else:
            return (t.replace(second=0, microsecond=0, minute=30, hour=t.hour))
    url = 'https://api.infedg.xyz/search/rank'
    now = datetime.now()
    date_time = now.strftime("%Y%m%d")
    hour_round = hour_rounder(datetime.now())
    hour_round = hour_round.strftime("%H%M")
    fillname = "tw/4/" + date_time +hour_round
    params = {"filename": fillname,"search": "", "page": 0, "page_limit": 10}
    try:
        r = requests.post(url, json=params).json()['data']
        df = pd.DataFrame.from_dict(r).T
        # set fig size
        fig, ax = plt.subplots(figsize=(18, 3))
        # no axes
        ax.xaxis.set_visible(False)
        ax.yaxis.set_visible(False)
        # no frame
        ax.set_frame_on(False)
        # plot table
        df.style.hide_index()
        tab = table(ax, df, loc="upper right",colLabels=df.keys())
        # set font manually
        tab.auto_set_font_size(True)
        ax.autoscale(enable=True) 
        plt.autoscale()
       # tab.set_fontsize(4)
        await sv11.broadcast(fig)
        plt.close()   
    except:
        await sv11.broadcast(f'https://kyaru.infedg.xyz/tw 沒有{date_time} {hour_round} 數據')      

### farm 
@sv12.scheduled_job('cron', hour='12', minute='00', misfire_grace_time=60*10)
async def pcr_reminder_utc12():
    msg="請記得裝備請求"
    await sv12.broadcast("<@&865579705977012234>"+"\n"+msg) 

@sv13.scheduled_job('cron', hour='20', minute='00', misfire_grace_time=60*10)
async def pcr_reminder_utc13():
    msg="請記得裝備請求"
    await sv13.broadcast("<@&865579705977012234>"+"\n"+msg) 
 
### drug 
@sv14.scheduled_job('cron', hour='06', minute='00', misfire_grace_time=60*10)
async def pcr_reminder_utc14():
    pic =  R.img('drug.jpg')
    await sv14.broadcast("<@&865580109251215361>"+"\n") 
    await sv14.broadcast(pic) 

@sv15.scheduled_job('cron', hour='12', minute='00', misfire_grace_time=60*10)
async def pcr_reminder_utc15():
    pic =  R.img('drug.jpg')
    await sv15.broadcast("<@&865580109251215361>"+"\n") 
    await sv15.broadcast(pic) 

@sv16.scheduled_job('cron', hour='18', minute='00', misfire_grace_time=60*10)
async def pcr_reminder_utc16():
    pic =  R.img('drug.jpg')
    await sv16.broadcast("<@&865580109251215361>"+"\n") 
    await sv16.broadcast(pic) 

@sv17.scheduled_job('cron', hour='00', minute='02', misfire_grace_time=60*10)
async def pcr_reminder_utc17():
    pic =  R.img('drug.jpg')
    await sv17.broadcast("<@&865580109251215361>"+"\n") 
    await sv17.broadcast(pic)        