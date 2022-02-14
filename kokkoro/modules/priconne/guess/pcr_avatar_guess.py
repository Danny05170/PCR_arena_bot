import os, math, random

from kokkoro.service import Service
from kokkoro.common_interface import EventInterface, KokkoroBot
from kokkoro.modules.priconne import chara, _pcr_data

import kokkoro

from .guess_helper import WinnerJudger, WinningCounter


sv = Service('pcr-avatar-guess')

HINT_LIMIT = 3
PIC_SIDE_LENGTH = 25 
ONE_TURN_TIME = 20
DB_PATH = os.path.expanduser(f'~/.kokkoro/pcr_avatar_guess_winning_counter.db')
BLACKLIST_ID = [
    1000, # unknow chara
    1072, 1900, 1908, 1909, 1910, 1911, 1914, 1915, 1916, 1917, 1918, 1919, 1920, 
    4031, 9000, # npc
    9601, 9602, 9603, 9604, # horse
    ]



winner_judger = WinnerJudger()

@sv.on_fullmatch(('排行榜', '猜頭像群排行'))
async def description_guess_group_ranking(bot: KokkoroBot, ev: EventInterface):
    members = ev.get_members_in_group()
    print(members)
    card_winningcount_dict = {}
    winning_counter = WinningCounter(DB_PATH)
    print(winning_counter    )
    for member in members:
        print(  member  )
        if member.get_id() != ev.get_author_id():
            card_winningcount_dict[member.get_nick_name()] = winning_counter._get_winning_number(ev.get_group_id(), member.get_id())
    group_ranking = sorted(card_winningcount_dict.items(), key = lambda x:x[1], reverse = True)
    print( group_ranking  )
    msg = '猜頭像小遊戲此群排行為:\n'
    for i in range(min(len(group_ranking), 10)):
        if group_ranking[i][1] != 0:
            msg += f'第{i+1}名: {group_ranking[i][0]}, 猜對次數: {group_ranking[i][1]}次\n'
    await bot.kkr_send(ev, msg.strip())

group_hint_cnt = {}
@sv.on_fullmatch('猜頭像')
async def avatar_guess(bot: KokkoroBot, ev: EventInterface):
    try:
        gid = ev.get_group_id()
        if winner_judger.get_on_off_status(gid):
            await bot.kkr_send(ev, "此輪猜頭像還沒結束 0x0")
            return
                
        winner_judger.turn_on(gid)
        chara_id_list = list(_pcr_data.CHARA_NAME.keys())
        random.shuffle(chara_id_list)
        i = 0
        while chara_id_list[i] in BLACKLIST_ID:
            i += 1
        correct_id = chara_id_list[i]
        winner_judger.set_result(gid, correct_id)

        msg = f'猜猜這個圖片是哪位角色頭像的一部分?\n※發送"頭像提示"，可以得到更多信息~\n※回答時請加前綴 a\n※示例：a 可可蘿'
        await bot.kkr_send(ev, msg)
        
        group_hint_cnt[gid] = 0
        await hint(bot, ev)
        
    except Exception as e:
        winner_judger.turn_off(gid)
        raise e

@sv.on_fullmatch(('答案', 'avatar-answer'))
async def avatar_guess(bot: KokkoroBot, ev: EventInterface):   
    gid = ev.get_group_id()
    if winner_judger.get_on_off_status(gid):
        correct_id = winner_judger.get_result(gid)
        c = chara.fromid(correct_id)
        msg =  f'正確答案是: {c.name}\n很遺憾，沒有人答對~'
        await bot.kkr_send(ev, msg)
        await bot.kkr_send(ev, c.icon)

        winner_judger.turn_off(gid)
    # else:
    #     await bot.kkr_send(ev, "尚未開始猜頭像0x0")

@sv.on_fullmatch('提示')
async def hint(bot: KokkoroBot, ev: EventInterface):
    gid = ev.get_group_id()
    if not winner_judger.get_on_off_status(gid):
        await bot.kkr_send(ev, '尚未開始猜頭像0x0')
        return
    cnt = group_hint_cnt[gid]
    if cnt >= HINT_LIMIT:
        await bot.kkr_send(ev, '提示次數用完啦0x0\n輸入"頭像答案"查看答案')
        return

    correct_id = winner_judger.get_result(gid)
    c = chara.fromid(correct_id)
    img = c.icon.open()
    left = math.floor(random.random()*(129-PIC_SIDE_LENGTH))
    upper = math.floor(random.random()*(129-PIC_SIDE_LENGTH))
    cropped_img = img.crop((left, upper, left+PIC_SIDE_LENGTH, upper+PIC_SIDE_LENGTH))
        
    await bot.kkr_send(ev, f'提示{cnt+1}/{HINT_LIMIT}:')
    await bot.kkr_send(ev, cropped_img)
    group_hint_cnt[gid] += 1


@sv.on_prefix(('a'))
async def on_input_chara_name(bot: KokkoroBot, ev: EventInterface):
    gid = ev.get_group_id()
    uid = ev.get_author_id()
    if winner_judger.get_on_off_status(gid):
        s = ev.get_param().remain
        cid = chara.name2id(s)
        correct_id = winner_judger.get_result(gid)
        if cid != chara.UNKNOWN and cid == correct_id and winner_judger.get_winner(gid) == None:
            winner_judger.record_winner(gid, uid)
            winning_counter = WinningCounter(DB_PATH)
            winning_counter._record_winning(gid, uid)
            winning_count = winning_counter._get_winning_number(gid, uid)
            nick = ev.get_author().get_nick_name()
            msg_part = f'{nick}猜對了，真厲害！TA已經猜對{winning_count}次了~'
            c = chara.fromid(correct_id)
            msg =  f'正確答案是: {c.name}'
            await bot.kkr_send(ev, msg)
            await bot.kkr_send(ev, c.icon)
            await bot.kkr_send(ev, msg_part)

            winner_judger.turn_off(gid)