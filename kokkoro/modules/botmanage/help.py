import itertools

from kokkoro import priv
from kokkoro.service import Service
from kokkoro.common_interface import EventInterface
from kokkoro.util import join_iterable

sv = Service('_help_', manage_priv=priv.SUPERUSER, visible=False)

HELP_HEADER='''
=====================
- KokkoroBot使用說明 -
=====================
发送方括號[]內的關鍵詞即可觸发
※功能采取模塊化管理，管理員可控制開關
※部分未實裝功能以符號 ※ 開頭
'''.strip()

HELP_BOTTOM='''
※※KokkoroBot是基於HoshinoBot開发的跨平台bot
※※可以從github下載源碼自行搭建部署，歡迎star&pr
※※https://github.com/zzbslayer/KokkoroBot-Multi-Platform
'''.strip()

PRC_HELP = '''
==================
- 公主連結Re:Dive -
==================
-      娛樂      -
==================
[@bot 簽到] 給主さま蓋章章
[@bot 運勢] 預測今日運勢
[@bot 單抽] 單抽轉蛋模擬
[@bot 來发十連] 十連轉蛋模擬
[@bot 來一井] 4w5鉆！買定離手！
[查看卡池] 模擬卡池&出率
[切換卡池] 更換模擬卡池
[賽馬]蘭德索爾賽🐎大賽
[多人賽馬]多人蘭德索爾賽🐴大賽
[猜頭像] 猜猜庫唔似撒
[頭像答案] 公布猜頭像答案
[猜角色] 猜猜庫唔似撒
[角色答案] 公布猜角色答案
[切嚕一下] 後以空格隔開接想要轉換為切嚕語的話
[切嚕～♪切啰巴切拉切蹦切蹦] 切嚕語翻譯
[@bot 官漫132] 官方四格閱覽
[@bot 看微博 公主連結] 官方微博閱覽（僅限最近5條）
==================
-      查詢      -
==================
[怎麼拆 妹弓] 後以空格隔開接角色名，查詢競技場解法
[pcr/bcr速查] 常用網址/速查表
[rank表] 查看rank推薦表
[黃騎充電表] 查詢黃騎1動充電規律
[挖礦 15001] 查詢礦場中還剩多少鉆
[角色計算 2 100] 查詢角色升級所需的經驗藥水與mana
[國/日服日程表] 查看活動日程表
[國/台服新聞] 查看新聞
==================
-      推送      -
==================
[啟用/禁用 pcr-comic] 官方漫畫推送（日文）
[啟用/禁用 pcr-arena-reminder-utc9] 背刺時間提醒(日服)
[啟用/禁用 pcr-arena-reminder-utc8] 背刺時間提醒(國服台服)
[啟用/禁用 pcr-portion-reminder-utc9] 提醒買藥小助手(日服)
[啟用/禁用 pcr-portion-reminder-utc8] 提醒買藥小助手(國服台服)
[啟用/禁用 weibo-pcr] 國服官微推送
==================
-      會戰      -
==================
[！幫助] 查看會戰管理功能的說明
'''.strip()

ARKNIGHTS_HELP='''
=====================
- 明日方舟 Arknights -
=====================
[公開招募 位移 近戰位] 公開招募模擬器
[公招TAG] 公開招募TAG一覽
[啟用/禁用 weibo-ark] 國服官微推送
'''.strip()

PUSH_HELP='''
===========
- 推送服務 -
===========
[微博配置] 查看微博推送服務的配置
[@bot 看微博 公主連結 3] 根據別名閱覽指定賬戶最近的微博（僅限最近5條）
[pcr-comic get-bc-tag] 獲取推送服務的頻道標簽
[weibo-pcr set-bc-tag 國服推送] 設置推送服務的頻道標簽（管理員限定）
'''.strip()

NORMAL_HELP='''
===========
- 通用功能 -
===========
[啟用/禁用 antiqks] 識破騎空士的陰謀
※[啟用/禁用 bangumi] 開啟番劇更新推送
※[@bot 來點新番] 查看最近的更新(↑需開啟番劇更新推送↑)
※[倒放<gif圖片>] 倒放gif(需開啟gif-reverter)
※[搜無損 關鍵詞] 搜索無損acg音樂
[.r] 擲骰子
[.r 3d12] 擲3次12面骰子
[生成表情 <表情名> <文字>] 表情包生成器
[表情列表] 列出可生成的表情名稱
※[@bot 精致睡眠] 8小時精致睡眠(bot需具有群管理權限)
※[給我來一份精致昏睡下午茶套餐] 叫一杯先輩特調紅茶(bot需具有群管理權限)
'''.strip()

SHORT_HELP=f'''
{HELP_HEADER}
====================
[公主連結幫助]查看公主連結相關功能
[！幫助] 查看公主連結會戰管理功能的說明
[明日方舟幫助]查看明日方舟相關功能
[通用功能]查看通用功能
[推送幫助]查看推送服務
=====管理限定功能=====
[lssv] 查看功能模塊的開關狀態
[lsbcsv] 查看推送服務的開關狀態與標簽
[enable <服務名>] 開啟指定服務
[disable <服務名>] 關閉指定服務
====================
{HELP_BOTTOM}
'''.strip()

_pcr=['公主連結', '公主鏈接', '公主連接', 'pcr', 'bcr']
_help=['幫助', 'help']
@sv.on_fullmatch(join_iterable(_pcr, _help) + ('pcr-help', ))
async def pcr_help(bot, ev: EventInterface):
    await bot.kkr_send(ev, PRC_HELP)

_ark=['明日方舟', '舟遊', 'arknights']
@sv.on_fullmatch(tuple([''.join(l) for l in itertools.product(_ark, _help)]))
async def ark_help(bot, ev: EventInterface):
    await bot.kkr_send(ev, ARKNIGHTS_HELP)

_push=['推送', 'push']
@sv.on_fullmatch(tuple([''.join(l) for l in itertools.product(_push, _help)]))
async def push_help(bot, ev: EventInterface):
    await bot.kkr_send(ev, PUSH_HELP)

@sv.on_fullmatch(('通用功能', '通用幫助', 'general-help'))
async def normal_help(bot, ev: EventInterface):
    await bot.kkr_send(ev, NORMAL_HELP)

@sv.on_fullmatch(('幫助', 'help'))
async def send_help(bot, ev: EventInterface):
    await bot.kkr_send(ev, SHORT_HELP)
