from kokkoro.service import Service
from kokkoro import priv
from kokkoro.common_interface import KokkoroBot, EventInterface

sv = Service('kkr-status', use_priv=priv.NORMAL, manage_priv=priv.SUPERUSER, enable_on_default=True, visible=False)

@sv.on_fullmatch(('usage', '使用情況'), only_to_me=True)
async def broadcast(bot: KokkoroBot, ev: EventInterface):
    groups = bot.get_groups()
    num_g = len(groups)
    num_m = 0
    for g in groups:
        members = g.get_members()
        num_m = num_m + len(members)
    num_m = num_m - num_g
    msg = f'目前 KokkoroBot 正在為 {num_g} 個群組共 {num_m} 個用戶服務 0x0'
    await bot.kkr_send(ev, msg)