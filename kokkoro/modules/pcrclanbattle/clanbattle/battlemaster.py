from datetime import datetime, timezone, timedelta

from kokkoro import config
from .dao.sqlitedao import ClanDao, MemberDao, BattleDao
from .exception import NotFoundError
import copy



def get_config():
    return config.modules.pcrclanbattle.boss_config


class BattleMaster(object):
    '''
    Different bits represent different damage kind: 
    '''
    NORM    = BattleDao.NORM    # 0
    LAST    = BattleDao.LAST    # 1<<0
    EXT     = BattleDao.EXT     # 1<<1
    TIMEOUT = BattleDao.TIMEOUT # 1<<2

    @staticmethod
    def has_damage_kind_for(src, dst):
        return src & dst != 0

    @staticmethod
    def damage_kind_to_string(src):
        res = []
        if src & BattleMaster.EXT:
            res.append('補時')
        if src & BattleMaster.LAST:
            res.append('尾刀')
        if src & BattleMaster.TIMEOUT:
            res.append('掉線')
        if src == BattleMaster.NORM:
            res.append('通常')
        return res

    SERVER_JP = ClanDao.SERVER_JP
    SERVER_TW = ClanDao.SERVER_TW
    SERVER_CN = ClanDao.SERVER_CN

    SERVER_JP_NAME = ('jp', 'JP', 'Jp', '日', '日服', str(SERVER_JP))
    SERVER_TW_NAME = ('tw', 'TW', 'Tw', '台', '台服', str(SERVER_TW))
    SERVER_CN_NAME = ('cn', 'CN', 'Cn', '國', '國服', 'B', 'B服', str(SERVER_CN)) 
  
    def __init__(self, group):
        super().__init__()
        self.group = group
        self.clandao = ClanDao()
        self.memberdao = MemberDao()
        self.config = get_config()

    @staticmethod
    def get_timezone_num(server):
        return 9 if BattleMaster.SERVER_JP == server else 8

    
    @staticmethod
    def get_yyyymmdd(time, zone_num:int=8):
      #  print( 'zone_num', zone_num   )
        '''
        返回time對應的會戰年月日。
        其中，年月為該期會戰的年月；日為刷新周期對應的日期。
        會戰為每月最後一星期，編程時認為mm月的會戰一定在mm月20日至mm+1月10日之間，每日以5:00 UTC+8為界。
        注意：返回的年月日並不一定是自然時間，如2019年9月2日04:00:00我們認為對應2019年8月會戰，日期仍為1號，將返回(2019,8,1)
        '''
        # 日台服均為當地時間淩晨5點更新，故減5
      #  print(  time.astimezone  )
       # utc = timezone.utc
      #  utc_time =datetime.utcnow().replace(tzinfo=utc)
      #  time = utc_time.astimezone(timezone(timedelta(hours=5)))  ### have bug in astimezone , so stop first
       # time = utc_time.astimezone(timezone(timedelta(hours=+8))) 
        time = time.astimezone(timezone(timedelta(hours=zone_num-5)))

       # print(    time)
      #  if chao_data ==False:
          #  utc = timezone.utc
         #   utc_time =datetime.utcnow().replace(tzinfo=utc)
         #   time = utc_time.astimezone(timezone(timedelta(hours=4))) 
         #   print('before_time', time.astimezone(timezone(timedelta(hours=3))) )
         #   time = datetime.now() -  timedelta(hours=5)  ### return princess real day
         #   print('adj_time', time )
     #   else:    
          #  time = time.astimezone(timezone(timedelta(hours=3)))  ### challenge time adjust
          #  print('chao_time', time )
      #  print(  timezone(timedelta(hours=5)  )
    #    adj_time = timezone(timedelta(hours=0))
      #  time = time.astimezone(timezone(timedelta(hours=0)))
        yyyy = time.year
        mm = time.month
        dd = time.day
     #   print( yyyy, mm   ,dd  )
        if dd < 20:
            mm = mm - 1
        if mm < 1:
            mm = 12
            yyyy = yyyy - 1
      #  print(  yyyy, mm, dd    )    
        return (yyyy, mm, dd)


    @staticmethod
    def next_boss(round_:int, boss:int):
        return (round_, boss + 1) if boss < 5 else (round_ + 1, 1)


    @staticmethod
    def get_stage(round_, server):
        if server == BattleMaster.SERVER_CN:
            y, m, _ = BattleMaster.get_yyyymmdd(datetime.now(), 8)
            if y == 2020:
                if m < 9:
                    return 5 if round_ == 1 else 6
                elif m < 12:
                    return 7 if round_ <= 3 else 8
        # All other situation
        return 5 if round_ >= 41 else 4 if round_ >= 31 else 3 if round_ >= 11 else 2 if round_ >= 4 else 1


    def get_boss_info(self, round_, boss, server):
        """@return: boss_max_hp, score_rate"""
        stage = BattleMaster.get_stage(round_, server)
        config = self.config
        boss_hp = config[ config["BOSS_HP"][server] ][ stage-1 ][ boss-1 ]
        score_rate = config[ config["SCORE_RATE"][server] ][ stage-1 ][ boss-1 ]
        return boss_hp, score_rate


    def get_boss_hp(self, round_, boss, server):
        stage = BattleMaster.get_stage(round_, server)
        config = self.config
        return config[ config["BOSS_HP"][server] ][ stage-1 ][ boss-1 ]


    def get_score_rate(self, round_, boss, server):
        stage = BattleMaster.get_stage(round_, server)
        config = self.config
        return config[ config["SCORE_RATE"][server] ][ stage-1 ][ boss-1 ]


    @staticmethod
    def int2kanji(x):
        if 0 <= x <= 50:
            return '零一二三四五六七八九十⑪⑫⑬⑭⑮⑯⑰⑱⑲廿㉑㉒㉓㉔㉕㉖㉗㉘㉙卅㉛㉜㉝㉞㉟㊱㊲㊳㊴㊵㊶㊷㊸㊹㊺㊻㊼㊽㊾㊿'[x]
        raise ValueError("'x' should in range [0, 50]")

    @staticmethod
    def get_server_code(server_name):
        if server_name in BattleMaster.SERVER_JP_NAME:
            return BattleMaster.SERVER_JP
        elif server_name in BattleMaster.SERVER_TW_NAME:
            return BattleMaster.SERVER_TW
        elif server_name in BattleMaster.SERVER_CN_NAME:
            return BattleMaster.SERVER_CN
        else:
            return -1


    def get_battledao(self, cid, time):
        clan = self.get_clan(cid)
        zone_num = self.get_timezone_num(clan['server'])
        yyyy, mm, _ = self.get_yyyymmdd(time, zone_num)
        return BattleDao(self.group, cid, yyyy, mm)


    def add_clan(self, cid, name, server):
        return self.clandao.add({'gid': self.group, 'cid': cid, 'name': name, 'server': server})
    def del_clan(self, cid):
        return self.clandao.delete(self.group, cid)
    def mod_clan(self, cid, name, server):
        return self.clandao.modify({'gid': self.group, 'cid': cid, 'name': name, 'server': server})
    def has_clan(self, cid):
        return True if self.clandao.find_one(self.group, cid) else False
    def get_clan(self, cid):
        return self.clandao.find_one(self.group, cid)
    def list_clan(self):
        return self.clandao.find_by_gid(self.group)


    def add_member(self, uid, alt, name, cid):
        return self.memberdao.add({'uid': uid, 'alt': alt, 'name': name, 'gid': self.group, 'cid': cid})
    def del_member(self, uid, alt):
        return self.memberdao.delete(uid, alt)
    def clear_member(self, cid=None):
        return self.memberdao.delete_by(gid=self.group, cid=cid)
    def mod_member(self, uid, alt, new_name, new_cid):
        return self.memberdao.modify({'uid': uid, 'alt': alt, 'name': new_name, 'gid': self.group, 'cid': new_cid})
    def has_member(self, uid, alt):
        mem = self.memberdao.find_one(uid, alt)
        return True if mem and mem['gid'] == self.group else False
    def get_member(self, uid, alt):
        mem = self.memberdao.find_one(uid, alt)
        return mem if mem and mem['gid'] == self.group else None
    def list_member(self, cid=None):
        return self.memberdao.find_by(gid=self.group, cid=cid)
    def list_account(self, uid):
        return self.memberdao.find_by(gid=self.group, uid=uid)


    def add_challenge(self, uid, alt, round_, boss, dmg, flag, time):
        mem = self.get_member(uid, alt)
        if not mem or mem['gid'] != self.group:
            raise NotFoundError('未找到成員')
        challenge = {
            'uid':   uid,
            'alt':   alt,
            'time':  time,
            'round': round_,
            'boss':  boss,
            'dmg':   dmg,
            'flag':  flag
        }
        dao = self.get_battledao(mem['cid'], time)
        return dao.add(challenge)

    def mod_challenge(self, eid, uid, alt, round_, boss, dmg, flag, time):
        mem = self.get_member(uid, alt)
        if not mem or mem['gid'] != self.group:
            raise NotFoundError('未找到成員')
        challenge = {
            'eid':   eid,
            'uid':   uid,
            'alt':   alt,
            'time':  time,
            'round': round_,
            'boss':  boss,
            'dmg':   dmg,
            'flag':  flag
        }
        print(   challenge    )
        dao = self.get_battledao(mem['cid'], time)
        return dao.modify(challenge)

    def del_challenge(self, eid, cid, time):
        dao = self.get_battledao(cid, time)
        return dao.delete(eid)

    def get_challenge(self, eid, cid, time):
        dao = self.get_battledao(cid, time)
        return dao.find_one(eid)

    def list_challenge(self, cid, time):
        dao = self.get_battledao(cid, time)
        return dao.find_all()

    def list_challenge_of_user(self, uid, alt, time):
        mem = self.memberdao.find_one(uid, alt)
        if not mem or mem['gid'] != self.group:
            return []
        dao = self.get_battledao(mem['cid'], time)
        return dao.find_by(uid=uid, alt=alt)


    @staticmethod
    def filt_challenge_of_day(challenge_list, time, zone_num:int=8):
     #   print('loca_time', time    )
        _, _, day = BattleMaster.get_yyyymmdd(time, zone_num)
      #  print("now",_,_,day)
        return list(filter(lambda challen: day == BattleMaster.get_yyyymmdd(challen['time'], zone_num)[2], challenge_list))


    def list_challenge_of_day(self, cid, time, zone_num:int=8):
        return self.filt_challenge_of_day(self.list_challenge(cid, time), time, zone_num)


    def list_challenge_of_user_of_day(self, uid, alt, time, zone_num:int=8):
        return self.filt_challenge_of_day(self.list_challenge_of_user(uid, alt, time), time, zone_num)


    def stat_challenge(self, cid, time, only_one_day=True, zone_num:int=8):
        '''
        統計每個成員的出刀
        return [(member, [challenge])]
        '''
        ret = []
        mem = self.list_member(cid)
        dao = self.get_battledao(cid, time)
        for m in mem:
            challens = dao.find_by(uid=m['uid'], alt=m['alt'])
            if only_one_day:
                challens = self.filt_challenge_of_day(challens, time, zone_num)
            ret.append((m, challens))
     #   print(ret)    
        return ret

    
    def stat_damage(self, cid, time,one_day_only=False):
        '''
        統計cid會各成員的本月各Boss傷害總量
        :return: [(uid, alt, name, [total_dmg, dmg1, ..., dmg5])]
        '''
        clan = self.get_clan(cid)
        if not clan:
            raise NotFoundError(f'未找到公會{cid}')
        server = clan['server']
        stat = self.stat_challenge(cid, time, only_one_day=one_day_only, zone_num=self.get_timezone_num(server))
        ret = []
        for mem, challens in stat:
            dmgs = [0] * 6
            for ch in challens:
                d = ch['dmg']
                dmgs[0] += d
                dmgs[ch['boss']] += d          
            ret.append((mem['uid'], mem['alt'], mem['name'], dmgs))
        return ret


    def stat_score(self, cid, time,one_day_only=False):
        '''
        統計cid會各成員的本月總分數
        :return: [(uid,alt,name,score)]
        '''
        clan = self.get_clan(cid)
        if not clan:
            raise NotFoundError(f'未找到公會{cid}')
        server = clan['server']
        stat = self.stat_challenge(cid, time, only_one_day=one_day_only, zone_num=self.get_timezone_num(server))
        ret = [
            (mem['uid'], mem['alt'], mem['name'], sum(map(lambda ch: round(self.get_score_rate(ch['round'], ch['boss'], server) * ch['dmg']), challens)))
            for mem, challens in stat
        ]
        return ret


    def list_challenge_remain(self, cid, time):
        '''
        return [(uid,alt,name,remain_n,remain_e)]

        norm + timeout + last == 3 - remain_n       // 正常出刀數 == 3 - 余刀數
        last - ext == remain_e                      // 尾刀數 - 補時刀數 == 補時余刀
        challen_cnt == norm + last + ext + timeout  // 列表長度 == 所有出刀
        故有==>
        remain_n = 3 - (norm + timeout + last)
        remain_e = last - ext
        '''
        def count(challens):
            norm = 0
            last = 0
            ext = 0
            timeout = 0
            for ch in challens:
                f = ch['flag']
                if f & BattleMaster.EXT:
                    ext = ext + 1
                elif f & BattleMaster.LAST:
                    last = last + 1
                elif f & BattleMaster.TIMEOUT:
                    timeout = timeout + 1
                else:
                    norm = norm + 1
            return norm, last, ext, timeout

        clan = self.get_clan(cid)
        if not clan:
            raise NotFoundError(f'未找到公會{cid}')
        ret = []
        stat = self.stat_challenge(cid, time, only_one_day=True, zone_num=self.get_timezone_num(clan['server']))
        for mem, challens in stat:
            norm, last, ext, timeout = count(challens)
            r = (
                mem['uid'], mem['alt'], mem['name'],
                3 - (norm + timeout + last),
                last - ext,
            )
            ret.append(r)
        return ret

    def get_challenge_progress(self, cid, time,boss,round_plus =0):
        '''
        return (round, boss, remain_hp)
        '''
        clan = self.get_clan(cid)
        if not clan:
            return None
        server = clan['server']
        dao = self.get_battledao(cid, time)
        challens = dao.find_all()
        round_= 0
        print( boss  )
        for challen in reversed(challens):
            if  challen['boss'] == boss :
                round_ = challen['round']
                break
        print( round_  )    
        if not len(challens):
            return ([1,1,1,1,1],[self.get_boss_hp(1, 1, server) , self.get_boss_hp(1, 2, server) ,self.get_boss_hp(1, 3, server) ,self.get_boss_hp(1, 4, server) ,self.get_boss_hp(1, 5, server)   ]     )  
       # round_ = challens[-1]['round'] + round_plus
        remain_hp = self.get_boss_hp(round_, boss, server)
        for challen in reversed(challens):
            if challen['round'] < round_ :
                    break 
            if challen['round'] == round_ and challen['boss'] == boss :
                remain_hp = remain_hp - challen['dmg']        
        return (round_, boss, remain_hp)

    def get_challenge_progress_all_boss(self, cid, time):
        '''
        return (round, boss, remain_hp)
        '''
        clan = self.get_clan(cid)
        if not clan:
            return None
        server = clan['server']
        dao = self.get_battledao(cid, time)
        challens = dao.find_all()
        remain_hp_list= [self.get_boss_hp(1, 1, server) , self.get_boss_hp(1, 2, server) ,self.get_boss_hp(1, 3, server) ,self.get_boss_hp(1, 4, server) ,self.get_boss_hp(1, 5, server)   ] 
        round_list = [1,1,1,1,1]
        if not len(challens):
            return (round_list,  remain_hp_list  )  
      #  round_ = challens[-1]['round']
        ### first find pervious 5 boss last round
        for boss_num in range(1,6):
            for challen in reversed(challens):
                if  challen['boss'] == boss_num :
                    round_list[boss_num-1] = challen['round']
                    break 

      # print(  'round_list1', round_list  )    
        ### first find pervious 5 boss last blood
        for boss_num in range(1,6):
            round_ = round_list[boss_num-1]
            remain_hp = self.get_boss_hp(round_, boss_num, server) 
            for challen in reversed(challens):
                if challen['round'] < round_ :
                    break 
                if challen['round'] == round_ and challen['boss'] == boss_num    :
                    remain_hp = remain_hp - challen['dmg']
            remain_hp_list[boss_num-1] = remain_hp          

      #  print('remain_hp_list1',remain_hp_list)
        original_remain_hp_list = copy.deepcopy(remain_hp_list   )
        ### loop once to get global max and min
        for i in range(len(remain_hp_list)):
            round_ = round_list[i]
            now_stage = BattleMaster.get_stage(round_, server) 
            next_stage = BattleMaster.get_stage(round_+1, server) 
            max_r = max(   round_list  )
            if all(x == 0 for x in remain_hp_list)  and all(x == round_ for x in round_list):
                for new_i in  range(len(remain_hp_list)):
                    remain_hp = self.get_boss_hp(round_+1, new_i+1, server) 
                    remain_hp_list[new_i] = remain_hp
                    round_list[new_i] =round_+1 
                break
            if (remain_hp_list[i]<= 0  and now_stage==  next_stage )or (remain_hp_list[i]<= 0  and max_r> round_)  :
               # print( 'i',i)
                remain_hp = self.get_boss_hp(round_+1, i+1, server) 
                remain_hp_list[i] = remain_hp
                round_list[i] =round_+1 
     #   print( 'remain_hp_list2', remain_hp_list   )      
     #   print( 'round_list2', round_list   )  
        max_r = max(   round_list  )
        min_r = min(   round_list  )      
     #   print( 'max_r', max_r   )      
     #   print( 'min_r', min_r   )  
        new_round_list=[]
        new_remain_hp_list=[]
        ### adjust based on global max and min
        for i in range(len(remain_hp_list)):
            round_ = round_list[i]
            diff = max_r- min_r
            if round_ - min_r>=2  :
                    #print( 'i',i)
                    remain_hp = self.get_boss_hp(round_-1, i+1, server) 
                    new_remain_hp_list.append(original_remain_hp_list[i])
                    new_round_list.append(round_-1 )  
            else:
                new_remain_hp_list.append(remain_hp_list[i])
                new_round_list.append(round_ )        

       # print( 'new_remain_hp_list', new_remain_hp_list   )      
     #   print( 'new_round_list', new_round_list   )     

     #   if all(x == 0 for x in remain_hp_list):
        #    round_ = challens[-1]['round'] +1 
         #   remain_hp_list= []
         #   for boss_num in range(1,6):
            #    remain_hp = self.get_boss_hp(round_, boss_num, server) 
             #   print( remain_hp  )
             #   remain_hp_list.append(remain_hp)         
        return (new_round_list,new_remain_hp_list)    
    

    