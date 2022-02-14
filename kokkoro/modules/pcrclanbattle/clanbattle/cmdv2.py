"""
PCR會戰管理命令 v2

猴子也會用的會戰管理

命令設計遵循以下原則：
- 中文：降低學習成本
- 唯一：There should be one-- and preferably only one --obvious way to do it.
- 耐草：參數不規範時盡量執行
"""
import math
import kokkoro
import os
import re
from discord.ext.commands import MemberConverter
import discord
from datetime import datetime, timedelta
from typing import List
from matplotlib import pyplot as plt
import httpx
import json
from collections import defaultdict
import pandas as pd 
from itertools import combinations
import itertools
import urllib
import copy
import shutil
import requests
from pandas.plotting import table
from .battlemaster import BattleMaster
from .exception import *
from matplotlib import font_manager as fm
import inspect

from .argparse import ArgParser, ArgHolder, ParseResult
from .argparse.argtype import *

from . import sv, cb_cmd, cb_prefix
from kokkoro.modules.pcrclanbattle.clanbattle.report.data_source import get_data, get_person, get_time

from kokkoro.service import Service
from kokkoro.common_interface import KokkoroBot, EventInterface
from kokkoro import priv, R, util, config

plt.style.use('seaborn-pastel')
plt.rcParams['font.family'] = ['DejaVuSans', 'Microsoft YaHei', 'SimSun', ]

USAGE_ADD_CLAN = '.建會 N公會名 S服務器代號'
USAGE_ADD_MEMBER = '.入會 昵稱 (@id)'
USAGE_LIST_MEMBER = '.查看成員'

USAGE_TIP = '\n\n※無需輸入尖括號，圓括號內為可選參數'

ERROR_CLAN_NOTFOUND = f'公會未初始化：請*群管理*使用【{USAGE_ADD_CLAN}】進行初始化{USAGE_TIP}'
ERROR_ZERO_MEMBER = f'公會內無成員：使用【{USAGE_ADD_MEMBER}】以添加{USAGE_TIP}'
ERROR_MEMBER_NOTFOUND = f'未找到成員：請使用【{USAGE_ADD_MEMBER}】加入公會{USAGE_TIP}'
ERROR_PERMISSION_DENIED = '權限不足：需*群管理*以上權限'

def _check_clan(bm:BattleMaster):
    clan = bm.get_clan(1)
    if not clan:
        raise NotFoundError(ERROR_CLAN_NOTFOUND)
    return clan

def _check_member(bm:BattleMaster, uid:str, alt:str, tip=None):
    mem = bm.get_member(uid, alt) or bm.get_member(uid, 0) # 兼容cmdv1
    if not mem:
        raise NotFoundError(tip or ERROR_MEMBER_NOTFOUND)
    return mem

def _check_admin(ev:EventInterface, tip:str='') -> bool:
    if not priv.check_priv(ev.get_author(), priv.ADMIN):
        raise PermissionDeniedError(ERROR_PERMISSION_DENIED + tip)


@cb_cmd(('建會', '建会'), ArgParser(usage=USAGE_ADD_CLAN, arg_dict={
        'N': ArgHolder(tip='公會名'),
        'S': ArgHolder(tip='服務器地區', type=server_code)}))
async def add_clan(bot: KokkoroBot, ev: EventInterface, args:ParseResult):
    _check_admin(ev)
    bm = BattleMaster(ev.get_group_id())
    if bm.has_clan(1):
        bm.mod_clan(1, args.N, args.S)
        await bot.kkr_send(ev, f'公會信息已修改！\n{args.N} {server_name(args.S)}', at_sender=True)
    else:
        bm.add_clan(1, args.N, args.S)
        await bot.kkr_send(ev, f'公會建立成功！{args.N} {server_name(args.S)}', at_sender=True)

    

@cb_cmd(('查看公會', '查看公会'), ArgParser('.查看公會'))
async def list_clan(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clans = bm.list_clan()
    if len(clans):
        clans = map(lambda x: f"{x['cid']}會：{x['name']} {server_name(x['server'])}", clans)
        msg = ['本群公會：', *clans]
        await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
    else:
        raise NotFoundError(ERROR_CLAN_NOTFOUND)


@cb_cmd(('入會', '入会'), ArgParser(usage=USAGE_ADD_MEMBER, arg_dict={
        '': ArgHolder(tip='昵稱', default=''),
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def add_member(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)

    uid = args['@'] or args.uid 
    name = args[''] or args.name 
    author = ev.get_author()
    
    if uid == None:
        uid = ev.get_author_id()
    else:
        if uid != ev.get_author_id():
            _check_admin(ev, '才能添加其他人')
          #  if not ev.whether_user_in_group(uid):
            #   raise NotFoundError(f'Error: 無法獲取該群員信息，請檢查{uid}是否屬於本群')
        ## if we can't get name from mentions
        # if not name and :
        #     m = await bot.get_group_member_info(self_id=ctx['self_id'], group_id=bm.group, user_id=uid)
        #     name = m['card'] or m['nickname'] or str(m['user_id'])

    name = name or author.get_nick_name() or author.get_name()

    mem = bm.get_member(uid, bm.group) or bm.get_member(uid, 0)     # 兼容cmdv1
    if mem:
        bm.mod_member(uid, mem['alt'], name, 1)
        await bot.kkr_send(ev, f'成員{bot.kkr_at(uid)}昵稱已修改為{name}')
    else:
        bm.add_member(uid, bm.group, name, 1)
        await bot.kkr_send(ev, f"成員{bot.kkr_at(uid)}添加成功！歡迎{name}加入{clan['name']}")


@cb_cmd(('查看成員', '查看成员', '查詢成員', '成員查詢', 'list-member'), ArgParser(USAGE_LIST_MEMBER))
async def list_member(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)

    mems = bm.list_member(1)
    if l := len(mems):
        # 數字太多會被騰訊ban
        mems = map(lambda x: '{uid} | {name}'.format_map(x), mems)
        msg = [ f"\n{clan['name']}   {l}/30 人\n____ ID ____ | 昵稱", *mems]
        await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
    else:
        raise NotFoundError(ERROR_ZERO_MEMBER)


@cb_cmd(('退會', '退会'), ArgParser(usage='.退會 (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def del_member(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid = args['@'] or args.uid or ev.get_author_id()
    mem = _check_member(bm, uid, bm.group, '公會內無此成員')
    if uid != ev.get_author_id():
        _check_admin(ev, '才能踢人  ')
    bm.del_member(uid, mem['alt'])
    await bot.kkr_send(ev, f"成員{mem['name']}已從公會刪除", at_sender=True)


@cb_cmd(('清空成員', '清空成员'), ArgParser('.清空成員'))
async def clear_member(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)

    _check_admin(ev)
    msg = f"{clan['name']}已清空！" if bm.clear_member(1) else f"{clan['name']}已無成員"
    await bot.kkr_send(ev, msg, at_sender=True)


@cb_cmd(('一鍵入會', 'batch-add-member'), ArgParser('.一鍵入會'))
async def batch_add_member(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)

    _check_admin(ev)
    mlist = ev.get_members_in_group() 
    
    if len(mlist) > 50:
        raise ClanBattleError('群員過多！一鍵入會僅限50人以內群使用')

    self_id = config.BOT_ID
    succ, fail = 0, 0
    for m in mlist:
        if m.get_id() != self_id:
            try:
                bm.add_member(m.get_id(), bm.group, m.get_nick_name() or m.get_name() or m.get_id(), 1)
                succ += 1
            except DatabaseError:
                fail += 1
    msg = f'批量注冊完成！成功{succ}/失敗{fail}\n使用【{USAGE_LIST_MEMBER}】查看當前成員列表'
    await bot.kkr_send(ev, msg, at_sender=True)


def _gen_progress_text(round_, boss, hp, max_hp, score_rate):
    return f"\n目前{round_}周目 {BattleMaster.int2kanji(boss)}王    SCORE x{score_rate:.1f}\nHP={hp:,d}/{max_hp:,d}"


async def process_challenge(bot:KokkoroBot, ev:EventInterface, ch:ParseResult):
    """
    處理一條報刀 需要保證challenge['flag']的正確性
    """
    bm = BattleMaster(ev.get_group_id())
    now = datetime.now() - timedelta(days=ch.get('dayoffset', 0))
    clan = _check_clan(bm)
    msg = ['']

    rlist = bm.list_challenge_remain(1, now)
    rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
    for uid, _, name, r_n, r_e in rlist:  ### can't be negative challenge
        if ch.uid == uid :
            if r_n >0  or r_e > 0:
                mem = _check_member(bm, ch.uid, ch.alt)
                boss = ch.boss
                real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
                cur_round = real_r[int(ch.boss)-1]
                cur_boss= boss
                cur_hp = remain_hp_list[int(ch.boss)-1]

                if cur_hp == 0:
                    raise NotFoundError(f"這周{boss}王已經死了 出刀失敗") 

              #  round_plus = real_r- cur_round
              #  cur_round, cur_boss, cur_hp = bm.get_challenge_progress(1, now,int(boss),round_plus=round_plus) 
                round_ = cur_round or ch.round  

              #  if not (ch.round or ch.boss):
                    # 當前周目並且是尾刀，則自動將傷害設置為當前血量
                if BattleMaster.has_damage_kind_for(ch.flag, BattleMaster.LAST):
                    damage = cur_hp
                else:
                    damage = None    
                if not damage:
                    if not ch.damage:
                        raise NotFoundError('請給出傷害值')
                    damage = ch.damage
             #   if damage > cur_hp:
            #        damage = cur_hp
               #     msg.append(f'⚠️過度虐殺 傷害數值已自動修正為{damage}')    

                
                flag = ch.flag
                
                ### if in_list is 補償
                compen_no = 0
                get_file_now = datetime.now() -  timedelta(hours=5)
                dt_string = get_file_now.strftime("%d%m%Y")+ " "+ clan['gid']
                sub = _load_sub(dt_string)
                LN = sub.get_in_list()
                compen = sub.get_compen_list()
                try:
                    if uid in LN[str(boss)] :
                        if '補償' in  LN[str(boss)][uid][-1] :
                            flag = flag | BattleMaster.EXT
                            ### delete related 補償
                            compen_str = str(LN[str(boss)][uid][-1])
                            compen_no = compen_str.replace("補償",'')
                            del compen[uid][compen_no]
                except:
                    pass            
                
                # check if has 正刀 or 補償
                if r_n <=0 and compen_no== 0  :
                    raise NotFoundError("你已經沒正刀 出刀失敗") 

                if r_e <=0 and compen_no!= 0  :
                    raise NotFoundError("你已經沒補償 出刀失敗") 
                
                ### if 尾刀 add compen datails
                if flag == 1 and compen_no==0:
                    sub.add_compen(uid, f"{cur_boss}王補償" +str(ch.compen_details))
                    _save_sub(sub, dt_string)    

                # if (ch.flag == BattleMaster.LAST) and (ch.round or ch.boss) and (not damage):
                #     raise NotFoundError('補報尾刀請給出傷害值')     # 補報尾刀必須給出傷害值


                # 上一刀如果是尾刀，這一刀就是補償刀
              #  challenges = bm.list_challenge_of_user_of_day(mem['uid'], mem['alt'], now)
              #  if len(challenges) > 0 and challenges[-1]['flag'] == BattleMaster.LAST and r_e > 0:
               #     flag = flag | BattleMaster.EXT
               #     msg.append('⚠️這刀已自動標記為補時刀') ### 這是該刀是用了補時刀的意思
                   # await del_comp(bot, ev,ch.uid) 
            #    else:   # 傷害校對
                   # if damage >= cur_hp:
                        # 不是尾刀，則標記為尾刀
                a=[   '''    if not BattleMaster.has_damage_kind_for(flag, BattleMaster.LAST):
                            rlist = bm.list_challenge_remain(1, datetime.now() - timedelta(0))
                            rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
                            str_now = datetime.now() -  timedelta(hours=5)
                            dt_string = str_now.strftime("%d%m%Y")+ " "+ clan['gid']
                            sub = _load_sub(dt_string)
                            compen = sub.get_compen_list()
                            for _ in rlist:
                                if uid in _ :
                                    time_chall = _[-1]
                                    if time_chall == 0 :
                                        cur_round, cur_boss, cur_hp = bm.get_challenge_progress(1, now)
                                        compen.append(  [uid, f"{cur_boss}王補償"] )   
                                        _save_sub(sub, dt_string)
                            flag = flag | BattleMaster.LAST            
                            msg.append('⚠️已自動標記為尾刀, ⚠️⚠️⚠️請用.改補 秒數 提供補償刀備注')''']

             #       if BattleMaster.has_damage_kind_for(flag, BattleMaster.LAST):
               #         if damage < cur_hp:
                #            damage = cur_hp
            #                msg.append(f'⚠️尾刀傷害已自動修正為{damage}')
                eid = bm.add_challenge(mem['uid'], mem['alt'], round_, boss, damage, flag, now)
                real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
                aft_boss= boss
                aft_round = real_r[int(ch.boss)-1]
                aft_hp = remain_hp_list[int(ch.boss)-1]
                max_hp, score_rate = bm.get_boss_info(aft_round, aft_boss, clan['server'])
                
                ### clear 你在篩刀大會的名單
                for in_key in LN.keys(): ### first delete already key
                    try:
                        del LN[in_key][uid]
                    except :
                        print("no such key")                  
                _save_sub(sub, dt_string)
                msg.append(f"記錄編號E{eid}：\n{mem['name']}給予{round_}周目{bm.int2kanji(boss)}王{damage:,d}點傷害\n")
                if compen_no != 0:
                    msg.append(f"已使用了【{compen_str}】")
                else:
                    msg.append(f"已使用了【正刀】")    
                msg.append(_gen_progress_text(aft_round, aft_boss, aft_hp, max_hp, score_rate))
                await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)

                # 判斷是否更換boss，呼叫預約
                real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
               # call_r = min(  real_r  )
                print( real_r )
                print('int(ch.boss) ',  int(ch.boss)   )
                if real_r[int(ch.boss)-1] !=round_ or aft_hp<=0  :
                    print(  'real_r' , real_r  )
                    await call_subscribe(bot, ev, real_r, aft_boss)
                
                real_r = real_r[int(ch.boss)-1]
                await auto_unlock_boss(bot, ev, bm)
                await auto_unsubscribe(bot, ev, bm.group, mem['uid'], boss,real_r,bm)
            else:
                raise NotFoundError('你打完三刀了 還打!?')

def isDD(damage):
    return damage < 600000

import random
async def jiuzhe(bot, ev):
    msglist = ['就這？會長： 你下期不用打了', R.img('就這.jpg')]
    index = random.randint(0, len(msglist)-1)
    await bot.kkr_send(ev, msglist[index])

@cb_cmd(('出刀', '報刀', '报刀', '3'), ArgParser(usage='.出刀 <傷害值> (@id)', arg_dict={
    '': ArgHolder(tip='傷害值', type=damage_int),
    '@': ArgHolder(tip='id', type=str, default=0),
    'R': ArgHolder(tip='周目數', type=round_code, default=0),
    'B': ArgHolder(tip='Boss編號', type=boss_code, default=0),
    'D': ArgHolder(tip='日期差', type=int, default=0)}))
async def add_challenge(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    ### if already in in_list, then use in_list infor 
    uid = args['@'] or args.uid or ev.get_author_id()
    now = datetime.now() -  timedelta(hours=5)
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    LN = sub.get_in_list()
    boss = 0
    for in_key in LN.keys():
        if uid in LN[in_key]:
            boss = in_key
    boss =  args.B or boss
    if boss ==0 :
        raise NotFoundError(f'沒有boss編號')
    ### check if dmg > hp
    real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
    hp = remain_hp_list[int(boss)-1]
    damage = args.get('')
    if damage > hp:
        raise NotFoundError(f'傷害超出王血 請改用.4 補償秒數')
    challenge = ParseResult({
        'round': args.R,
        'boss': int(boss),
        'damage': args.get(''),
        'uid': uid,
        'alt': ev.get_group_id(),
        'flag': BattleMaster.NORM,
        'dayoffset': args.get('D', 0)
    })
    await process_challenge(bot, ev, challenge)

    if isDD(damage):
        await jiuzhe(bot, ev)
        

@cb_cmd(('出尾刀', '收尾', '尾刀', '4'), ArgParser(usage='.尾刀 (秒數s備註) (@<id>)', arg_dict={
    '': ArgHolder(tip='秒數s備註', type=str,default=0),
    '@': ArgHolder(tip='id', type=str, default=0),
    'R': ArgHolder(tip='周目數', type=round_code, default=0),
    'B': ArgHolder(tip='Boss編號', type=boss_code, default=0)}))
async def add_challenge_last(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    uid = args['@'] or args.uid or ev.get_author_id()
    now = datetime.now() -  timedelta(hours=5)
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    LN = sub.get_in_list()
    boss = 0
    for in_key in LN.keys():
        if uid in LN[in_key]:
            boss = in_key
    boss =  args.B or boss
    if boss ==0 :
        raise NotFoundError(f'沒有boss編號')
    challenge = ParseResult({
        'round': args.R,
        'boss': int(boss),
        'damage':0,
        'uid': args['@'] or args.uid or ev.get_author_id(),
        'alt': ev.get_group_id(),
        'flag': BattleMaster.LAST,
        'compen_details' :args.get("")
    })
    ### if this is 正刀 ，have to update 補償
    compen_seconds = args.get("")
    if compen_seconds==0 :
        raise NotFoundError(f'你沒有提供補償秒數 重新輸入.4 補償秒數')
   # cur_round, cur_boss, cur_hp = bm.get_challenge_progress(1, now,int(boss))  
   # sub.add_compen(uid, f"{cur_boss}王補償" +compen_seconds)
  #  _save_sub(sub, dt_string)     
    await process_challenge(bot, ev, challenge)


@cb_cmd(('出補時刀', '補償刀', '補時', 'add-challenge-ext'), ArgParser(usage='.出補時刀 <傷害值> (@id)', arg_dict={
    '': ArgHolder(tip='傷害值', type=damage_int),
    '@': ArgHolder(tip='id', type=str, default=0),
    'R': ArgHolder(tip='周目數', type=round_code, default=0),
    'B': ArgHolder(tip='Boss編號', type=boss_code, default=0)}))
async def add_challenge_ext(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    challenge = ParseResult({
        'round': args.R,
        'boss': args.B,
        'damage': args.get(''),
        'uid': args['@'] or args.uid or ev.get_author_id(),
        'alt': ev.get_group_id(),
        'flag': BattleMaster.EXT
    })
    await process_challenge(bot, ev, challenge)


@cb_cmd(('掉刀', 'add-challenge-timeout'), ArgParser(usage='.掉刀 (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0),
    'R': ArgHolder(tip='周目數', type=round_code, default=0),
    'B': ArgHolder(tip='Boss編號', type=boss_code, default=0)}))
async def add_challenge_timeout(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    msg ="還打什麼指令 趕快找下期戰隊吧"
    challenge = ParseResult({
        'round': args.R,
        'boss': args.B,
        'damage': 1,
        'uid': args['@'] or args.uid or ev.get_author_id(),
        'alt': ev.get_group_id(),
        'flag': BattleMaster.TIMEOUT
    })
   # await process_challenge(bot, ev, challenge)
    await bot.kkr_send(ev,msg,at_sender=True)


# TODO 將預約信息轉至數據庫
SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/clanbattle_sub/')
SUBSCRIBE_MAX = [99, 6, 6, 6, 6, 6]
os.makedirs(SUBSCRIBE_PATH, exist_ok=True)

class SubscribeData:

    def __init__(self, data:dict):
        for i in '12345':
            data.setdefault(i, [])
            data.setdefault('m' + i, [])
            l = len(data[i])
            if len(data['m' + i]) != l:
                data['m' + i] = [None] * l
        data.setdefault('tree', {})
        data.setdefault('sl', [])
        data.setdefault('lock', [])
        data.setdefault('in', {})
        data.setdefault('del', [])
        data.setdefault('compen', {})
        data.setdefault('queue', [])
        if 'max' not in data or len(data['max']) != 6:
            data['max'] = [99, 6, 6, 6, 6, 6]
        self._data = data
        
    @staticmethod
    def default():
        return SubscribeData({
            '1':[], '2':[], '3':[], '4':[], '5':[],
            'm1':[], 'm2':[], 'm3':[], 'm4':[], 'm5':[],
            'tree':{}, 'lock':[],'sl':[],'in':{},'compen':{}, 'del':[], 'queue':[],
            'max': [99, 6, 6, 6, 6, 6]
        })
    
    def get_sub_list(self, boss:int):
        return self._data[str(boss)]
        
    def get_memo_list(self, boss:int):
        return self._data[f'm{boss}']
    
    def get_tree_list(self):
        return self._data['tree']
    
    def get_queue_list(self):
        return self._data['queue']

    def get_del_list(self):
        return self._data['del']    

    def get_compen_list(self):
        return self._data['compen']    

    def get_in_list(self):
        return self._data['in']    

    def get_SL_list(self):
        return self._data['sl']    

    def get_sub_limit(self, boss:int):
        return self._data['max'][boss]

    def set_sub_limit(self, boss:int, limit:int):
        self._data['max'][boss] = limit

    def add_sub(self, boss:int, uid:str, memo:str,sub_round:str):
        self._data[str(boss)].append(str(uid) +"&"+str(sub_round) )
        self._data[f'm{boss}'].append(memo)
  
    def remove_sub(self, boss:int, uid:str):
        s = self._data[str(boss)]
        m = self._data[f'm{boss}']
        i = s.index(uid)
        s.pop(i)
        m.pop(i)

    def add_tree(self,boss:str,uid:str):
        for loop_boss in  self._data['tree']: 
            if uid in self._data['tree'][loop_boss]:
                self._data['tree'][loop_boss].remove(uid)

        if boss in self._data['tree']: 
            if uid not in self._data['tree'][boss] :
                self._data['tree'][boss].append(  uid)   
        else:
            update_data={boss:[uid]}
            self._data['tree'].update(update_data)        


    def add_del(self, uid:str,details:str):
        self._data['del'].append([uid,details])
    def add_queue(self, uid:str,details:str):
        self._data['queue'].append([uid,details])    

    def add_compen(self, uid:str,details:str):
        print( uid  )
        if uid in self._data['compen']: ## then add again
            if 'a' not in self._data['compen'][uid] :
                self._data['compen'][uid]['a'] = details  
            elif 'b' not in self._data['compen'][uid] :
                self._data['compen'][uid]['b'] = details    
            elif 'c' not in self._data['compen'][uid] :
                self._data['compen'][uid]['c'] = details    
        else:
            update_data={uid:{'a':details}}
            self._data['compen'].update(update_data)    

    def del_redu_compen(self, uid:str):
        print( uid  )
        if uid in self._data['compen']: ## then del reduplicate
            if 'a'  in self._data['compen'][uid] :
                del self._data['compen'][uid]['a']
                return 
            elif 'b'  in self._data['compen'][uid] :
                del self._data['compen'][uid]['b']   
                return
            elif 'c'  in self._data['compen'][uid] :
                del self._data['compen'][uid]['c']  
                return

    def add_in(self, uid:str,sl:str,remain_chall:str,dmg:str,boss:str,in_challeng:str):
        for in_key in self._data['in'].keys(): ### first delete already key
            try:
                del self._data['in'][in_key][uid]
            except :
                print("no such key")    
        if boss in self._data['in']: ## then add again
            self._data['in'][boss][uid] = [sl,remain_chall,dmg,in_challeng]
        else:    
            update_data={boss:{uid:[sl,remain_chall,dmg,in_challeng]}}
            self._data['in'].update(update_data)

    def add_sl(self, uid:str):
        self._data['sl'].append(uid)    

    def clear_tree_sep(self,uid:str):
        for tree_key in self._data['tree']:
            if uid in  self._data['tree'][tree_key]:
                self._data['tree'][tree_key].remove(uid)
        
    def clear_tree(self,boss:str):
        try:
            del self._data['tree'][str(boss)]
        except:
            pass   
  

    def clear_del(self):
        self._data['del'].clear()    

    def clear_compen(self):
        self._data['compen'].clear()   

    def clear_in(self):
        self._data['in'].clear()    

    def clear_sl(self):
        self._data['sl'].clear()    
        
    def get_lock_info(self):
        return self._data['lock']
    
    def set_lock(self, uid:str, ts):
        self._data['lock'] = [ (uid, ts) ]

    def clear_lock(self):
        self._data['lock'].clear()

    def dump(self, filename):
        with open(filename, 'w', encoding='utf8') as f:
            json.dump(self._data, f, ensure_ascii=False)


def _load_sub(gid) -> SubscribeData:
    filename = os.path.join(SUBSCRIBE_PATH, f"{gid}.json")
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf8') as f:
            return SubscribeData(json.load(f))
    else:
        return SubscribeData.default()


def _save_sub(sub:SubscribeData, gid):
    filename = os.path.join(SUBSCRIBE_PATH, f"{gid}.json")
    sub.dump(filename)


def _gen_namelist_text(bot:KokkoroBot, bm:BattleMaster, uidlist:List[str], memolist:List[str]=None, do_at=False):
    if do_at:
        mems = map(lambda x: str(bot.kkr_at(x)), uidlist)
    else:
        mems = map(lambda x: bm.get_member(x, bm.group) or bm.get_member(x, 0) or {'name': str(x)}, uidlist)
        mems = map(lambda x: x['name'], mems)
    if memolist:
        mems = list(mems)
        for i in range(len(mems)):
            if i < len(memolist) and memolist[i]:
                mems[i] = f"{mems[i]}：{memolist[i]}"
    return mems


SUBSCRIBE_TIP = ''

global enabledict 
enabledict ={}

@cb_cmd(('enable'), ArgParser(usage='.enable func', arg_dict={
    '': ArgHolder(tip='功能', type=str),
    }))    
async def enable(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    print(  config.SUPER_USER   )
    print( ev.get_author_id()  )
    if ev.get_author_id() in config.SUPER_USER :
        remain = list(str(ev.get_param().remain).split(' '))
        func = remain[0]
        enabledict[func] =True
        await bot.kkr_send(ev, f'已啟動{func}')  
    else:
        raise NotFoundError(f'你沒有權限')

@cb_cmd(('disable'), ArgParser(usage='.disable func', arg_dict={
    '': ArgHolder(tip='功能', type=str),
    }))    
async def disable(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    if ev.get_author_id() in config.SUPER_USER :
        remain = list(str(ev.get_param().remain).split(' '))
        func = remain[0]
        enabledict[func] =False
        await bot.kkr_send(ev, f'已關閉{func}')  
    else:
        raise NotFoundError(f'你沒有權限')

@cb_cmd(('backup'), ArgParser('.backup'))
async def backup(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    try :
        fun_name = inspect.stack()[0][3]
        if enabledict[fun_name] :
            _check_admin(ev)
            SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/')
            SUBSCRIBE_PATH2 = os.path.expanduser('~/.kokkoro/backup/')
            path1 = os.path.join(SUBSCRIBE_PATH, 'clanbattle.db')
            path2 = os.path.join(SUBSCRIBE_PATH2, 'clanbattle.db')
            shutil.copy(path2, path1)
            await bot.kkr_send(ev, '已拿回昨天資料')  
        else:
            raise NotFoundError(f'backup功能未啟動,請聯絡bot管理員') 
    except:
        raise NotFoundError(f'backup功能未啟動,請聯絡bot管理員')   

@cb_cmd(('刪刀', '删刀'), ArgParser(usage='.刪刀 E記錄編號', arg_dict={
    'E': ArgHolder(tip='記錄編號', type=int)}))
async def del_challenge(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    now = datetime.now()
    clan = _check_clan(bm)
    zone = bm.get_timezone_num(clan['server'])
    challen = bm.list_challenge_of_day(clan['cid'], now, zone)
   # _check_admin(ev)
    ch = bm.get_challenge(args.E, 1, now)
    if not ch:
        raise NotFoundError(f'未找到出刀記錄E{args.E}')
    if ch['uid'] != ev.get_author_id():
        _check_admin(ev, '才能刪除其他人的記錄')
    bm.del_challenge(args.E, 1, now)
    #back up ,刪刀記錄
    challenstr = 'E{eid:0>3d}|{name}|r{round}|b{boss}|{dmg: >7,d}{flag_str}'
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    dlist = sub.get_del_list()
    msg= []
    for c in challen:
        if c['eid'] == args.E :
            mem = bm.get_member(c['uid'], c['alt'])
            c['name'] = mem['name'] if mem else c['uid']
            flag = c['flag']
            c['flag_str'] = '|' + ','.join(BattleMaster.damage_kind_to_string(flag))
            msg = challenstr.format_map(c)
 #   print(msg)    
    sub.add_del(ch['uid'] ,msg)
    _save_sub(sub, dt_string)
    await bot.kkr_send(ev, f"{clan['name']}已刪除{bot.kkr_at(ch['uid'])}的出刀記錄E{args.E},同時記錄至刪刀記錄", at_sender=True)

@cb_cmd(('查刪刀', '查刪','查删刀'), ArgParser(usage='.查刪刀 (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0),
    }))    
async def list_del_knife(bot:KokkoroBot, ev:EventInterface,args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5) 
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    del_list = sub.get_del_list()
    send_del_list=[]
    if args['@']!= 0 :
        for del_ in  del_list:
            if del_[0]==args['@'] :
                send_del_list.append( del_[1]    )
    else:
        send_del_list = [x[1] for x in del_list]            

    msg = [ f"刪除了的刀如下" ]
    msg.extend(_gen_namelist_text(bot, bm, send_del_list))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)  


@cb_cmd(('預約', '预约','sub'), ArgParser(usage='.預約 周 Boss編號 備註 (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0),
    '': ArgHolder(tip='備註', type=str)
    }))
async def subscribe(bot:KokkoroBot, ev:EventInterface, args:ParseResult): 
    uid =  args['@'] or ev.get_author_id()
    remain = list(str(ev.get_param().remain).split(' '))
    sub_round = remain[0]
    boss = remain[1]
    if len(remain) >= 3 :
        memo = remain[2]
    else:
        memo = ""    
    if "+" in boss:
        boss = boss.split("+")
        for b in boss:
            await subscribe2(bot, ev, uid,int(b), int(sub_round),memo)
    else:
       await subscribe2(bot, ev, uid,int(boss), int(sub_round),memo)         
 

async def subscribe2(bot:KokkoroBot, ev:EventInterface, uid ,boss, sub_round,memo):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
    r = min(real_r)
    sub = _load_sub(dt_string)
    boss_name = bm.int2kanji(boss)
    slist = sub.get_sub_list(boss)
    mlist = sub.get_memo_list(boss)
    limit = sub.get_sub_limit(boss)
    memo = memo + f" ( {sub_round}周)"
    if str(uid) +"&"+str(sub_round) in slist:
        raise AlreadyExistError(f'您已經預約過{sub_round}周{boss_name}王了')
    msg = ['']
    if int(sub_round) >=  r :
        if len(slist) < limit:
            clan = _check_clan(bm)
            sub.add_sub(boss, uid, memo,sub_round)
            now = datetime.now() -  timedelta(hours=5)
            dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
            _save_sub(sub, dt_string)
            msg.append(f'已為您預約{boss_name}王！')
        else:
            msg.append(f'預約失敗：{boss_name}王預約人數已達上限')
        msg.append(f'=== 當前隊列 {len(slist)}/{limit} ===')
        slist = [ x.split("&")[0] for x in slist]
        msg.extend(_gen_namelist_text(bot, bm, slist, mlist))
        msg.append(SUBSCRIBE_TIP)
        await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
    else:
        raise AlreadyExistError(f'現在已經是{r}周了，不能預約{sub_round}周')    

async def unsubscribe2(bot:KokkoroBot, ev:EventInterface, uid ,boss, sub_round):
    remain = list(str(ev.get_param().remain).split(' '))
    bm = BattleMaster(ev.get_group_id())
    _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    boss_name = bm.int2kanji(boss)    
    slist = sub.get_sub_list(boss)
    mlist = sub.get_memo_list(boss)
    limit = sub.get_sub_limit(boss)    
    del_uid = uid+"&"+str(sub_round)
 #   slist = [ x.split("&")[0] for x in slist]
    if del_uid not in slist:
        raise NotFoundError(f'您沒有預約{sub_round}周{boss_name}王')
    now = datetime.now() -  timedelta(hours=5)
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub.remove_sub(boss, del_uid)
    _save_sub(sub,dt_string )
    msg = [ f'\n已為您取消預約{boss_name}王！' ]
    slist = sub.get_sub_list(boss)
    slist = [ x.split("&")[0] for x in slist]
    mlist = sub.get_memo_list(boss)
    msg.append(f'=== 當前隊列 {len(slist)}/{limit} ===')    
    msg.extend(_gen_namelist_text(bot, bm, slist, mlist))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)

@cb_cmd(('取消預約', '取消预约', 'unsub'), ArgParser(usage='.取消預約 周 <Boss號> (@id)', arg_dict={
    '': ArgHolder(tip='周 Boss編號'),
     '@': ArgHolder(tip='id', type=str, default=0)}))
async def unsubscribe(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    uid =  args['@'] or ev.get_author_id()
    remain = list(str(ev.get_param().remain).split(' '))
    sub_round = remain[0]
    boss = remain[1]  
    if "+" in boss:
        boss = boss.split("+")
        for b in boss:
            await unsubscribe2(bot, ev, uid,int(b), int(sub_round))
    else:
       await unsubscribe2(bot, ev, uid,int(boss), int(sub_round))  


async def auto_unsubscribe(bot:KokkoroBot, ev:EventInterface, gid, uid, boss,round_,bm):
    now = datetime.now() -  timedelta(hours=5)
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    slist = sub.get_sub_list(boss)
    slist_deepcopy = copy.deepcopy(slist)
    msg= []
    for s in slist_deepcopy :
        if int(s.split("&")[1]) <= int(round_):
            sub.remove_sub(boss, s)
            msg.append( f'已為{bot.kkr_at(s.split("&")[0])}自動取消{BattleMaster.int2kanji(boss)}王的訂閱'  )
            _save_sub(sub, dt_string)        
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
        
async def call_subscribe(bot:KokkoroBot, ev:EventInterface, round_:list, boss:int):
    print( 'r ', round_)
    bm = BattleMaster(ev.get_group_id())
    msg = []
    now = datetime.now() -  timedelta(hours=5)
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    tlist = sub.get_tree_list()
    inlist = sub.get_in_list()
    slist2 =[]
    mlist2 =[]   
    for loop_boss in range(1,6):
        slist = sub.get_sub_list(loop_boss)
        mlist = sub.get_memo_list(loop_boss)
        for loop_s in slist:
            match_round = round_[ loop_boss-1]
            if str(match_round) == loop_s.split("&")[1]  : #and str(loop_boss)==str(boss)   :
                slist2.append(   loop_s.split("&")[0]   )
                mlist2 .append(   f'{loop_s.split("&")[1]}周{loop_boss}王'  )
    if slist2   :
        msg.append(f"您們預約的王出現啦！")
        msg.extend(_gen_namelist_text(bot, bm, slist2, mlist2, do_at=True))
    if slist and tlist:
        msg.append("==========")   
    tlist= tlist.get(str(boss), None) 
    if tlist:
        msg.append(f"以下成員可以下樹了")
        msg.extend(map(lambda x: str(bot.kkr_at(x)), tlist))
        sub.clear_tree(boss)
        now = datetime.now() -  timedelta(hours=5)
        dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
        _save_sub(sub, dt_string)
    if inlist:
        if str(boss) in inlist:
            name_list = list(inlist[str(boss)].keys())
            del inlist[str(boss)]
            msg.append(f"篩刀大會表清空了")
            msg.extend(map(lambda x: str(bot.kkr_at(x)), name_list))
            now = datetime.now() -  timedelta(hours=5)
            clan = _check_clan(bm)
            dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
            _save_sub(sub, dt_string)
    if msg:
        await bot.kkr_send(ev, '\n'.join(msg), at_sender=False)    # do not at the sender


@cb_cmd(('查詢預約', '查询预约', '查预约', '預約查看', 'csub'), ArgParser('.查預約'))
async def list_subscribe(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
    msg = [ f"\n現在{r}周目：" ]
    for boss in range(1, 6):
        slist = sub.get_sub_list(boss)
        mlist = sub.get_memo_list(boss)
        limit = sub.get_sub_limit(boss)
        slist = [ x.split("&")[0] for x in slist]
        msg.append(f"========\n{bm.int2kanji(boss)}王: {len(slist)}/{limit}")
        msg.extend(_gen_namelist_text(bot, bm, slist, mlist))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)


@cb_cmd(('清空預約', '清空预约', '清理預約', '預約清理', 'clear-subscribe'), ArgParser('.清空預約', arg_dict={
    '': ArgHolder(tip='Boss編號',type = int, default=0)}))
async def clear_subscribe(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    _check_admin(ev, '才能清理預約隊列')
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    boss = args['']
    if boss == 0 :
        for _ in range(1,6):  
            slist = sub.get_sub_list(_)
            mlist = sub.get_memo_list(_)
            if slist:
                slist.clear()
                mlist.clear()
                _save_sub(sub, dt_string)
        await bot.kkr_send(ev, f"整個預約隊列已清空", at_sender=True)
    else:            
        slist = sub.get_sub_list(boss)
        mlist = sub.get_memo_list(boss)
        if slist:
            slist.clear()
            mlist.clear()
            _save_sub(sub, dt_string)
            await bot.kkr_send(ev, f"{bm.int2kanji(boss)}王預約隊列已清空", at_sender=True)
        else:
            raise NotFoundError(f"無人預約{bm.int2kanji(boss)}王")


@cb_cmd(('預約上限', '预约上限'), ArgParser(usage='.預約上限 B<Boss號> <上限值>', arg_dict={
    'B': ArgHolder(tip='Boss編號', type=boss_code),
    '': ArgHolder(tip='上限值', type=int)
}))
async def set_subscribe_limit(bot:KokkoroBot, ev, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)

    _check_admin(ev, '才能設置預約上限')
    limit = args['']
    if not (0 < limit <= 30):
        raise ClanBattleError('預約上限只能為1~30內的整數')
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    sub.set_sub_limit(args.B, limit)    
    _save_sub(sub, dt_string)
    await bot.kkr_send(ev, f'{bm.int2kanji(args.B)}王預約上限已設置為：{limit}')

async def check_inList(bot:KokkoroBot, ev:EventInterface,boss=0):

    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    LN = sub.get_in_list()
    SL = sub.get_SL_list()
    tree = sub.get_tree_list()
  #  real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
   # r, b, hp = bm.get_challenge_progress(1, datetime.now(),int(boss))
   # round_plus = real_r - r
   # tree_len= 0 
  #  in_len = 0

    no_one = 0
    whole_msg = []
    print('b',boss)
    if boss == 0 :
        for boss in range(1,6) :
            real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
            r = real_r[int(boss)-1]
            b =boss 
            hp = remain_hp_list[int(boss)-1]
            hp = int(round(hp / 10000,0))
            hp =str(hp)+'w'
            solid_line  = '━━━━━━━━━━━━━━━━━'  
            tree_len =   len(tree.get(str(boss), []) )
            in_len =   len(LN.get(str(boss), []))
            try:      
                copy_LN = LN[str(boss)]                
                msg = [ f'【{b}王 {r}周 {hp}  | {in_len}人進 {tree_len}人掛樹】']
                # challenstr = '({remain_chall} {SL}) | {name}【{dmg}】'
                challenstr = '{name}【{dmg}】'
                match_dict = {}
                for each_key, each_item in copy_LN.items():
                    uid = each_key
                    if uid in SL:
                        sl_ = "沒SL"
                    else:
                        sl_= "有SL"   
                    remain_chall=  each_item[1]    
                    dmg=  each_item[2]              
                    mems = _check_member(bm, uid, bm.group)
                    match_dict['name'] = mems['name']
                    match_dict['dmg'] =dmg
                    match_dict['SL'] =sl_
                    match_dict['remain_chall'] =remain_chall
                    msg.append(challenstr.format_map(match_dict))  
                    print( msg  )
                msg.append(solid_line)    
                whole_msg.append( msg  )
                print(  whole_msg  )  
            except:
                pass               
        print(  whole_msg  )    
        flat_list = [item for sublist in whole_msg for item in sublist]       
        try: 
            await bot.kkr_send(ev, '\n'.join(flat_list))       
        except:
            raise AlreadyExistError("目前沒有人進")        
    else:
        real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
        r = real_r[int(boss)-1]
        b =boss 
        hp = remain_hp_list[int(boss)-1]
        hp = int(round(hp / 10000,0))
        hp =str(hp)+'w'
        solid_line = '━━━━━━━━━━━━━━━━━' 
        msg = [ f'{clan["name"]}篩刀大會 目前{b}王 {r}周 {hp} \n {solid_line}']
        challenstr = '({remain_chall} {SL}) | {name}【{dmg}】'
        match_dict = {}  
        try:    
            LN = LN[boss]
        except:
            raise AlreadyExistError('\n'.join(msg))   
        for each_key, each_item in LN.items():
            uid = each_key
            if uid in SL:
                sl_ = "沒SL"
            else:
                sl_= "有SL"   
            remain_chall=  each_item[1]    
            dmg=  each_item[2]              
            mems = _check_member(bm, uid, bm.group)
            match_dict['name'] = mems['name']
            match_dict['dmg'] =dmg
            match_dict['SL'] =sl_
            match_dict['remain_chall'] =remain_chall
            msg.append(challenstr.format_map(match_dict))  
        await bot.kkr_send(ev, '\n'.join(msg),at_sender=True)                    

@cb_cmd(('掛樹', '上樹', '挂树','tree'), ArgParser(usage='.掛樹 王編號 (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0),
    '': ArgHolder(tip='boss', type=str, default=0)
    }))
async def add_sos(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid = args['@'] or ev.get_author_id()
    clan = _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    tree = sub.get_tree_list()
    LN = sub.get_in_list()
    boss_key = 0
    for in_key in LN:
        if uid in LN[in_key]:
            LN[in_key][uid][-2] = "掛樹"
            boss_key = in_key
    boss = boss_key or args['']  
    if boss ==0:
        raise AlreadyExistError("請提供掛樹的王編號 e.g 掛樹 王編號 (@id)")   
    if uid in tree:
        raise AlreadyExistError("您已在樹上")
    print( 'boss', boss  )
    sub.add_tree(boss,uid)
    _save_sub(sub, dt_string)
    msg = [ "\n您已上樹，本Boss被擊敗時將會通知您",
           f"目前{clan['name']}掛樹人數為{len(tree[boss])}人：" ]
    msg.extend(_gen_namelist_text(bot, bm, tree[boss]))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
    await check_inList(bot, ev,boss)


@cb_cmd(('查樹', '查树'), ArgParser('.查樹'))
async def list_sos(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    tree = sub.get_tree_list()
    for tree_key in tree:
        if len(tree[tree_key]) > 0:
            msg = [ f"\n{tree_key}王掛樹人數為{len(tree[tree_key])}人：" ]
            msg.extend(_gen_namelist_text(bot, bm, tree[tree_key]))
            msg.append( '--------------------------------------' )
            await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)


@cb_cmd(('鎖定', '申請出刀', '锁定'), ArgParser('.鎖定'))
async def lock_boss(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    _check_member(bm, ev.get_author_id(), bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']

    sub = _load_sub(dt_string)
    lock = sub.get_lock_info()
    if lock:
        uid, ts = lock[0]
        time = datetime.fromtimestamp(ts)
        mem = bm.get_member(uid, bm.group) or bm.get_member(uid, 0) or {'name': str(uid)}
        delta = datetime.now() - time
        delta = timedelta(seconds=round(delta.total_seconds()))     # ignore miliseconds
        msg = f"\n鎖定失敗：{mem['name']}已於{delta}前鎖定了Boss"
        await bot.kkr_send(ev, msg, at_sender=True)
    else:
        uid = ev.get_author_id()
        time = datetime.now()
        sub.set_lock(uid, datetime.now().timestamp())
        _save_sub(sub, dt_string)
        msg = f"已鎖定Boss"
        await bot.kkr_send(ev, msg, at_sender=True)


@cb_cmd(('解鎖', '解锁'), ArgParser('.解鎖'))
async def unlock_boss(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']

    sub = _load_sub(dt_string)
    lock = sub.get_lock_info()
    if lock:
        uid, ts = lock[0]
        time = datetime.fromtimestamp(ts)
        if uid != ev.get_author_id():
            mem = bm.get_member(uid, bm.group) or bm.get_member(uid, 0) or {'name': str(uid)}
            delta = datetime.now() - time
            delta = timedelta(seconds=round(delta.total_seconds()))     # ignore miliseconds
            _check_admin(ev, f"才能解鎖其他人\n解鎖失敗：{mem['name']}於{delta}前鎖定了Boss")
        sub.clear_lock()
        _save_sub(sub, dt_string)
        msg = f"\nBoss已解鎖"
        await bot.kkr_send(ev, msg, at_sender=True)
    else:
        msg = "\n無人鎖定Boss"
        await bot.kkr_send(ev, msg, at_sender=True)


async def auto_unlock_boss(bot:KokkoroBot, ev:EventInterface, bm:BattleMaster):
    now = datetime.now() -  timedelta(hours=5)
    clan = _check_clan(bm)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    lock = sub.get_lock_info()
    if lock:
        uid, ts = lock[0]
        time = datetime.fromtimestamp(ts)
        if uid != ev.get_author_id():
            mem = bm.get_member(uid, bm.group) or bm.get_member(uid, 0) or {'name': str(uid)}
            delta = datetime.now() - time
            delta = timedelta(seconds=round(delta.total_seconds()))     # ignore miliseconds
            msg = f"⚠️{mem['name']}於{delta}前鎖定了Boss，您出刀前未申請鎖定！"
            await bot.kkr_send(ev, msg, at_sender=True)
        else:
            sub.clear_lock()
            _save_sub(sub, dt_string)
            msg = f"\nBoss已自動解鎖"
            await bot.kkr_send(ev, msg, at_sender=True)


@cb_cmd(('進度', '进度', '查詢進度', '進度查看', '查看進度', '狀態', 'progress'), ArgParser(usage='.進度'))
async def show_progress(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    r_list, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
    msg = []
    for b in range(1,6):    
        hp = remain_hp_list[b-1]
        r = r_list[b-1]
        max_hp, score_rate = bm.get_boss_info(r, b, clan['server'])
        msg2 = _gen_progress_text(r, b, hp, max_hp, score_rate)
        msg.append( msg2  )
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)


@cb_cmd(('統計', '傷害統計','统计'), ArgParser(usage='.傷害統計', arg_dict={
        '': ArgHolder(tip='time',type = str, default="")}))
async def stat_damage(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    now = datetime.now()
    clan = _check_clan(bm)

    yyyy, mm, _ = bm.get_yyyymmdd(now)
    if "y" in list(ev.get_param().remain) or "Y"  in list(ev.get_param().remain)  :
        stat = bm.stat_damage(1, now,one_day_only=True)
    else:
        stat = bm.stat_damage(1, now)

    yn = len(stat)
    if not yn:
        await bot.kkr_send(ev, f"{clan['name']}{yyyy}年{mm}月會戰統計數據為空", at_sender=True)
        return

    stat.sort(key=lambda x: x[3][0], reverse=True)
    total = [ s[3][0] for s in stat ]
    name = [ s[2] for s in stat ]
    y_pos = list(range(yn))
    y_size = 0.3 * yn + 1.0
    unit = 1e4
    unit_str = 'w'

    # convert to pre-sum
    for s in stat:
        d = s[3]
        d[0] = 0
        for i in range(2, 6):
            d[i] += d[i - 1]
    pre_sum_dmg = [
        [ s[3][b] for s in stat ] for b in range(6)
    ]

    # generate statistic figure
    fig, ax = plt.subplots()
    fig.set_size_inches(10, y_size)
    ax.set_title(f"{clan['name']}{yyyy}年{mm}月會戰傷害統計")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(name)
    ax.set_ylim((-0.6, yn - 0.4))
    ax.invert_yaxis()
    ax.set_xlabel('傷害')
    colors = ['#00a2e8', '#22b14c', '#b5e61d', '#fff200', '#ff7f27', '#ed1c24']
    bars = [ ax.barh(y_pos, pre_sum_dmg[b], align='center', color=colors[b]) for b in range(5, -1, -1) ]
    bars.reverse()
    ax.ticklabel_format(axis='x', style='plain')
    for b in range(1, 6):
        for i, rect in enumerate(bars[b]):
            x = (rect.get_width() + bars[b - 1][i].get_width()) / 2
            y = rect.get_y() + rect.get_height() / 2
            d = pre_sum_dmg[b][i] - pre_sum_dmg[b - 1][i]
            if d > unit:
                ax.text(x, y, f'{d/unit:.0f}{unit_str}', ha='center', va='center')
            if b == 5:
                ax.text(rect.get_width() + 10, y, f'{total[i]/unit:.0f}{unit_str}', ha='left', va='center')
    plt.subplots_adjust(left=0.12, right=0.96, top=1 - 0.35 / y_size, bottom=0.55 / y_size)

    await bot.kkr_send(ev, fig)
    plt.close()
    
    msg = f"※分數統計請发送“.分數統計”"
    await bot.kkr_send(ev, msg, at_sender=True)

@cb_cmd(('分數統計', '分数统计'), ArgParser(usage='.分數統計', arg_dict={
        '': ArgHolder(tip='time',type = str, default="")}))
async def stat_score(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    now = datetime.now()
    clan = _check_clan(bm)

    yyyy, mm, _ = bm.get_yyyymmdd(now)
    if "y" in list(ev.get_param().remain) or "Y"  in list(ev.get_param().remain)  :
        stat = bm.stat_score(1, now,one_day_only=True)
    else:
        stat = bm.stat_score(1, now)
    stat.sort(key=lambda x: x[3], reverse=True)
    if not len(stat):
        await bot.kkr_send(ev, f"{clan['name']}{yyyy}年{mm}月會戰統計數據為空", at_sender=True)
        return

    # msg = [ f"\n{yyyy}年{mm}月會戰{clan['name']}分數統計：" ]
    # for _, _, name, score in stat:
    #     score = f'{score:,d}'           # 數字太多會被騰訊ban，用逗號分隔
    #     blank = '  ' * (11-len(score))  # QQ字體非等寬，width(空格*2) == width(數字*1)
    #     msg.append(f"{blank}{score}分 | {name}")

    # generate statistic figure
    fig, ax = plt.subplots()
    score = list(map(lambda i: i[3], stat))
    yn = len(stat)
    name = list(map(lambda i: i[2], stat))
    y_pos = list(range(yn))

    if score[0] >= 1e8:
        unit = 1e8
        unit_str = 'e'
    else:
        unit = 1e4
        unit_str = 'w'

    y_size = 0.3 * yn + 1.0
    fig.set_size_inches(10, y_size)
    bars = ax.barh(y_pos, score, align='center')
    ax.set_title(f"{clan['name']}{yyyy}年{mm}月會戰分數統計")
    ax.set_yticks(y_pos)
    ax.set_yticklabels(name)
    ax.set_ylim((-0.6, yn - 0.4))
    ax.invert_yaxis()
    ax.set_xlabel('分數')
    ax.ticklabel_format(axis='x', style='plain')
    for rect in bars:
        w = rect.get_width()
        ax.text(w, rect.get_y() + rect.get_height() / 2, f'{w/unit:.2f}{unit_str}', ha='left', va='center')
    plt.subplots_adjust(left=0.12, right=0.96, top=1 - 0.35 / y_size, bottom=0.55 / y_size)
    await bot.kkr_send(ev, fig)
    plt.close()
    msg = f"※傷害統計請发送“.傷害統計”"
    await bot.kkr_send(ev, msg, at_sender=True)


async def _do_show_remain(bot:KokkoroBot, ev:EventInterface, args:ParseResult, at_user:bool):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    uid  = ev.get_author_id()
    _check_member(bm, uid, bm.group)

    if at_user:
        _check_admin(ev, '才能催刀。您可以用【.查刀】查詢余刀')
    rlist = bm.list_challenge_remain(1, datetime.now() - timedelta(days=args.get('D', 0)))
    rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
    msg = [ f"\n{clan['name']}今日余刀：" ]
    sum_remain = 0
    sum_compen = 0
    for uid, _, name, r_n, r_e in rlist:
        if r_n or r_e:
            msg.append(f"剩{r_n}刀 補時{r_e}刀 | {bot.kkr_at(uid) if at_user else name}")
            sum_remain += r_n
            sum_compen += r_e
    
    if len(msg) == 1:
        await bot.kkr_send(ev, f"今日{clan['name']}所有成員均已下班！各位辛苦了！", at_sender=True)
    else:
        msg.append(f'剩余{sum_remain}正刀 | 剩余{sum_compen}補償')
        msg.append('若有負數說明報刀有誤 請注意核對\n使用“.出刀記錄 @id”可查看詳細記錄')
        if at_user:
            msg.append("=========\n在？阿sir喊你出刀啦！")
        await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
        if at_user:
            await bot.kkr_send(ev, R.img('priconne/催刀.jpg'))


@cb_cmd(('查刀', 'list-remain'), ArgParser(usage='.查刀', arg_dict={
        'D': ArgHolder(tip='日期差', type=int, default=0)}))
async def list_remain(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    await _do_show_remain(bot, ev, args, at_user=False)
@cb_cmd(('催刀', 'urge-remain'), ArgParser(usage='.催刀'))
async def urge_remain(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    await _do_show_remain(bot, ev, args, at_user=True)


@cb_cmd(('出刀記錄', '出刀记录','d'), ArgParser(usage='.出刀記錄 (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0),
        'D': ArgHolder(tip='日期差', type=int, default=0)}))
async def list_challenge(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    def divide_chunks(l, n):
        for i in range(0, len(l), n): 
            yield l[i:i + n]
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    uid  =  ev.get_author_id()
    _check_member(bm, uid, bm.group)
    now = datetime.now() - timedelta(days=args.D)
    zone = bm.get_timezone_num(clan['server'])
   # zone= "TZ"
    print( zone  )
    uid = args['@'] or args.uid
    if uid:
        mem = _check_member(bm, uid, bm.group, '公會內無此成員')
        challen = bm.list_challenge_of_user_of_day(mem['uid'], mem['alt'], now, zone)
    else:
        challen = bm.list_challenge_of_day(clan['cid'], now, zone)

    msg = [ f'{clan["name"]}出刀記錄：\n編號|出刀者|周目|Boss|傷害|標記' ]
    challenstr = 'E{eid:0>3d}|{name}|r{round}|b{boss}|{dmg:d}{flag_str}'
   # print( challen  )
    for c in challen:
       # print(   c['uid'] )
        mem = bm.get_member(c['uid'], c['alt'])
        c['name'] = mem['name'] if mem else c['uid']
        flag = c['flag']
        c['flag_str'] = '|' + ','.join(BattleMaster.damage_kind_to_string(flag))
        msg.append(challenstr.format_map(c)) 
    a = list(divide_chunks( msg,50   ))    
  #  print(a) 
    for _ in a :
        await bot.kkr_send(ev, '\n'.join(_))


@cb_cmd(('舊合刀計算', '舊補償刀計算', '舊boss-slayer'), ArgParser(usage='.補償刀計算 50w 60w', arg_dict={'': ArgHolder(tip='傷害'),
        'B': ArgHolder(tip='boss', type=int, default=0)})) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def boss_slayer(bot, ev: EventInterface, args: ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    if clan['server'] == BattleMaster.SERVER_CN:
        servertag = '**國服合刀**'
        ext0 = 100
    else:
        servertag = '**日服/台服合刀**'
        ext0 = 110 # 日服補償刀20秒起

    remain = ev.get_param().remain
    prm = re.findall("\d+[wW萬]", remain)
    if len(prm) == 2:
        dmg1 = int(prm[0][:-1]) * 10000
        dmg2 = int(prm[1][:-1]) * 10000
    else:
        prm = re.findall("\d+", remain)
        if len(prm) == 2:
            dmg1 = int(prm[0])
            dmg2 = int(prm[1])
        else:
            usage = "【用法/用例】\n!補償刀計算 50w 60w"
            await bot.kkr_send(ev, usage, at_sender=True)
            return
    boss =args.get("B")        
    real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
    r = real_r[int(boss)-1]
    b =boss 
    hp = remain_hp_list[int(boss)-1]

    if dmg1 + dmg2 < hp:
        msg = '0x0 這兩刀合起來還打不死BOSS喔'
    else:
        if dmg1 >= hp and dmg2 >= hp:
            ans1 = f'先出{dmg1:,}，BOSS直接就被打死啦'
            ans2 = f'先出{dmg2:,}，BOSS直接就被打死啦'
        elif dmg1 >= hp and dmg2 < hp:
            ans1 = f'先出{dmg1:,}，BOSS直接就被打死啦'
            ext2 = min(math.ceil(ext0-((hp-dmg2)/dmg1)*90), 90)
            ans2 = f'先出{dmg2:,}再出{dmg1:,}，返還時間{ext2}秒'
        elif dmg1 < hp and dmg2 >= hp:
            ext1 = min(math.ceil(ext0-((hp-dmg1)/dmg2)*90), 90)
            ans1 = f'先出{dmg1:,}再出{dmg2:,}，返還時間{ext1}秒'
            ans2 = f'先出{dmg2:,}，BOSS直接就被打死啦'
        else:
            ext1 = min(math.ceil(ext0-((hp-dmg1)/dmg2)*90), 90)
            ans1 = f'先出{dmg1:,}再出{dmg2:,}，返還時間{ext1}秒'
            ext2 = min(math.ceil(ext0-((hp-dmg2)/dmg1)*90), 90)
            ans2 = f'先出{dmg2:,}再出{dmg1:,}，返還時間{ext2}秒'

        not_my_fault = "計算結果僅供參考，可能與遊戲內實際返還時間有偏差"
        msg = '\n'.join([servertag, ans1, ans2, not_my_fault])
    await bot.kkr_send(ev, msg, at_sender=False)


@cb_cmd(('算全返','算全返'), ArgParser(usage='.算全返 1000w', arg_dict={
    '': ArgHolder(tip='傷害')})) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def calculate_90s(bot, ev: EventInterface, args: ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    remain = ev.get_param().remain
    prm = re.findall("\d+[wW萬]", remain)
    if len(prm)>1 :   
        usage = "【用法/用例】\n.算全返 王現在血量"
        await bot.kkr_send(ev, usage, at_sender=True)
        return
    ex_hp = int(prm[0][:-1]) * 10000    
    dmg_need = ex_hp*4.3
    dmg_need = "{:,}".format(dmg_need)
    ans0 =  f'假設現在王血是{ex_hp},需要{dmg_need}才能全返'
    await bot.kkr_send(ev, ans0, at_sender=False)

@cb_cmd(('算補償','算补偿'), ArgParser(usage='.算補償 50w 60w 1000W B王編號', arg_dict={
    '': ArgHolder(tip='傷害')})) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def boss_slayer2(bot, ev: EventInterface, args: ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)

    if clan['server'] == BattleMaster.SERVER_CN:
        servertag = '**國服合刀**'
        ext0 = 100
    else:
        servertag = '**日服/台服合刀**'
        ext0 = 110 # 日服補償刀20秒起

    remain = ev.get_param().remain
    prm = re.findall("\d+[wW萬]", remain)

    if len(prm)>3 :   
        usage = "【用法/用例】\n.算補償 50w 60w 1000W"
        await bot.kkr_send(ev, usage, at_sender=True)
        return
    if len(prm) ==2 :
        dmg1 = int(prm[0][:-1]) * 10000
        ex_hp = int(prm[1][:-1]) * 10000
        if dmg1 >=  ex_hp:
            ex_compens = str(min( round(90- ex_hp/(dmg1/90) +20),90))
        else:
            ex_compens = 0  
        ans1 = f'返還時間{ex_compens}秒'
        ans0 =  f'假設現在王血是{ex_hp}, 你打了{dmg1}'
        not_my_fault = "計算結果僅供參考，可能與遊戲內實際返還時間有偏差"
        msg = '\n'.join([servertag, ans0,ans1,not_my_fault])
    if len(prm)>2 and len(prm) <=3 :   
        dmg1 = int(prm[0][:-1]) * 10000
        dmg2 = int(prm[1][:-1]) * 10000
        ex_hp = int(prm[2][:-1]) * 10000
        hp = ex_hp
        print( dmg1,  dmg2, ex_hp   )
        if dmg1 + dmg2 < hp:
            msg = '0x0 這兩刀合起來還打不死BOSS喔'
        else:
            if dmg1 >= hp and dmg2 >= hp:
                ans1 = f'先出{dmg1:,}，BOSS直接就被打死啦'
                ans2 = f'先出{dmg2:,}，BOSS直接就被打死啦'
            elif dmg1 >= hp and dmg2 < hp:
                ans1 = f'先出{dmg1:,}，BOSS直接就被打死啦'
                ext2 = min(math.ceil(ext0-((hp-dmg2)/dmg1)*90), 90)
                ans2 = f'先出{dmg2:,}再出{dmg1:,}，返還時間{ext2}秒'
            elif dmg1 < hp and dmg2 >= hp:
                ext1 = min(math.ceil(ext0-((hp-dmg1)/dmg2)*90), 90)
                ans1 = f'先出{dmg1:,}再出{dmg2:,}，返還時間{ext1}秒'
                ans2 = f'先出{dmg2:,}，BOSS直接就被打死啦'
            else:
                ext1 = min(math.ceil(ext0-((hp-dmg1)/dmg2)*90), 90)
                ans1 = f'先出{dmg1:,}再出{dmg2:,}，返還時間{ext1}秒'
                ext2 = min(math.ceil(ext0-((hp-dmg2)/dmg1)*90), 90)
                ans2 = f'先出{dmg2:,}再出{dmg1:,}，返還時間{ext2}秒'
            ans0 =  f'假設現在是王血是{hp}'
            not_my_fault = "計算結果僅供參考，可能與遊戲內實際返還時間有偏差"
            msg = '\n'.join([servertag, ans0,ans1, ans2, not_my_fault])

    await bot.kkr_send(ev, msg, at_sender=False)


## 0 = 通常, 1 = 尾刀 , 2 = 補時 , 3= 補時,尾刀 , 4= 掉線

@cb_cmd(('修改', 'amend'), ArgParser(usage='.修改 E030 D300000 R20 B2 F2 (@id)', arg_dict={
    'D': ArgHolder(tip='傷害值', type=damage_int),
    'E': ArgHolder(tip='eid'),
    '@': ArgHolder(tip='id', type=str, default=0),
    'R': ArgHolder(tip='周目數', type=round_code, default=0),
    'B': ArgHolder(tip='Boss編號', type=boss_code, default=0),
    'F': ArgHolder(tip='通常/尾刀', type=str)}))
async def mod_challenge(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    _check_admin(ev)
    bm = BattleMaster(ev.get_group_id())
    uid = args['@'] 
    now = datetime.now()
    clan = _check_clan(bm)
    if args.get('D') == 0 :
        max_hp, score_rate = bm.get_boss_info(args.R, args.B, clan['server'])
        input_hp = max_hp
    else:
        input_hp = args.get('D')     
    bm.mod_challenge(args.E, uid, ev.get_group_id(), args.R, args.B, input_hp, args.F,now)
    msg = f'記錄已被修改,可使用 .出刀記錄查看' 
    await bot.kkr_send(ev, msg, at_sender=True)
    
@cb_cmd(('SL', 'sl'), ArgParser('.SL (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0)}))
async def add_SL(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid  = args['@'] or ev.get_author_id()
    clan = _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    SL = sub.get_SL_list()
    if uid in SL:
        raise AlreadyExistError("您已用了SL")
    sub.add_sl(uid)
    ### if sl , remove from inlist
    LN = sub.get_in_list()
    for every_key in LN:
        if uid in LN[every_key]:
            del LN[every_key][uid]
    ### if sl , remove from treelist
    tree = sub.get_tree_list()
    for every_key in tree:
        if uid in tree[every_key]:
            tree[every_key].remove(uid)
           # del tree[every_key][uid]
    _save_sub(sub, dt_string)
    msg = [ "\n您已用了SL,同時由篩刀大會移去名單",
           f"目前{clan['name']}用了SL人數為{len(SL)}人：" ]
    msg.extend(_gen_namelist_text(bot, bm, SL))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
    await check_inList(bot, ev)


@cb_cmd(('查SL', '查sl','check-sl'), ArgParser('.查SL'))
async def list_SL(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    SL = sub.get_SL_list()
    msg = [ f"\n目前{clan['name']}申請了SL人數為{len(SL)}人：" ]
    msg.extend(_gen_namelist_text(bot, bm, SL))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)

@cb_cmd(('刪SL','刪sl','删SL'), ArgParser('.刪SL (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0)}))
async def del_SL(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    uid  = args['@'] or ev.get_author_id()
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    SL = sub.get_SL_list()
    if uid in SL:
        SL.remove(uid)
        _save_sub(sub, dt_string)
        msg = [ f"你已刪除了SL記錄" ]
    else:
        raise AlreadyExistError("您未使用SL")
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)


@cb_cmd(('查進', 'list'), ArgParser(usage='.查進', arg_dict={
    '': ArgHolder(tip='boss', type=str, default=0)}))
async def check_inList2(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    boss = args.get('')
    await check_inList(bot, ev,boss)  

@cb_cmd(('進', '1','进'), ArgParser(usage='.進 王編號 (@id)',  arg_dict={
        '': ArgHolder(tip='boss', type=str),
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def add_Lnlist(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    uid = args['@'] or ev.get_author_id()
    mems =  _check_member(bm, uid, bm.group)
    details = list(str(ev.get_param().remain).split(' '))
    boss = str(details[0])
    if boss not in ['1','2','3','4','5'] :
        raise NotFoundError('王編號必須在1至5之間')
    find_list = ['a','b','c',"A","B",'C']
    in_chanlleng = set(find_list) & set(details)
    in_chanlleng =list(in_chanlleng)
   # if len(in_chanlleng) ==0 and len(details) >1:
     #   raise NotFoundError('補償刀編號必須是a,b,c其一')
    now  = datetime.now() 
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    LN = sub.get_in_list()
    SL = sub.get_SL_list()
    tree = sub.get_tree_list()
    sub.clear_tree_sep(uid)
    real_r, remain_hp_list= bm.get_challenge_progress_all_boss(1, datetime.now())
    if remain_hp_list[ int(boss) -1 ] <=0:
        raise NotFoundError("這王已死") 
    ### del tree 
    if len(in_chanlleng) !=0 :
        await list_Compen(bot, ev,uid,print_out=False)
        await check_compen(bot, ev,uid,str(in_chanlleng[0]))
        in_chanlleng = "補償" +str(in_chanlleng[0])
    else:
        in_chanlleng= "正刀"    
    alt = ev.get_group_id()
    rlist = bm.list_challenge_remain(1, datetime.now() - timedelta(days=args.get('D', 0)))
    rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
    dmg = in_chanlleng
        
    for _ in rlist:
        if uid in _ :
            if int(_[-2]) <=0 and in_chanlleng== "正刀"  :
                raise NotFoundError("你已經沒正刀 不能用正刀進") 
            if int(_[-1]) <=0 and '補償' in in_chanlleng  :
                raise NotFoundError("你已經沒補償 不能用補償進") 
            main_chall = str(_[-2])
            time_chall = str(_[-1])
            remain_chall =   str(main_chall+"正" + " "+  time_chall+"補" ) 

    if uid in SL:
        sl_ = "沒SL"
    else:
        sl_= "有SL"   
    
    sub.add_in(uid,sl_,str(remain_chall ),dmg,boss,in_chanlleng)
    _save_sub(sub,dt_string)
    msg = [ f"\n成功進了{boss}王, 請卡好秒, 目前已有{len(LN[boss])}人進了：",
           f"\n{mems['name']}使用了【{in_chanlleng}】",
           f"\n補償刀詳細如下:"]              
    await bot.kkr_send(ev, '\n'.join(msg))       
    await list_Compen(bot, ev,uid)
    await check_inList(bot, ev,boss)          
    

@cb_cmd(('報', '2','报'), ArgParser(usage='.報 傷害xxx (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0),
        '': ArgHolder(tip='傷害值')}))
async def report_inList(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    dmg = args.get('')
    LN = sub.get_in_list()
    uid = args['@'] or ev.get_author_id()
    _check_member(bm, uid, bm.group)
    have_key = False

    for every_key in LN:
        if uid in LN[every_key]:
            LN[every_key][uid][-2] = dmg
            _save_sub(sub, dt_string)
            have_key = True
            boss = every_key
    if not have_key:
        raise NotFoundError("你沒有進任何一王")
    
  #  _save_sub(sub, dt_string)
    await bot.kkr_send(ev, '成功更改了傷害值', at_sender=True)
    await check_inList(bot, ev,boss) 


@cb_cmd(('退', 'report-inlist'), ArgParser(usage='.退 (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def quit_LNlist(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    LN = sub.get_in_list()
    uid = args['@'] or ev.get_author_id()
    _check_member(bm, uid, bm.group)
    tree = sub.get_tree_list()
    sub.clear_tree_sep(uid)

    have_key = False
    
    for every_key in LN:
        if uid in LN[every_key]:
            del LN[every_key][uid]
            _save_sub(sub, dt_string)
            await bot.kkr_send(ev, '你已退了篩刀大會', at_sender=True)
            have_key = True
    if not have_key:
        raise NotFoundError("你沒有進任何一王")

   # await check_inList(bot, ev) 

@cb_cmd(('清', 'report-inlist'), ArgParser(usage='.清', arg_dict={
       '': ArgHolder(tip='boss', type=str, default=0)}))
async def list_LNlist(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    _check_admin(ev)
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    LN = sub.get_in_list()
    msg= []
    boss = args.get('')
    if boss in LN:
        del LN[boss]  
        _save_sub(sub,dt_string )

    await bot.kkr_send(ev, f'{boss}王篩刀大會清空', at_sender=True)  # do not at the sender


@cb_cmd(('shift', '移軸','移轴'), ArgParser(usage='.shift', arg_dict={
        '': ArgHolder(tip='time')}))
async def shift(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    compensate_time =  args.get('')
    len_of_com = len(  compensate_time )
    split_compensate_time = compensate_time.split(":")
    full_time = 90
    diff_time = timedelta(seconds=full_time) -timedelta(minutes=int(split_compensate_time[0]), seconds = int(split_compensate_time[1])) 
    remain = str(ev.get_param().remain)
    remain = remain[len_of_com+1:]
    msg = []

    for _ in remain.splitlines():
        org_time_list = re.findall(r'[0-1][:\.]?[0-5]\d',str(_))
        for org_time in org_time_list:
            org_time= str(org_time)
            format_org_time = org_time.replace(":","").replace(".","")
            if  diff_time <  timedelta(minutes=int(format_org_time[0]), seconds = int(format_org_time[1:]))    :
                after_time = timedelta(minutes=int(format_org_time[0]), seconds = int(format_org_time[1:])) - diff_time
                _ = _.replace(  org_time,   str(after_time)[3:]  )
            if  diff_time >=  timedelta(minutes=int(format_org_time[0]), seconds = int(format_org_time[1:]))    : 
                _=""  
                break            
        if _!="":
            msg.append(  _  )             
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)    # do not at the sender    
        

async def list_Compen(bot:KokkoroBot, ev:EventInterface,args:ParseResult,print_out=True):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    uid  = args
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y") + " "+ clan['gid']
    sub = _load_sub(dt_string)
    compen = sub.get_compen_list()
    if uid !=0 :
        compen = dict((key,value) for key, value in compen.items() if key == uid)
   # print( compen )    
    rlist = bm.list_challenge_remain(1, datetime.now() )
    rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
    
    ### make sure compen_dict match with challeng data
    chanlleng_dict = {}
    for _ in rlist:
        time_chall = _[-1]
        if time_chall != 0 : 
            uid_key = _[0]
            chanlleng_dict[uid_key] = time_chall  ### real 
  
    compen_deep = copy.deepcopy(compen)
    ###if real comp > list 
    for compen_key in chanlleng_dict.keys():
        try :
            if len( compen_deep[compen_key]  ) < chanlleng_dict[compen_key] : 
                length = len( compen_deep[compen_key]  ) 
                diff = int(chanlleng_dict[compen_key]) - length
                for _ in range(0,diff):
                    sub.add_compen(compen_key, '沒有具體資料')
                    _save_sub(sub, dt_string)
        except:
            if uid ==0 :
                diff = int(chanlleng_dict[compen_key]) - 0
                for _ in range(0,diff):
                    sub.add_compen(compen_key, '沒有具體資料')
                    _save_sub(sub, dt_string)
     ###if real comp < list  
    for compen_key in compen_deep.keys():
        try:
            if compen_key not in chanlleng_dict:
                chanlleng_dict_len =  0 
            else:
                chanlleng_dict_len =  chanlleng_dict[compen_key]    
            print(compen_key, 'chanlleng_dict_len', chanlleng_dict_len)    
            if  len( compen_deep[compen_key]  ) > chanlleng_dict_len :     
                length = len( compen_deep[compen_key]  ) 
                diff = length - int(chanlleng_dict_len)
                for _ in range(0,diff):
                    sub.del_redu_compen(compen_key)
                    _save_sub(sub, dt_string)           
        except:
            pass                         
    ### output
    whole_msg = [  ]
    for compen_key in compen.keys():
        mems = _check_member(bm, compen_key, bm.group)
        msg = [ f"{mems['name']}" ]
        boss_num_list =[]
        details_list =[]
        for second_key in compen[compen_key].keys():
            boss_num_list.append(f'補償編號{second_key}')
            details_list.append(compen[compen_key][second_key])
        if  boss_num_list :    
            msg.extend(_gen_namelist_text(bot, bm, boss_num_list,details_list))    
            msg.append("-------------------------------")   
            whole_msg.append( msg   )
    if print_out == True:        
        if uid !=0  and (not compen or not boss_num_list) :
            await bot.kkr_send(ev, '你沒有補償')  
        else:    
            try:
                flat_list  = [item for sublist in whole_msg for item in sublist]
                await bot.kkr_send(ev, '\n'.join(flat_list))  
            except:
                await bot.kkr_send(ev, '沒有補償')  


async def check_compen(bot:KokkoroBot, ev:EventInterface,uid,compen_id):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y") + " "+ clan['gid']
    sub = _load_sub(dt_string)
    compen = sub.get_compen_list()
    if uid not in compen: 
        raise NotFoundError("你沒有補償")
       # await list_Compen(bot, ev,uid) 
    if uid in compen: 
        if compen_id not in compen[uid]:
            await list_Compen(bot, ev,uid) 
            raise NotFoundError( f'你沒有補償{compen_id}'  )
           #     return f"你沒有補償{compen_id}"


async def del_comp(bot:KokkoroBot, ev:EventInterface,uid,boss):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    compen = sub.get_compen_list()

    await check_compen(bot, ev,uid,str(boss))
    
    if uid in compen:
        del compen[uid]
        _save_sub(sub, dt_string)
        await bot.kkr_send(ev, '你已刪除了補償', at_sender=True)
  #  await list_Compen(bot, ev)

@cb_cmd(('查補償','查補','查补偿','查补'), ArgParser('.查補 (@id)', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0)}))
async def list_Compen2(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    uid = args['@'] 
    await list_Compen(bot, ev,uid)  


@cb_cmd(('改補', '改補償','改补','改补偿'), ArgParser(usage='.改補 補償編號 details (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0),
        '': ArgHolder(tip='秒數', type=str, default=0)}))
async def report_compen(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    clan = _check_clan(bm)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    remain_list = list(str(ev.get_param().remain).split(' '))
    boss = remain_list[0]
    if boss not in ['a','b','c',"A","B",'C'] :
        raise NotFoundError(f'參考格式 : .改補 補償編號 details (@id) ')   
    details = remain_list[1]
    compen = sub.get_compen_list()
    uid = args['@'] or ev.get_author_id()
    _check_member(bm, uid, bm.group)
    await check_compen(bot, ev,uid,str(boss))

    if uid in compen:
        compen[uid][boss] = details
    _save_sub(sub, dt_string)
    await bot.kkr_send(ev, '成功更改了', at_sender=True)
    await list_Compen(bot, ev,uid) 
  
@cb_cmd(('刪補償','刪補','删补偿','删补'), ArgParser('.刪補 (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0),
        '': ArgHolder(tip='補償編號', type=str, default=0)}))
async def del_comp2(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    uid = args['@'] or ev.get_author_id()
    boss  = args['']
    await del_comp(bot, ev,uid,boss) 


async def download_excel(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    dls = "https://docs.google.com/spreadsheets/d/1ik2Ug5obEj2Jii0sEHPZnU2sjYh5f0YtaHojaz205Hw/export?format=xlsx"
    SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/clanbattle_sub/')
    urllib.request.urlretrieve(dls, SUBSCRIBE_PATH+ "三杯練度表.xlsx")  # For Python 3
    filename = os.path.join(SUBSCRIBE_PATH, '三杯練度表.xlsx')
    class Vividict(dict):
        def __missing__(self, key):
            value = self[key] = type(self)()
            return value
    def get_data(file_name,member= False ):
        princess_pd = pd.read_excel(file_name)
        detail_data = pd.read_excel(file_name, skiprows=[0])
        if member:
            princess_pd =  princess_pd[princess_pd['DC ID'].notnull()]    
            detail_data =  detail_data[detail_data['Unnamed: 1'].notnull()]  
            princess_pd['DC ID'] = princess_pd['DC ID'].astype('int').apply(lambda x: '{:d}'.format(x))
           # detail_data['Unnamed: 1'] = detail_data['Unnamed: 1'].astype('int').apply(lambda x: '{:d}'.format(x))
            detail_data['Unnamed: 1'] = detail_data['Unnamed: 1'].apply(str)
            princess_pd.set_index("DC ID",inplace =True)
            detail_data.set_index("Unnamed: 1",inplace =True)
            character_list = [  x for x in list(princess_pd.columns) if x not in ['角色練度調查' ]    if 'Unnamed' not in x ]
            member_list = [ x for x in list(detail_data.index.values)  if str(x) != 'nan' ]
        del detail_data['戰隊成員']    
        detail_data = detail_data.loc[:,~detail_data.columns.str.startswith('Unname')]  
        return  detail_data,character_list,member_list
    def create_dict(detail_data,character_list, member_list, boss=False):
        whole_dict =   Vividict()
        char_length = len( character_list  )
        char_num = 0
        if boss :
            beginng_value =2
        else:
            beginng_value =0
        for _ in range(beginng_value,len(detail_data.columns),3):
        # print(_)
            if char_num <  char_length :
                    for member in member_list:
                        if boss:
                            whole_dict[member]['血量']=detail_data.iloc[:, 0][member] 
                            whole_dict[member]['標準傷害']=detail_data.iloc[:, 1][member] 
                            whole_dict[member]['一刀']=whole_dict[member]['標準傷害']/whole_dict[member]['血量']
                        if not pd.isnull(detail_data.iloc[:, _][member] ) :
                            whole_dict[member][character_list[char_num]]['星數']=str(detail_data.iloc[:, _][member])
                            try:
                                whole_dict[member][character_list[char_num]]['RANK']=detail_data.iloc[:, _+1][member].strftime("%m-%#d")
                            except:
                                whole_dict[member][character_list[char_num]]['RANK']=str(detail_data.iloc[:, _+1][member])
                            whole_dict[member][character_list[char_num]]['專武']=str(detail_data.iloc[:, _+2][member] )
                        
                    char_num = char_num +1   

        return whole_dict    
    detail_data,character_list,member_list = get_data(filename ,member=True   )     
    index_list =  list(range(1, len(character_list    )))
    index1 = character_list.index("前衛")
    index2 = character_list.index("中衛")
    index3 = character_list.index("後衛")
    character_list.remove('前衛')
    character_list.remove('中衛')
    character_list.remove('後衛')
    whole_pp_dict = create_dict(detail_data,character_list,member_list    )
    character_list.insert(index1,'━━━━━━━━━━━━━━━')
    index_list.insert(index1,'')
    character_list.insert(index2,'━━━━━━━━━━━━━━━')
    index_list.insert(index2,'')
    character_list.insert(index3,'━━━━━━━━━━━━━━━')
    index_list.insert(index3,'')
    charcter_dict = dict(zip(index_list, character_list))
    filename = os.path.join(SUBSCRIBE_PATH, "charcter_dict.json")
    del charcter_dict['']
    with open(filename ,'w') as fp:
        json.dump(charcter_dict, fp,ensure_ascii=False)
    filename = os.path.join(SUBSCRIBE_PATH, "member_dict.json")
    with open(filename, 'w') as fp:
        json.dump(whole_pp_dict, fp,ensure_ascii=False)
    filename = os.path.join(SUBSCRIBE_PATH, "character_list.json")
    with open(filename, 'w') as fp:
        json.dump(character_list, fp,ensure_ascii=False)    
    filename = os.path.join(SUBSCRIBE_PATH, "index_list.json")    
    with open(filename, 'w') as fp:
        json.dump(index_list, fp,ensure_ascii=False)       

@cb_cmd(('查角色'), ArgParser('.查角色', arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0)}))
async def check_char(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    pd.options.display.float_format = '{:.0f}'.format
    bm = BattleMaster(ev.get_group_id())
    await download_excel(bot,ev,args)
    filename = os.path.join(SUBSCRIBE_PATH, 'character_list.json')
    with open(filename) as json_file:
        character_list = list(json.load(json_file))
    filename = os.path.join(SUBSCRIBE_PATH, 'index_list.json')    
    with open(filename) as json_file:
        index_list = list(json.load(json_file))    
    msg = []
    msg.extend(_gen_namelist_text(bot, bm, character_list,index_list))
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=False)   

    
async def list_practice(bot:KokkoroBot, ev: EventInterface):
    bm = BattleMaster(ev.get_group_id())
    SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/clanbattle_sub/')
    filename = os.path.join(SUBSCRIBE_PATH, 'practice_dict.json')
    if os.path.exists(filename):
        with open(filename) as json_file:
            practice_dict = json.load(json_file)
            msg = ['作業名，stage，角色，標準傷害 \n ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━']
            msg.extend(_gen_namelist_text(bot, bm, list(practice_dict.keys()),list(practice_dict.values())))
            await bot.kkr_send(ev, '\n'.join(msg), at_sender=False)  

    else:
        raise NotFoundError(f'Error: 目前沒有作業,請先用.作業 ')    

@cb_cmd(('查作業','查作业'), ArgParser(usage='.查作業')) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def list_practice2(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    await list_practice(bot, ev)  


@cb_cmd(('刪作業','删作业'), ArgParser(usage='.刪作業 作業名', arg_dict={'': ArgHolder(tip='作業名')})) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def del_practice(bot, ev: EventInterface, args: ParseResult):
    bm = BattleMaster(ev.get_group_id())
    SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/clanbattle_sub/')
    filename = os.path.join(SUBSCRIBE_PATH, 'practice_dict.json')
    if os.path.exists(filename):
        with open(filename) as json_file:
            practice_dict = json.load(json_file)
            if args.get("") in practice_dict.keys():
                del practice_dict[ args.get("")  ]
                with open(filename ,'w') as fp:
                    json.dump(practice_dict, fp,ensure_ascii=False)
                await bot.kkr_send(ev,'成功刪除', at_sender=True)    
                await list_practice(bot, ev) 
            else:
                raise NotFoundError(f'Error: 沒有{args.get("")}這個作業')            
    else:
        raise NotFoundError(f'Error: 目前沒有作業,請先用.作業 ')   


@cb_cmd(('作業','作业'), ArgParser(usage='.作業 作業名 D4 角色號碼1[R14+,3星] 角色號碼2 角色號碼3 角色號碼4 角色號碼5 標準傷害', arg_dict={'': ArgHolder(tip='傷害')})) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def practice(bot, ev: EventInterface, args: ParseResult):
    class Vividict(dict):
        def __missing__(self, key):
            value = self[key] = type(self)()
            return value
    bm = BattleMaster(ev.get_group_id())
    remain_list = list(str(ev.get_param().remain).split(' '))
    SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/clanbattle_sub/')
    filename = os.path.join(SUBSCRIBE_PATH, 'charcter_dict.json')
    with open(filename) as json_file:
        charcter_dict = json.load(json_file)
    filename = os.path.join(SUBSCRIBE_PATH, 'practice_dict.json')
    if os.path.exists(filename):
        with open(filename) as json_file:
            practice_dict = json.load(json_file)
    else:
        practice_dict =Vividict()

    for _ in range(2,7) :
        try:
            chr_num_index = remain_list[_] .index('[')
            chr_num   =  remain_list[_][ :chr_num_index]
            if chr_num in charcter_dict :
               remain_list[_] =  charcter_dict[str(chr_num)] +  remain_list[_][chr_num_index:]   
            else:
                raise NotFoundError(f'Error: 角色編號有錯,沒有{chr_num}這編號,請用.查角色看編號')   
        except:
            if  remain_list[_] in charcter_dict :
                   remain_list[_] =  charcter_dict[str( remain_list[_])]   
            else:
                raise NotFoundError(f'Error: 角色編號有錯,沒有{remain_list[_]}這編號,請用.查角色看編號')       
    if   remain_list[0] in   practice_dict :
         raise NotFoundError(f'Error: 已有同名的作業，請用另一個名字')
    else:
        practice_dict[remain_list[0]] = remain_list[1:]
    with open(filename ,'w') as fp:
        json.dump(practice_dict, fp,ensure_ascii=False)
    msg = f'成功加入了作業{remain_list}'
    await bot.kkr_send(ev,msg, at_sender=True) 
   
@cb_cmd(('查組合','查组合'), ArgParser('.查組合 (@id)', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0),
        '': ArgHolder(tip='accruacy or not accruacy', type=str, default='N')}))
async def list_compos(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    def combos(whole_pp_dict,whole_boss_dict ,accuracy =False):
        knife_dict = Vividict()   
        for member , member_value in whole_pp_dict.items():      
            num =1  
            for combo in combinations(list(whole_boss_dict.keys()), 3):  # 2 for pairs, 3 for triplets, etc
                borrow_list =[]
                member_list = list(member_value.keys() )  
                need_list1 =  list(  whole_boss_dict[combo[0]].keys()  )[1:-1]
                need_list1 = [ x + str(  combo[0]) for x in need_list1 ]
                need_list2 =  list(  whole_boss_dict[combo[1]].keys()  )[1:-1]
                need_list2 = [ x + str(combo[1]) for x in need_list2 ]
                need_list3 =  list(  whole_boss_dict[combo[2]].keys()  )[1:-1]
                need_list3 = [ x + str(combo[2]) for x in need_list3 ]
                combo_stage =  [ str(whole_boss_dict[x]['stage']) + "-" + x  for x in combo ]
                ab = list(itertools.chain(need_list1, need_list2, need_list3))
                for _ in ab:
                    if _ in need_list1 :
                        now_combo = combo[0]
                    if _ in need_list2 : 
                        now_combo = combo[1]   
                    if _ in  need_list3 :  
                        now_combo = combo[2]
                    combo_len =len(now_combo)    
                    if  accuracy:
                        if _[:-combo_len]  in member_list:   ### have this char
                            member_star = str(whole_pp_dict[ member ][   _[:-combo_len]  ]['星數']).split(' ')[0].replace('.0','')
                            member_rank =str(whole_pp_dict[ member ][   _[:-combo_len]  ]['RANK']).split('-')[0]
                            if whole_boss_dict[now_combo][  _[:-combo_len]  ]['星數']== None or whole_boss_dict[now_combo][  _[:-combo_len]  ]['星數'] ==member_star or member_star== '5': ##star pass
                                if  whole_boss_dict[now_combo][  _[:-combo_len]  ]['RANK']== None or whole_boss_dict[now_combo][  _[:-combo_len]  ]['RANK'] ==member_rank: ##rank pass
                                    member_list.remove(_[:-combo_len])
                                else: ### if the char doesnt match rank, then borrow 
                                    borrow_list.append( _  )     
                            else: ### if the char doesnt match star, then borrow 
                                borrow_list.append( _  )                           
                        else:
                            borrow_list.append( _  ) 
                    else:           
                        if _[:-combo_len]  in member_list:
                            member_list.remove(_[:-combo_len])
                        else:
                            borrow_list.append( _  ) 
                    dupe_list = [x[-combo_len:] for x in borrow_list]    
                if len( borrow_list   )  <=3 and  len(dupe_list) == len(set(dupe_list))  :
                    knife_dict[member]["combination" + str(num)] = combo_stage
                    num =num+1
        return  knife_dict

    class Vividict(dict):
        def __missing__(self, key):
            value = self[key] = type(self)()
            return value
    await download_excel(bot,ev,args)        
    uid = args['@'] or ev.get_author_id()
    bm = BattleMaster(ev.get_group_id())
    SUBSCRIBE_PATH = os.path.expanduser('~/.kokkoro/clanbattle_sub/')
    filename = os.path.join(SUBSCRIBE_PATH, 'practice_dict.json')      
    if os.path.exists(filename):
        with open(filename) as json_file:
            practice_dict = json.load(json_file)
            amended_p_dict =Vividict()
            for Pkeys , Pvalues in practice_dict.items():
                for Pvalue in  Pvalues:
                    star = None
                    rank = None
                    weapon_lv =  None
                    char_name = Pvalue
                    if len(  Pvalue  )==2 and any(map(str.isdigit, Pvalue)) :
                        amended_p_dict[ Pkeys][ 'stage']  =   Pvalue
                        continue 
                    if  Pvalue.isdecimal() or 'w' in Pvalue or 'W' in Pvalue  :
                        amended_p_dict[ Pkeys][ 'dmg']  =   Pvalue
                        continue 
                    if "[" in Pvalue:
                        Pvalue_split =  str(Pvalue).split('[')
                        char_name = Pvalue_split[0]
                        search_word = Pvalue_split[1].replace("]",'').split(',')
                        for search_w in search_word:
                            if "R" in search_w:
                                rank = search_w.replace("R",'')
                            if "星"   in search_w: 
                                star = search_w.replace("星",'')
                            if "專"   in search_w: 
                                weapon_lv = search_w.replace("專",'')    
                    amended_p_dict[ Pkeys][char_name]['星數']  =   star
                    amended_p_dict[ Pkeys][char_name]['RANK']  =   rank
                    amended_p_dict[ Pkeys][char_name]['專武']  =   weapon_lv  
            ### loop combination 
            filename = os.path.join(SUBSCRIBE_PATH, 'member_dict.json')   
            with open(filename) as json_file:
                member_dict = json.load(json_file)  
            mems = _check_member(bm, uid, bm.group)    
            if "y" in list(ev.get_param().remain) or "Y"  in list(ev.get_param().remain)    :
                knife_dict =   combos(member_dict,amended_p_dict , accuracy =True )  
                msg = [ f"\n根據{mems['name']}在練度表的輸入，考慮你有該角色和符合作業星數、rank，在不卡角的情況下，可以打以下組合" ]
            else:
                knife_dict =   combos(member_dict,amended_p_dict , accuracy =False ) 
                msg = [ f"\n根據{mems['name']}在練度表的輸入，只考慮你有該角色和在不卡角的情況下，可以打以下組合" ]
          #  if  any(str( uid)[:-3] in string for string in list(member_dict.keys())):
            if uid in member_dict.keys() :
                msg.extend(_gen_namelist_text(bot, bm, list(knife_dict[str( uid)].keys()  ), list(knife_dict[str( uid)].values())))
                await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)
            else:
               raise NotFoundError(f'Error: 三杯兔練度表沒有這個人')                    
    else:
        raise NotFoundError(f'Error: 目前沒有作業,請先用.作業 ')    
    


async def get_cookies(url, **kwargs):
    async with httpx.AsyncClient() as client:
        r = await client.get(url, **kwargs)
        return r.cookies

async def post(url, **kwargs):
    async with httpx.AsyncClient() as client:
        r = await client.post(url, **kwargs)
        return r.json()



@cb_cmd('排名', ArgParser(
    usage='.排名'))
async def clan_rank(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
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
        await bot.kkr_send(ev, fig)
        plt.close()   
    except:
        await bot.kkr_send(ev, f'https://kyaru.infedg.xyz/tw 沒有{date_time} {hour_round} 數據')       

#### 出刀時間統計 ###

def get_ym():
    now = datetime.now()
    year = now.year
    month = now.month
    day = now.day
    if day < 20:
        month -= 1
    if month == 0:
        year -= 1
        month = 12
    return year,month

async def send_time_dist(bot: KokkoroBot, event: EventInterface,uid=None):
    gid = event.get_group_id()
    year,month = get_ym()
  
    try:
        name,times = get_time(gid,year,month,uid)
    except Exception as e:
        await bot.kkr_send(event, f"出現錯誤: {str(e)}\n請聯系開发組調教。")
        return

    plt.rcParams['axes.unicode_minus']=False
    FONT_PATH = kokkoro.config.FONT_PATH["msyh"]
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

@cb_cmd(('出刀時間統計', '出刀時間統計'), ArgParser(usage=USAGE_ADD_MEMBER, arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def send_chal_stat(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    uid = args['@']
    await send_time_dist(bot, ev,uid)

@cb_cmd(('排刀', '尾盤','尾盘'), ArgParser(usage=USAGE_ADD_MEMBER, arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0),
    '': ArgHolder(tip='boss dmg notes', type=str, default='')}))
async def add_queue(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid  = args['@'] or ev.get_author_id()
    clan = _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    queue = sub.get_queue_list()
    remain_list = list(str(ev.get_param().remain).split(' '))
    if len( remain_list  ) <2 :
        raise NotFoundError('請根據格式 .排刀 王編號 傷害 (@id)')
    boss = str(remain_list[0])
    if boss not in ['1','2','3','4','5'] :
        raise NotFoundError('王編號必須在1至5之間')
    dmg = str(remain_list[1])
    ifnum = any(chr.isdigit() for chr in dmg)
    if not ifnum:
        raise NotFoundError('必須提供傷害值 e.g1000法刀')
    ### check if remain chall > queue ###
    already_queue = 0
    for details in queue :
        if uid == details[0] :
                already_queue = already_queue +1 
    ### remain 
    rdict= {}
    rlist = bm.list_challenge_remain(1, datetime.now() - timedelta(days=args.get('D', 0)))
    rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
    for loop_uid, _, name, r_n, r_e in rlist:
        if r_n or r_e:
            r_total =  r_n + r_e
            rdict[loop_uid] = r_total  
    if uid not in  rdict:
        raise NotFoundError('你已經完刀')      
    if already_queue >= rdict[uid] :
        raise NotFoundError('申報尾盤的刀數多於剩餘刀數 請先用.刪尾盤 王編號 刪除')
   # dmg = str(remain_list[1]).replace("w","").replace("W","")
   # note = str(remain_list[2])
    details = boss+" "+dmg
    sub.add_queue(uid,details)
    _save_sub(sub, dt_string)
    await bot.kkr_send(ev, f'新增成功')  

@cb_cmd(('查排刀', '查尾盤','查尾盘'),  ArgParser(usage=USAGE_ADD_MEMBER, arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def check_queue(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid  = args['@'] or ev.get_author_id()
    clan = _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']
    sub = _load_sub(dt_string)
    queue = sub.get_queue_list()
    ### remain 
    rdict= {}
    rlist = bm.list_challenge_remain(1, datetime.now() - timedelta(days=args.get('D', 0)))
    rlist.sort(key=lambda x: x[3] + x[4], reverse=True)
    for uid, _, name, r_n, r_e in rlist:
        if r_n or r_e:
            if r_e ==1 :
                r_total =  r_n + 0.5
            else:
                r_total =  r_n  
            rdict[uid] = f"剩{r_total}刀 |"     
    ### already hit     
    now = datetime.now() 
    zone = bm.get_timezone_num(clan['server'])
    chanllen_dict ={}
    for details in queue :
        uid = details[0]
        mem = _check_member(bm, uid, bm.group, '公會內無此成員')
        chanllen_list =[]
        compen_list = []
        challen = bm.list_challenge_of_user_of_day(mem['uid'], mem['alt'], now, zone)
        if uid not in chanllen_dict :
            chanllen_dict[uid] =  {}
        for c in challen :
            if c['flag']==1 or c['flag']==0 :
                chanllen_list.append(  c['boss'])
                chanllen_dict[uid]['正刀'] = chanllen_list
            if c['flag'] ==2 or c['flag']==3:
                compen_list.append(  c['boss'])
                chanllen_dict[uid]['補償'] = compen_list
    ### print out result 
    msg= []
    for boss in range(1, 6):
        join_boss =0
        total_dmg = 0
        insert_row = len(  msg  )
        for details in queue :
          #  print(  details )
            uid = details[0]
            if uid in rdict : ### still have challenge 
                details_split = details[1].split(" ")
                boss_num = details_split[0]
                dmg = str(details_split[1])
                calculate_dmg = re.findall("\d+", str(details_split[1]))[0]
            #  note = details_split[2]
                if str(boss_num) == str(boss):
                    join_boss = join_boss +1
                    total_dmg = int(total_dmg)+ int(calculate_dmg)
                    mem = _check_member(bm, uid, bm.group, '公會內無此成員')
                    mem_name = mem["name"]
                    msg.append(f'{rdict[uid]} | {mem_name} {dmg}｜ {chanllen_dict[uid]}')  
        msg.insert(insert_row,f"=================\n{bm.int2kanji(boss)}王: 總人數{join_boss},總傷害:{total_dmg}")
    await bot.kkr_send(ev, '\n'.join(msg), at_sender=True)        

@cb_cmd(('刪排刀', '删尾盤','删尾盘','删排刀',),  ArgParser(usage=USAGE_ADD_MEMBER, arg_dict={
    '@': ArgHolder(tip='id', type=str, default=0),
    '': ArgHolder(tip='boss_number', type=str, default='')}))
async def del_queue(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid  = args['@'] or ev.get_author_id()
    clan = _check_clan(bm)
    _check_member(bm, uid, bm.group)
    now = datetime.now() -  timedelta(hours=5)
    dt_string = now.strftime("%d%m%Y")+ " "+ clan['gid']      
    remain_list = list(str(ev.get_param().remain).split(' '))
    boss = str(remain_list[0])
    sub = _load_sub(dt_string)
    queue = sub.get_queue_list()  
    for details in queue:
        sub = _load_sub(dt_string)
        queue = sub.get_queue_list()  
        queue_uid = details[0]
        details_split = details[1].split(" ")
        boss_num = details_split[0]
        if uid==queue_uid and str(boss_num)==boss :
            queue.remove(details)
            _save_sub(sub, dt_string)
    await bot.kkr_send(ev, f'刪除成功')          

@cb_cmd(('算','cal'), ArgParser(usage='.算 math_expression', arg_dict={'': ArgHolder(tip='math_expression')})) # 由於需要輸入兩個傷害，因此 ArgParser 僅僅是擺設
async def calculator(bot, ev: EventInterface, args: ParseResult):
    remain = list(str(ev.get_param().remain).split(' '))
    math_expression = str(remain[0])
    result = eval(math_expression)
    await bot.kkr_send(ev, str(result))


### for fun ### @everyone
@cb_cmd(('滑刀'), ArgParser(usage='.滑刀')) 
async def change_nick(bot:KokkoroBot, ev:EventInterface,args:ParseResult):
    nick_name =  ev.get_nick_name()
    msg = f'''{ev.get_nick_name()} 今天滑刀了，在此滿足大家三個要求之一
    1. 全員周年包一個
    2. 女裝跳舞30分鐘
    3. 代刀30
    '''
    print( msg  )
  #  await sv12.broadcast("<@&865579705977012234>"+"\n"+msg) 
    await bot.kkr_send(ev,"<@everyone>"+"\n"+msg) 

@cb_cmd(('87','大少','大爺','心情不好','老子'), ArgParser(usage='.87')) 
async def list_87(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    await bot.kkr_send(ev, R.img('87.jpg')) 

@cb_cmd(('妹妹'), ArgParser(usage='.妹妹', arg_dict={
        '@': ArgHolder(tip='id', type=str, default=0)}))
async def list_sister(bot:KokkoroBot, ev:EventInterface, args:ParseResult):
    bm = BattleMaster(ev.get_group_id())
    uid = args['@'] or args.uid or ev.get_author_id()
    mem = _check_member(bm, uid, bm.group, '醒 你只有你自已')
    msglist = [R.img('0.jpg'), R.img('1.jpg'),R.img('2.jpg'),R.img('3.jpg'),R.img('4.jpg'),R.img('5.jpg'),R.img('6.jpg'),R.img('7.jpg'),R.img('8.jpg')]
    index = random.randint(0, len(msglist)-1)
    await bot.kkr_send(ev, msglist[index])



