# 公主連接Re:Dive會戰管理插件
# clan == クラン == 戰隊（直譯為氏族）（CLANNAD的CLAN（笑））
from functools import wraps

from .argparse import ArgParser
from .exception import *

from kokkoro.typing import *
from kokkoro.common_interface import KokkoroBot, EventInterface
from kokkoro.service import Service
from kokkoro.util import join_iterable

sv = Service('clanbattle')
SORRY = 'ごめんなさい！嚶嚶嚶(〒︿〒)'

def cb_prefix(cmds):
    if isinstance(cmds, str):
        cmds = (cmds, )
    return join_iterable(('.', '.'), cmds)

def cb_cmd(prefixes, parser:ArgParser) -> Callable:
    prefixes = cb_prefix(prefixes)
    if not isinstance(prefixes, Iterable):
        raise ValueError('`name` of cb_cmd must be `str` or `Iterable[str]`')
    
    def deco(func):
        @wraps(func)
        async def wrapper(bot: KokkoroBot, ev: EventInterface):
            try:
                args = parser.parse(ev.get_param().args, ev)
            except ParseError as e:
                await bot.kkr_send(ev, e.message, at_sender=True)
                return
            try:
                return await func(bot, ev, args)
            except ClanBattleError as e:
                await bot.kkr_send(ev, e.message, at_sender=True)
            except Exception as e:
                await bot.kkr_send(ev, f'{SORRY} 发生未知錯誤', at_sender=True)
                raise e
        sv.on_prefix(prefixes)(wrapper)
        return wrapper
    return deco


from .cmdv2 import *

@sv.on_fullmatch(cb_prefix(('幫助', 'help')), only_to_me=False)
async def cb_help(bot: KokkoroBot, ev:EventInterface):
    QUICK_START1 = f'''
出刀指令教學
============================================================================
主要流程
 .預約(非必要)→ .1進場 → .2 回報 → .3/.4 出去
預約 
【.預約 周目 王】
.預約 12 2+4  (等於預約12周 2、4王的意思)
報名進場
【.1 刀種、傷害】
.1 新黑2000 *刀種、傷害中間不能有空格，不打也行
卡3秒暫停
【.2 回報傷害】
.2 3s2121 （不要謊報！準確到萬，有ub就說還有誰的ub，"跟傷害之間不能有空格"）
分數高的打完不領殘就 
【.3 實際打的傷害w】
.3 123w （一定要是數字，記得後面要加上w）
打完領殘就 
【.4 你得到的補償秒數、刀種  】
.4 27s新黑   一樣中間不能有空格
============================================================================
其它指令
【群初次使用】
.建會 N公會名 Stw
【公會成員】
.入會 祐樹
.入會 佐樹 (@id)
.退會  (@id)
.查看成員
.一鍵入會
.清空成員
【會戰進行時】
.刪刀 E1
.掛樹
【鎖定Boss】
.鎖定
.解鎖
【會戰信息查詢】
.進度
.查刀
.催刀
.出刀記錄 or .d (@id)
.查樹
【預約Boss】到該周該王會自動提醒
.預約 or .sub 周 Boss編號 (備註) (@id)
e.g .預約 20 3 物刀 (@id)
e.g .預約 20 1+3 物刀 (@id)  << 這個情況會同時預約20周 1+3 王
e.g .預約 20 1+3＋4＋5 物刀 (@id)  << 這個情況會同時預約20周 1，3，4，5 王
.取消預約 周 Boss號 (@id)
.查預約
.清空預約 (boss編號) 
e.g .清空預約 1 >>一王預約隊列已清空
e.g .清空預約  >>整個預約隊列已清空
【統計信息】
.分數統計
.傷害統計
'''

    QUICK_START2 = f'''
########## 新增 ##########
【算補償】
.算補償 50w 60w 1000W [第一刀傷害 第二刀傷害 王現在的血量] 計算合刀補償 (一定要有單位w)
.算補償 50w 60w [在裡面傷害 王現在的血量] 計算普通補償 (一定要有單位w)
.算全返 王剩血量 [計算需要幾多傷害才有全反]
【修改出刀記錄--幹部專用】
.修改 E030 D300000 R20 B2 F2 @id [E修改編數(根據.出刀記錄), D修改傷害 , R修改周目, B修改王, F修改備註,@修改出刀者]
備註 ： 0 = 通常, 1 = 尾刀 , 2 = 補時 , 3= 補時,尾刀 , 4= 掉線
【sl】
.SL (@id) (沒提供id 就當輸入指令的人)
.查SL
.刪SL (@id) (沒提供id 就當輸入指令的人)
【篩刀大會】
.進 (@id) [沒提供id 就當輸入指令的人]   
.查進 [篩刀]
.報 傷害卡xx秒 (@id) [先.進之後卡秒報傷害,沒提供id 就當輸入指令的人]
.退 (@id)  [中途退出篩刀大會, 沒提供id 就當輸入指令的人]    
.清 [篩刀大會表歸0 ，當王死後篩刀大會表會自動歸0 ,此指是給要中途清空篩刀大會表]
p.s 最後成功出了刀的人要輸入 .報刀 傷害值 或.出刀 傷害值 
【移軸】
.shift 補償時間(格式m:ss) 軸
軸的時間一定要最前 格式為m:ss 或 mss 都可
e.g 
.shift 0:57 118 搶新黑
111 搶新黑
110 搶似似花
109 搶泳媽、搶妹法、搶露娜
【補償刀】
.查補
.改補 秒數備註 
.刪補 (@id)
【作業】
.查角色 (返回根據練度表中的角色編數)
.作業 作業名 D4 角色號碼1[R14+,3星] 角色號碼2 角色號碼3 角色號碼4 角色號碼5 標準傷害
p.s 作業名一定要的 是自定義 例如酒鬼軸 
p.s 當中D4代表4階4王
p.s 要打詳細的資料一定要角色號碼[RXX,X星,xx專]這個格式 (可以只打星，專或R, 如果全部都打，一定要在[]內用','隔開)
.查作業
.刪作業 作業名
【查三刀組合】
.查組合 (@id) 
根據成員在練度表的輸入，只考慮他有否該角色和在不卡角的情況下，可以打出的組合
.查組合 y (@id) 
根據成員在練度表的輸入，考慮他有否該角色、rank、星數都滿足作業和在不卡角的情況下，可以打出的組合
【查刪刀】
.查刪刀 (@id)
'''    
    await bot.kkr_send(ev, QUICK_START1)
    await bot.kkr_send(ev, QUICK_START2, at_sender=True)
    # msg = MessageSegment.share(url='https://github.com/Ice-Cirno/HoshinoBot/blob/master/hoshino/modules/pcrclanbattle/clanbattle/README.md',
    #                            title='Hoshino會戰管理v2',
    #                            content='命令一覽表')
    # await session.send(msg)

from . import report