import os
import re
import random
import asyncio
from urllib.parse import urljoin, urlparse, parse_qs
try:
    import ujson as json
except:
    import json

from kokkoro import aiorequests, R
from kokkoro.service import BroadcastService, BroadcastTag
from kokkoro.common_interface import KokkoroBot, EventInterface

sv = BroadcastService('pcr-comic', broadcast_tag=BroadcastTag.jp_broadcast)

def load_index():
    with open(R.get('img/priconne/comic/index.json').path, encoding='utf8') as f:
        return json.load(f)

def get_pic_name(id_):
    pre = 'episode_'
    end = '.png'
    return f'{pre}{id_}{end}'


@sv.on_prefix('官漫')
async def comic(bot:KokkoroBot, ev: EventInterface):
    episode = ev.get_param().remain
    if not re.fullmatch(r'\d{0,3}', episode):
        return
    episode = episode.lstrip('0')
    if not episode:
        await bot.kkr_send(ev, '请输入漫画集数 如：官漫132', at_sender=True)
        return
    index = load_index()
    if episode not in index:
        await bot.kkr_send(ev, f'未查找到第{episode}话，敬请期待官方更新', at_sender=True)
        return
    title = index[episode]['title']
    pic = R.img('priconne/comic/', get_pic_name(episode))
    msg = f'プリンセスコネクト！Re:Dive公式4コマ\n第{episode}話 {title}'
    await bot.kkr_send(ev, pic)
    await bot.kkr_send(ev, msg, at_sender=True)


async def download_img(save_path, link):
    '''
    从link下载图片保存至save_path（目录+文件名）
    会覆盖原有文件，需保证目录存在
    '''
    sv.logger.info(f'download_img from {link}')
    resp = await aiorequests.get(link, stream=True)
    sv.logger.info(f'status_code={resp.status_code}')
    if 200 == resp.status_code:
        if re.search(r'image', resp.headers['content-type'], re.I):
            sv.logger.info(f'is image, saving to {save_path}')
            with open(save_path, 'wb') as f:
                f.write(await resp.content)
                sv.logger.info('saved!')


async def download_comic(id_):
    '''
    下载指定id的官方四格漫画，同时更新漫画目录index.json
    episode_num可能会小于id
    '''
    base = 'https://comic.priconne-redive.jp/api/detail/'
    save_dir = R.img('priconne/comic/').path
    index = load_index()

    # 先从api获取detail，其中包含图片真正的链接
    sv.logger.info(f'getting comic {id_} ...')
    url = base + id_
    sv.logger.info(f'url={url}')
    resp = await aiorequests.get(url)
    sv.logger.info(f'status_code={resp.status_code}')
    if 200 != resp.status_code:
        return
    data = await resp.json()
    data = data[0]

    episode = data['episode_num']
    title = data['title']
    link = data['cartoon']
    index[episode] = {'title': title, 'link': link}
    sv.logger.info(f'episode={index[episode]}')

    # 下载图片并保存
    await download_img(os.path.join(save_dir, get_pic_name(episode)), link)

    # 保存官漫目录信息
    with open(os.path.join(save_dir, 'index.json'), 'w', encoding='utf8') as f:
        json.dump(index, f, ensure_ascii=False)


