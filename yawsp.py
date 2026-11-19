# -*- coding: utf-8 -*-
# Module: default
# Author: cache-sk
# License: AGPL v.3 https://www.gnu.org/licenses/agpl-3.0.html

import io
import os
import sys
import re
import json
import uuid
import hashlib
import traceback
from urllib.parse import urlencode, parse_qsl
from xml.etree import ElementTree as ET

import requests
import unidecode
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon
import xbmcvfs

from md5crypt import md5crypt

BASE = 'https://webshare.cz'
API = BASE + '/api/'
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
HEADERS = {'User-Agent': UA, 'Referer': BASE}
REALM = ':Webshare:'
CATEGORIES = ['', 'video', 'images', 'audio', 'archives', 'docs', 'adult']
SORTS = ['', 'recent', 'rating', 'largest', 'smallest']
SEARCH_HISTORY = 'search_history.json'
BOOKMARKS_FILE = 'bookmarks.json'
NONE_WHAT = '%#NONE#%'

PROP_DOWNLOADING = 'plugin.video.yawsp.downloading'
PROP_CANCEL_DL = 'plugin.video.yawsp.cancel_download'

_url = sys.argv[0]
_handle = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].lstrip('-').isdigit() else -1
_addon = xbmcaddon.Addon()
_session = requests.Session()
_session.headers.update(HEADERS)
_profile = xbmcvfs.translatePath(_addon.getAddonInfo('profile'))


def log(msg, level=xbmc.LOGINFO):
    xbmc.log(f"[plugin.video.yawsp] {msg}", level)


def ensure_profile():
    try:
        if not os.path.exists(_profile):
            os.makedirs(_profile)
    except OSError:
        log(traceback.format_exc(), xbmc.LOGERROR)


def get_url(**kwargs):
    return '{0}?{1}'.format(_url, urlencode(kwargs))


def api(fnct, data):
    try:
        return _session.post(API + fnct + "/", data=data, timeout=15)
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)
        return None


def parse_xml(response):
    if response is None or not response.content:
        return None
    try:
        return ET.fromstring(response.content)
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)
        return None


def is_ok(xml):
    if xml is None:
        return False
    status = xml.find('status')
    return status is not None and status.text == 'OK'


def popinfo(message, heading=None, icon=xbmcgui.NOTIFICATION_INFO, time=3000, sound=False):
    if heading is None:
        heading = _addon.getAddonInfo('name')
    xbmcgui.Dialog().notification(heading, message, icon, time, sound=sound)


def set_video_info(listitem, title, plot=None, duration=None, rating=None, year=None):
    try:
        info_tag = listitem.getVideoInfoTag()
        info_tag.setTitle(title)
        if plot:
            info_tag.setPlot(plot)
        if duration:
            try:
                info_tag.setDuration(int(float(duration)))
            except (ValueError, TypeError):
                pass
        if rating:
            try:
                info_tag.setRating(float(rating))
            except (ValueError, TypeError):
                pass
        if year:
            try:
                info_tag.setYear(int(year))
            except (ValueError, TypeError):
                pass
    except AttributeError:
        info = {'title': title}
        if plot:
            info['plot'] = plot
        listitem.setInfo('video', info)


def login():
    username = _addon.getSetting('wsuser')
    password = _addon.getSetting('wspass')
    if not username or not password:
        popinfo(_addon.getLocalizedString(30101), sound=True)
        _addon.openSettings()
        return None

    response = api('salt', {'username_or_email': username})
    xml = parse_xml(response)
    if is_ok(xml):
        salt_node = xml.find('salt')
        if salt_node is None or not salt_node.text:
            popinfo(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
            return None
        salt = salt_node.text
        crypted = md5crypt(password.encode('utf-8'), salt.encode('utf-8')).encode('utf-8')
        encrypted_pass = hashlib.sha1(crypted).hexdigest()
        pass_digest = hashlib.md5(
            username.encode('utf-8') + REALM.encode('utf-8') + encrypted_pass.encode('utf-8')
        ).hexdigest()

        response = api('login', {
            'username_or_email': username,
            'password': encrypted_pass,
            'digest': pass_digest,
            'keep_logged_in': 1
        })
        xml = parse_xml(response)
        if is_ok(xml):
            token_node = xml.find('token')
            if token_node is not None and token_node.text:
                token = token_node.text
                _addon.setSetting('token', token)
                return token
        popinfo(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
        _addon.openSettings()
    else:
        popinfo(_addon.getLocalizedString(30102), icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
        _addon.openSettings()
    return None


def get_account_status(token):
    response = api('user_data', {'wst': token})
    xml = parse_xml(response)
    if is_ok(xml):
        vip_node = xml.find('vip')
        days_node = xml.find('vip_days')
        is_vip = vip_node is not None and vip_node.text == '1'
        vip_days = days_node.text if (days_node is not None and days_node.text) else '0'
        return True, is_vip, vip_days
    return False, False, '0'


def revalidate(return_status=False):
    token = _addon.getSetting('token')
    if not token:
        token = login()
        if not token:
            return (None, False, '0') if return_status else None

    valid, is_vip, vip_days = get_account_status(token)
    if valid:
        if not is_vip:
            popinfo(_addon.getLocalizedString(30103), icon=xbmcgui.NOTIFICATION_WARNING)
        return (token, is_vip, vip_days) if return_status else token

    new_token = login()
    if new_token:
        valid, is_vip, vip_days = get_account_status(new_token)
        if valid:
            if not is_vip:
                popinfo(_addon.getLocalizedString(30103), icon=xbmcgui.NOTIFICATION_WARNING)
            return (new_token, is_vip, vip_days) if return_status else new_token

    return (None, False, '0') if return_status else None


def todict(xml, skip=None):
    if skip is None:
        skip = []
    result = {}
    for e in xml:
        if e.tag not in skip:
            value = e.text if len(list(e)) == 0 else todict(e, skip)
            if e.tag in result:
                if isinstance(result[e.tag], list):
                    result[e.tag].append(value)
                else:
                    result[e.tag] = [result[e.tag], value]
            else:
                result[e.tag] = value
    return result


def sizelize(txtsize, units=None):
    if units is None:
        units = ['B', 'KB', 'MB', 'GB']
    if txtsize:
        try:
            size = float(txtsize)
        except (ValueError, TypeError):
            return str(txtsize)
        if size < 1024:
            return str(int(size)) + units[0]
        size /= 1024
        if size < 1024:
            return str(int(round(size))) + units[1]
        size /= 1024
        if size < 1024:
            return str(round(size, 2)) + units[2]
        size /= 1024
        return str(round(size, 2)) + units[3]
    return str(txtsize)


def format_duration(seconds_raw):
    try:
        secs = int(float(seconds_raw))
        if secs <= 0:
            return ''
        h = secs // 3600
        m = (secs % 3600) // 60
        s = secs % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except (ValueError, TypeError):
        return ''


def detect_badges(name, width=None, height=None):
    badges = []
    upper_name = name.upper()

    h_val = 0
    try:
        if height:
            h_val = int(float(height))
        elif width:
            w_val = int(float(width))
            if w_val >= 3800:
                h_val = 2160
            elif w_val >= 1900:
                h_val = 1080
            elif w_val >= 1200:
                h_val = 720
    except (ValueError, TypeError):
        h_val = 0

    if h_val >= 2100 or re.search(r'(?:^|[^A-Z0-9])(4K|2160P|UHD)(?:$|[^A-Z0-9])', upper_name):
        badges.append('[COLOR cyan][4K][/COLOR]')
    elif h_val >= 1000 or re.search(r'(?:^|[^A-Z0-9])(1080P|FHD|FULLHD)(?:$|[^A-Z0-9])', upper_name):
        badges.append('[COLOR deepskyblue][1080p][/COLOR]')
    elif h_val >= 700 or re.search(r'(?:^|[^A-Z0-9])(720P|HD)(?:$|[^A-Z0-9])', upper_name):
        badges.append('[COLOR lightblue][720p][/COLOR]')

    has_cz = bool(re.search(r'(?:^|[^A-Z0-9])(CZ|CZE|CZECH|DABING|DAB)(?:$|[^A-Z0-9])', upper_name))
    has_sk = bool(re.search(r'(?:^|[^A-Z0-9])(SK|SVK|SLOVAK)(?:$|[^A-Z0-9])', upper_name))
    has_tit = bool(re.search(r'(?:^|[^A-Z0-9])(TIT|TITULKY|SUB|SUBS)(?:$|[^A-Z0-9])', upper_name))

    if has_cz and has_sk:
        badges.append('[COLOR lime][CZ/SK][/COLOR]')
    elif has_cz:
        badges.append('[COLOR lime][CZ][/COLOR]')
    elif has_sk:
        badges.append('[COLOR lime][SK][/COLOR]')
    elif has_tit:
        badges.append('[COLOR yellow][TIT][/COLOR]')

    if re.search(r'(?:^|[^A-Z0-9])(HDR|HDR10|DV|DOLBY[\s._\-]?VISION)(?:$|[^A-Z0-9])', upper_name):
        badges.append('[COLOR magenta][HDR][/COLOR]')
    if re.search(r'(?:^|[^A-Z0-9])(HEVC|X265|H265|H\.265)(?:$|[^A-Z0-9])', upper_name):
        badges.append('[COLOR orange][HEVC][/COLOR]')

    return ' '.join(badges)


def labelize(file):
    if file.get('size'):
        size = sizelize(file['size'])
    elif file.get('sizelized'):
        size = file['sizelized']
    else:
        size = '?'

    name = file.get('name') or 'Unknown'
    badges = detect_badges(name, file.get('width'), file.get('height'))
    tags = [size]

    w = file.get('width')
    h = file.get('height')
    if w and h:
        tags.append(f"{w}x{h}")
    elif h:
        tags.append(f"{h}p")

    fmt = file.get('format') or file.get('type')
    if fmt and str(fmt).lower() not in name.lower():
        tags.append(str(fmt).upper())

    dur = format_duration(file.get('length') or file.get('duration'))
    if dur:
        tags.append(dur)

    pos = file.get('positive_votes')
    neg = file.get('negative_votes')
    if pos is not None or neg is not None:
        tags.append(f"+{pos or 0}/-{neg or 0}")

    if file.get('password') == '1':
        tags.append("[COLOR red]LOCKED[/COLOR]")

    prefix = f"{badges} " if badges else ""
    return f"{prefix}{name} [{' | '.join(tags)}]"


def tolistitem(file, addcommands=None):
    if addcommands is None:
        addcommands = []
    label = labelize(file)
    listitem = xbmcgui.ListItem(label=label)
    if file.get('img'):
        listitem.setArt({'thumb': file['img'], 'icon': file['img']})
    set_video_info(
        listitem,
        title=file.get('name') or label,
        duration=file.get('length') or file.get('duration')
    )
    listitem.setProperty('IsPlayable', 'true')
    commands = [
        (_addon.getLocalizedString(30211), 'RunPlugin(' + get_url(action='info', ident=file['ident']) + ')'),
        (_addon.getLocalizedString(30212), 'RunPlugin(' + get_url(action='download', ident=file['ident']) + ')'),
        (_addon.getLocalizedString(30220), 'RunPlugin(' + get_url(action='bookmark_add', ident=file['ident'], name=file.get('name', ''), size=file.get('size', '')) + ')')
    ]
    if addcommands:
        commands.extend(addcommands)
    listitem.addContextMenuItems(commands)
    return listitem


def ask(what, heading=None):
    if what is None:
        what = ''
    if heading is None:
        heading = _addon.getLocalizedString(30007)
    kb = xbmc.Keyboard(what, heading)
    kb.doModal()
    if kb.isConfirmed():
        return kb.getText()
    return None


def load_json_list(filename):
    ensure_profile()
    old_path = os.path.join(_profile, 'search_history')
    new_path = os.path.join(_profile, filename)
    if filename == SEARCH_HISTORY and os.path.exists(old_path) and not os.path.exists(new_path):
        try:
            os.rename(old_path, new_path)
        except OSError:
            pass

    if not os.path.exists(new_path):
        return []
    try:
        with io.open(new_path, 'r', encoding='utf-8') as f:
            fdata = f.read()
            return json.loads(fdata) if fdata else []
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)
        return []


def save_json_list(filename, data):
    ensure_profile()
    try:
        with io.open(os.path.join(_profile, filename), 'w', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)


def loadsearch():
    return load_json_list(SEARCH_HISTORY)


def storesearch(what):
    if what:
        try:
            size = int(_addon.getSetting('shistory'))
        except (ValueError, TypeError):
            size = 10
        history = loadsearch()
        if what in history:
            history.remove(what)
        history = [what] + history
        if len(history) > size:
            history = history[:size]
        save_json_list(SEARCH_HISTORY, history)


def removesearch(what):
    if what:
        history = loadsearch()
        if what in history:
            history.remove(what)
            save_json_list(SEARCH_HISTORY, history)


def bookmarks(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30221))
    items = load_json_list(BOOKMARKS_FILE)
    updateListing = False

    if params.get('action') == 'bookmark_add':
        ident = params.get('ident')
        if ident and not any(b.get('ident') == ident for b in items):
            items.insert(0, {
                'ident': ident,
                'name': params.get('name', ident),
                'size': params.get('size', '')
            })
            save_json_list(BOOKMARKS_FILE, items)
            popinfo(_addon.getLocalizedString(30223))
        else:
            popinfo(_addon.getLocalizedString(30224))
        return

    if 'remove' in params:
        rem_id = params['remove']
        items = [b for b in items if b.get('ident') != rem_id]
        save_json_list(BOOKMARKS_FILE, items)
        popinfo(_addon.getLocalizedString(30225))
        updateListing = True

    for b in items:
        commands = [
            (_addon.getLocalizedString(30222), 'Container.Update(' + get_url(action='bookmarks', remove=b['ident']) + ')')
        ]
        listitem = tolistitem(b, commands)
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action='play', ident=b['ident'], name=b.get('name', b['ident'])),
            listitem,
            False
        )
    xbmcplugin.endOfDirectory(_handle, updateListing=updateListing)


def dosearch(token, what, category, sort, limit, offset, action):
    if offset == 0:
        sort_label = sort if sort else _addon.getLocalizedString(30232)
        cat_label = category if category else _addon.getLocalizedString(30233)
        filter_item = xbmcgui.ListItem(
            label=f"[COLOR yellow]{_addon.getLocalizedString(30230)}: {sort_label} | {_addon.getLocalizedString(30231)}: {cat_label}[/COLOR]"
        )
        filter_item.setArt({'icon': 'DefaultAddonService.png'})
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action='change_filter', what=what, category=category, sort=sort, limit=limit),
            filter_item,
            True
        )

    response = api('search', {
        'what': '' if what == NONE_WHAT else what,
        'category': category,
        'sort': sort,
        'limit': limit,
        'offset': offset,
        'wst': token,
        'maybe_removed': 'true'
    })
    xml = parse_xml(response)
    if is_ok(xml):
        if offset > 0:
            listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30206))
            listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
            prev_offset = offset - limit if offset > limit else 0
            xbmcplugin.addDirectoryItem(
                _handle,
                get_url(action=action, what=what, category=category, sort=sort, limit=limit, offset=prev_offset),
                listitem,
                True
            )

        for file in xml.iter('file'):
            item = todict(file)
            if 'ident' not in item or 'name' not in item:
                continue
            commands = [
                (_addon.getLocalizedString(30214), 'Container.Update(' + get_url(action='search', toqueue=item['ident'], what=what, offset=offset) + ')')
            ]
            listitem = tolistitem(item, commands)
            xbmcplugin.addDirectoryItem(
                _handle,
                get_url(action='play', ident=item['ident'], name=item['name']),
                listitem,
                False
            )

        total_node = xml.find('total')
        try:
            total = int(total_node.text) if total_node is not None and total_node.text else 0
        except (ValueError, TypeError):
            total = 0

        if offset + limit < total:
            listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30207))
            listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
            xbmcplugin.addDirectoryItem(
                _handle,
                get_url(action=action, what=what, category=category, sort=sort, limit=limit, offset=offset + limit),
                listitem,
                True
            )
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)


def change_filter(params):
    dialog = xbmcgui.Dialog()
    sort_options = [_addon.getLocalizedString(30232), 'recent', 'rating', 'largest', 'smallest']
    cat_options = [_addon.getLocalizedString(30233), 'video', 'images', 'audio', 'archives', 'docs', 'adult']

    sel_sort = dialog.select(_addon.getLocalizedString(30230), sort_options)
    new_sort = SORTS[sel_sort] if sel_sort >= 0 else params.get('sort', '')

    sel_cat = dialog.select(_addon.getLocalizedString(30231), cat_options)
    new_cat = CATEGORIES[sel_cat] if sel_cat >= 0 else params.get('category', '')

    params['sort'] = new_sort
    params['category'] = new_cat
    params['action'] = 'search'
    params.pop('ask', None)
    search(params)


def search_tmdb(params):
    """Vyhľadávanie seriálov s načítaním počtu sérií, epizód a možnosťou stiahnuť celú sériu."""
    query = params.get('query')
    if not query:
        query = ask('', _addon.getLocalizedString(30241))
    if not query:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + query)

    try:
        resp = _session.get(
            'https://api.tvmaze.com/search/shows',
            params={'q': query},
            timeout=10
        )
        shows = resp.json() if resp.ok else []
    except Exception:
        shows = []

    # Možnosť priameho vyhľadania textu na Webshare
    direct_item = xbmcgui.ListItem(label=f"[B]{_addon.getLocalizedString(30242)}: {query}[/B]")
    direct_item.setArt({'icon': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='search', what=query), direct_item, True)

    for entry in shows:
        show = entry.get('show', {})
        show_id = show.get('id')
        title = show.get('name')
        premiered = (show.get('premiered') or '')[:4]
        status = show.get('status') or ''
        if not title or not show_id:
            continue

        # Získame zoznam sérií daného seriálu z TVMaze API, aby sme vedeli presný počet sérií
        seasons_count = 0
        episodes_total = 0
        try:
            s_resp = _session.get(f'https://api.tvmaze.com/shows/{show_id}/seasons', timeout=8)
            if s_resp.ok:
                seasons_data = s_resp.json()
                seasons_count = len(seasons_data)
                for s in seasons_data:
                    if s.get('episodeOrder'):
                        episodes_total += int(s['episodeOrder'])
        except Exception:
            pass

        info_parts = []
        if premiered:
            info_parts.append(premiered)
        if seasons_count > 0:
            info_parts.append(f"[COLOR cyan]{seasons_count} {_addon.getLocalizedString(30243)}[/COLOR]")
        if episodes_total > 0:
            info_parts.append(f"{episodes_total} ep.")
        if status:
            info_parts.append(status)

        suffix = f" [{' | '.join(info_parts)}]" if info_parts else ""
        display_title = f"{title}{suffix}"
        summary = re.sub(r'<[^>]+>', '', show.get('summary') or '')
        img = (show.get('image') or {}).get('medium')

        li = xbmcgui.ListItem(label=display_title)
        if img:
            li.setArt({'thumb': img, 'poster': img})
        set_video_info(li, title, plot=summary, year=premiered)

        # Otvorí prehľad sérií daného seriálu
        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action='show_seasons', show_id=show_id, title=title, img=img or ''),
            li,
            True
        )

    xbmcplugin.endOfDirectory(_handle)


def show_seasons(params):
    """Zobrazí zoznam sérií pre zvolený seriál s možnosťou prehrať alebo stiahnuť celú sériu."""
    show_id = params.get('show_id')
    title = params.get('title', 'Serial')
    img = params.get('img', '')

    xbmcplugin.setPluginCategory(_handle, f"{title} - {_addon.getLocalizedString(30244)}")

    seasons_data = []
    try:
        resp = _session.get(f'https://api.tvmaze.com/shows/{show_id}/seasons', timeout=10)
        if resp.ok:
            seasons_data = resp.json()
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)

    # Položka na vyhľadanie celého seriálu naraz
    all_item = xbmcgui.ListItem(label=f"[B]{_addon.getLocalizedString(30245)}: {title}[/B]")
    all_item.setArt({'icon': 'DefaultAddonsSearch.png', 'thumb': img})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='search', what=title, category='video'), all_item, True)

    for s in seasons_data:
        s_num = s.get('number')
        if s_num is None:
            continue
        s_num = int(s_num)
        ep_count = s.get('episodeOrder') or '?'
        s_img = (s.get('image') or {}).get('medium') or img
        premiere = (s.get('premiereDate') or '')[:4]

        s_label = f"{_addon.getLocalizedString(30246)} {s_num:02d} ({ep_count} {_addon.getLocalizedString(30247)})"
        if premiere:
            s_label += f" [{premiere}]"

        li = xbmcgui.ListItem(label=s_label)
        if s_img:
            li.setArt({'thumb': s_img, 'poster': s_img})
        set_video_info(li, s_label)

        # Kontextové menu: Stiahnuť celú sériu!
        commands = [
            (
                f"[COLOR lime]{_addon.getLocalizedString(30248)}[/COLOR]",
                'RunPlugin(' + get_url(action='download_season', show_id=show_id, title=title, season=s_num) + ')'
            )
        ]
        li.addContextMenuItems(commands)

        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action='season_episodes', show_id=show_id, title=title, season=s_num, img=s_img),
            li,
            True
        )

    xbmcplugin.endOfDirectory(_handle)


def season_episodes(params):
    """Zobrazí epizódy konkrétnej série a navrchu ponúkne tlačidlo 'Stiahnuť celú sériu'."""
    show_id = params.get('show_id')
    title = params.get('title', 'Serial')
    season_num = int(params.get('season', 1))
    img = params.get('img', '')

    xbmcplugin.setPluginCategory(_handle, f"{title} - S{season_num:02d}")

    # Tlačidlo na stiahnutie kompletnej série jedným kliknutím
    dl_all_item = xbmcgui.ListItem(
        label=f"[COLOR lime][B]⬇ {_addon.getLocalizedString(30248)} (S{season_num:02d})[/B][/COLOR]"
    )
    dl_all_item.setArt({'icon': 'DefaultAddonService.png', 'thumb': img})
    xbmcplugin.addDirectoryItem(
        _handle,
        get_url(action='download_season', show_id=show_id, title=title, season=season_num),
        dl_all_item,
        False
    )

    # Priame vyhľadanie celej série na Webshare (napr. "Breaking Bad S01")
    search_s_query = f"{title} S{season_num:02d}"
    search_s_item = xbmcgui.ListItem(
        label=f"[COLOR yellow]{_addon.getLocalizedString(30249)}: {search_s_query}[/COLOR]"
    )
    search_s_item.setArt({'icon': 'DefaultAddonsSearch.png', 'thumb': img})
    xbmcplugin.addDirectoryItem(
        _handle,
        get_url(action='search', what=search_s_query, category='video'),
        search_s_item,
        True
    )

    episodes = []
    try:
        resp = _session.get(f'https://api.tvmaze.com/shows/{show_id}/episodes', timeout=10)
        if resp.ok:
            episodes = [ep for ep in resp.json() if ep.get('season') == season_num]
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)

    for ep in episodes:
        ep_num = int(ep.get('number') or 0)
        ep_name = ep.get('name') or f"Episode {ep_num}"
        ep_code = f"S{season_num:02d}E{ep_num:02d}"
        ep_img = (ep.get('image') or {}).get('medium') or img
        summary = re.sub(r'<[^>]+>', '', ep.get('summary') or '')

        li = xbmcgui.ListItem(label=f"{ep_code} - {ep_name}")
        if ep_img:
            li.setArt({'thumb': ep_img})
        set_video_info(li, f"{ep_code} - {ep_name}", plot=summary)

        xbmcplugin.addDirectoryItem(
            _handle,
            get_url(action='search', what=f"{title} {ep_code}", category='video'),
            li,
            True
        )

    xbmcplugin.endOfDirectory(_handle)


def pick_best_episode_file(files, ep_code_std, ep_code_alt):
    """Vyberie najvhodnejší videosúbor pre konkrétnu epizódu (uprednostní CZ/SK a 1080p/720p)."""
    candidates = []
    for f in files:
        fname = (f.get('name') or '').upper()
        if ep_code_std.upper() in fname or ep_code_alt.upper() in fname:
            score = 0
            if re.search(r'(?:^|[^A-Z0-9])(CZ|CZE|CZECH|DABING|SK|SVK)(?:$|[^A-Z0-9])', fname):
                score += 100
            if re.search(r'(1080P|FHD)', fname):
                score += 30
            elif re.search(r'(720P|HD)', fname):
                score += 20
            elif re.search(r'(2160P|4K)', fname):
                score += 15
            # Penalizácia za príliš malé alebo obrovské súbory (nad 8 GB na epizódu)
            try:
                sz = float(f.get('size') or 0)
                if 150 * 1024 * 1024 <= sz <= 6 * 1024 * 1024 * 1024:
                    score += 10
            except (ValueError, TypeError):
                pass
            candidates.append((score, f))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]


def download_season(params):
    """Automaticky vyhľadá a stiahne všetky epizódy zvolenej série do podpriečinka seriálu."""
    win = xbmcgui.Window(10000)
    if win.getProperty(PROP_DOWNLOADING) == 'true':
        popinfo(_addon.getLocalizedString(30307), icon=xbmcgui.NOTIFICATION_WARNING)
        return

    token = revalidate()
    if not token:
        return

    where = _addon.getSetting('dfolder')
    if not where or not xbmcvfs.exists(where):
        popinfo(_addon.getLocalizedString(30101), sound=True)
        _addon.openSettings()
        return

    show_id = params.get('show_id')
    title = params.get('title', 'Serial')
    season_num = int(params.get('season', 1))

    # Získame zoznam epizód danej série
    episodes = []
    try:
        resp = _session.get(f'https://api.tvmaze.com/shows/{show_id}/episodes', timeout=10)
        if resp.ok:
            episodes = [ep for ep in resp.json() if ep.get('season') == season_num and ep.get('number')]
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)

    if not episodes:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        return

    # Výber preferovanej kvality / jazyka pred spustením dávkového sťahovania
    dialog = xbmcgui.Dialog()
    pref_options = [
        _addon.getLocalizedString(30255),  # Automaticky (priorita CZ/SK + 1080p/720p)
        _addon.getLocalizedString(30256),  # Iba s CZ/SK dabingom/titulkami
    ]
    pref_idx = dialog.select(f"{title} - S{season_num:02d} ({len(episodes)} ep.)", pref_options)
    if pref_idx < 0:
        return
    only_czsk = (pref_idx == 1)

    # Vytvorenie podpriečinka pre seriál a sériu (napr. "Breaking Bad/Season 01")
    safe_title = re.sub(r'[\\/:*?"<>|]', '', title).strip()
    season_folder_name = f"{safe_title} - S{season_num:02d}"
    local = os.path.exists(where)
    target_dir = os.path.join(where, season_folder_name) if local else join_path(where, season_folder_name)

    try:
        if local:
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
        else:
            if not xbmcvfs.exists(target_dir):
                xbmcvfs.mkdirs(target_dir)
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)
        target_dir = where

    normalize = _addon.getSetting('dnormalize') == 'true'
    win.setProperty(PROP_DOWNLOADING, 'true')
    win.clearProperty(PROP_CANCEL_DL)

    progress = xbmcgui.DialogProgressBG()
    progress.create(_addon.getAddonInfo('name'), f"{title} S{season_num:02d}")

    downloaded_count = 0
    missing_episodes = []
    cancelled = False

    try:
        total_eps = len(episodes)
        for idx, ep in enumerate(episodes, start=1):
            if win.getProperty(PROP_CANCEL_DL) == 'true':
                cancelled = True
                break

            ep_num = int(ep['number'])
            ep_std = f"S{season_num:02d}E{ep_num:02d}"
            ep_alt = f"{season_num}x{ep_num:02d}"
            query = f"{title} {ep_std}"

            progress.update(
                int(((idx - 1) * 100) / total_eps),
                _addon.getAddonInfo('name'),
                f"[{idx}/{total_eps}] {ep_std} - {_addon.getLocalizedString(30257)}"
            )

            resp = api('search', {
                'what': query,
                'category': 'video',
                'sort': '',
                'limit': 20,
                'offset': 0,
                'wst': token
            })
            xml = parse_xml(resp)
            found_files = []
            if is_ok(xml):
                for f_node in xml.iter('file'):
                    f_dict = todict(f_node)
                    if 'ident' in f_dict and 'name' in f_dict:
                        if only_czsk:
                            up = f_dict['name'].upper()
                            if not re.search(r'(?:^|[^A-Z0-9])(CZ|CZE|CZECH|DABING|SK|SVK)(?:$|[^A-Z0-9])', up):
                                continue
                        found_files.append(f_dict)

            best_file = pick_best_episode_file(found_files, ep_std, ep_alt)
            if not best_file:
                missing_episodes.append(ep_std)
                continue

            link = getlink(best_file['ident'], token, 'file_download')
            if not link:
                missing_episodes.append(ep_std)
                continue

            fname = best_file['name']
            if normalize:
                fname = unidecode.unidecode(fname)

            target_path = os.path.join(target_dir, fname) if local else join_path(target_dir, fname)

            # Ak už epizóda existuje, preskočíme ju (umožňuje bezpečne nadviazať na prerušené sťahovanie!)
            exists = os.path.exists(target_path) if local else xbmcvfs.exists(target_path)
            if exists:
                downloaded_count += 1
                continue

            bf = None
            try:
                bf = io.open(target_path, 'wb') if local else xbmcvfs.File(target_path, 'wb')
                dl_resp = _session.get(link, stream=True, timeout=30)
                f_total = int(dl_resp.headers.get('content-length') or 0)
                dl_bytes = 0
                last_pct = -1

                for chunk in dl_resp.iter_content(chunk_size=65536):
                    if win.getProperty(PROP_CANCEL_DL) == 'true':
                        cancelled = True
                        break
                    if chunk:
                        bf.write(chunk)
                        dl_bytes += len(chunk)
                        if f_total > 0:
                            ep_pct = int((dl_bytes * 100) / f_total)
                            overall_pct = int((((idx - 1) + (dl_bytes / f_total)) * 100) / total_eps)
                            if ep_pct != last_pct:
                                progress.update(
                                    overall_pct,
                                    _addon.getAddonInfo('name'),
                                    f"[{idx}/{total_eps}] {ep_std}: {ep_pct}%"
                                )
                                last_pct = ep_pct
                bf.close()
                bf = None

                if cancelled:
                    if local and os.path.exists(target_path):
                        os.remove(target_path)
                    elif not local and xbmcvfs.exists(target_path):
                        xbmcvfs.delete(target_path)
                    break

                downloaded_count += 1
            except Exception:
                log(traceback.format_exc(), xbmc.LOGERROR)
                if bf is not None:
                    try:
                        bf.close()
                    except Exception:
                        pass
                if local and os.path.exists(target_path):
                    os.remove(target_path)
                elif not local and xbmcvfs.exists(target_path):
                    xbmcvfs.delete(target_path)
                missing_episodes.append(ep_std)

        progress.close()
        if cancelled:
            popinfo(_addon.getLocalizedString(30309) + f"{title} S{season_num:02d}", icon=xbmcgui.NOTIFICATION_WARNING)
        else:
            msg = f"{_addon.getLocalizedString(30258)}: {downloaded_count}/{len(episodes)}"
            if missing_episodes:
                msg += f" ({_addon.getLocalizedString(30259)}: {', '.join(missing_episodes[:5])})"
            popinfo(msg, time=5000, sound=True)
    finally:
        win.clearProperty(PROP_DOWNLOADING)
        win.clearProperty(PROP_CANCEL_DL)


def get_int_setting(setting_id, default_val):
    try:
        val = _addon.getSetting(setting_id)
        return int(val) if val else default_val
    except (ValueError, TypeError):
        return default_val


def search(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30201))
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    updateListing = False

    if 'remove' in params:
        removesearch(params['remove'])
        updateListing = True

    if 'toqueue' in params:
        toqueue(params['toqueue'], token)
        updateListing = True

    what = params.get('what')

    if 'ask' in params:
        slast = _addon.getSetting('slast')
        if slast != what:
            what = ask(what)
            if what is not None:
                storesearch(what)
            else:
                updateListing = True

    if what is not None:
        if 'offset' not in params:
            _addon.setSetting('slast', what)
        else:
            _addon.setSetting('slast', NONE_WHAT)
            updateListing = True

        cat_idx = get_int_setting('scategory', 0)
        sort_idx = get_int_setting('ssort', 0)
        category = params['category'] if 'category' in params else CATEGORIES[cat_idx if 0 <= cat_idx < len(CATEGORIES) else 0]
        sort = params['sort'] if 'sort' in params else SORTS[sort_idx if 0 <= sort_idx < len(SORTS) else 0]
        limit = int(params['limit']) if 'limit' in params else get_int_setting('slimit', 25)
        offset = int(params['offset']) if 'offset' in params else 0
        dosearch(token, what, category, sort, limit, offset, 'search')
    else:
        _addon.setSetting('slast', NONE_WHAT)
        history_list = loadsearch()

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30205))
        listitem.setArt({'icon': 'DefaultAddSource.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search', ask=1), listitem, True)

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30240))
        listitem.setArt({'icon': 'DefaultTVShows.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search_tmdb'), listitem, True)

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30208))
        listitem.setArt({'icon': 'DefaultAddonsRecentlyUpdated.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search', what=NONE_WHAT, sort=SORTS[1]), listitem, True)

        listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30209))
        listitem.setArt({'icon': 'DefaultHardDisk.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='search', what=NONE_WHAT, sort=SORTS[3]), listitem, True)

        for item_search in history_list:
            listitem = xbmcgui.ListItem(label=item_search)
            listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
            commands = [
                (_addon.getLocalizedString(30213), 'Container.Update(' + get_url(action='search', remove=item_search) + ')')
            ]
            listitem.addContextMenuItems(commands)
            xbmcplugin.addDirectoryItem(_handle, get_url(action='search', what=item_search, ask=1), listitem, True)
    xbmcplugin.endOfDirectory(_handle, updateListing=updateListing)


def queue(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30202))
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    updateListing = False

    if 'dequeue' in params:
        response = api('dequeue_file', {'ident': params['dequeue'], 'wst': token})
        xml = parse_xml(response)
        if is_ok(xml):
            popinfo(_addon.getLocalizedString(30106))
        else:
            popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        updateListing = True

    response = api('queue', {'wst': token})
    xml = parse_xml(response)
    if is_ok(xml):
        for file in xml.iter('file'):
            item = todict(file)
            if 'ident' not in item or 'name' not in item:
                continue
            commands = [
                (_addon.getLocalizedString(30215), 'Container.Update(' + get_url(action='queue', dequeue=item['ident']) + ')')
            ]
            listitem = tolistitem(item, commands)
            xbmcplugin.addDirectoryItem(
                _handle,
                get_url(action='play', ident=item['ident'], name=item['name']),
                listitem,
                False
            )
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    xbmcplugin.endOfDirectory(_handle, updateListing=updateListing)


def toqueue(ident, token):
    response = api('queue_file', {'ident': ident, 'wst': token})
    xml = parse_xml(response)
    if is_ok(xml):
        popinfo(_addon.getLocalizedString(30105))
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)


def history(params):
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name') + " / " + _addon.getLocalizedString(30203))
    token = revalidate()
    if not token:
        xbmcplugin.endOfDirectory(_handle, succeeded=False)
        return

    updateListing = False

    if 'remove' in params:
        remove = params['remove']
        updateListing = True
        response = api('history', {'wst': token})
        xml = parse_xml(response)
        ids = []
        if is_ok(xml):
            for file in xml.iter('file'):
                ident_node = file.find('ident')
                dl_id_node = file.find('download_id')
                if ident_node is not None and dl_id_node is not None and remove == ident_node.text:
                    ids.append(dl_id_node.text)
        else:
            popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        if ids:
            rr = api('clear_history', {'ids[]': ids, 'wst': token})
            xml = parse_xml(rr)
            if is_ok(xml):
                popinfo(_addon.getLocalizedString(30104))
            else:
                popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)

    if 'toqueue' in params:
        toqueue(params['toqueue'], token)
        updateListing = True

    response = api('history', {'wst': token})
    xml = parse_xml(response)
    files = []
    if is_ok(xml):
        for file in xml.iter('file'):
            item = todict(file, ['ended_at', 'download_id', 'started_at'])
            if item not in files and 'ident' in item and 'name' in item:
                files.append(item)
        for file in files:
            commands = [
                (_addon.getLocalizedString(30213), 'Container.Update(' + get_url(action='history', remove=file['ident']) + ')'),
                (_addon.getLocalizedString(30214), 'Container.Update(' + get_url(action='history', toqueue=file['ident']) + ')')
            ]
            listitem = tolistitem(file, commands)
            xbmcplugin.addDirectoryItem(
                _handle,
                get_url(action='play', ident=file['ident'], name=file['name']),
                listitem,
                False
            )
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    xbmcplugin.endOfDirectory(_handle, updateListing=updateListing)


def settings(params):
    _addon.openSettings()
    xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())


def infonize(data, key, process=str, showkey=True, prefix='', suffix='\n'):
    if key in data and data[key] is not None:
        return prefix + (key.capitalize() + ': ' if showkey else '') + process(data[key]) + suffix
    return ''


def fpsize(fps):
    try:
        x = round(float(fps), 3)
        if int(x) == x:
            return str(int(x))
        return str(x)
    except (ValueError, TypeError):
        return str(fps)


def getinfo(ident, wst):
    response = api('file_info', {'ident': ident, 'wst': wst})
    xml = parse_xml(response)
    ok = is_ok(xml)
    if not ok:
        response = api('file_info', {'ident': ident, 'wst': wst, 'maybe_removed': 'true'})
        xml = parse_xml(response)
        ok = is_ok(xml)
    if ok:
        return xml
    popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    return None


def info(params):
    token = revalidate()
    if not token:
        return
    xml = getinfo(params['ident'], token)

    if xml is not None:
        file_info = todict(xml)
        text = ''
        text += infonize(file_info, 'name')
        text += infonize(file_info, 'size', sizelize)
        text += infonize(file_info, 'type')
        text += infonize(file_info, 'width')
        text += infonize(file_info, 'height')
        text += infonize(file_info, 'format')
        text += infonize(file_info, 'fps', fpsize)
        text += infonize(file_info, 'bitrate', lambda x: sizelize(x, ['bps', 'Kbps', 'Mbps', 'Gbps']))
        if 'video' in file_info and isinstance(file_info['video'], dict) and 'stream' in file_info['video']:
            streams = file_info['video']['stream']
            if isinstance(streams, dict):
                streams = [streams]
            for stream in streams:
                text += 'Video stream: '
                text += infonize(stream, 'width', showkey=False, suffix='')
                text += infonize(stream, 'height', showkey=False, prefix='x', suffix='')
                text += infonize(stream, 'format', showkey=False, prefix=', ', suffix='')
                text += infonize(stream, 'fps', fpsize, showkey=False, prefix=', ', suffix='')
                text += '\n'
        if 'audio' in file_info and isinstance(file_info['audio'], dict) and 'stream' in file_info['audio']:
            streams = file_info['audio']['stream']
            if isinstance(streams, dict):
                streams = [streams]
            for stream in streams:
                text += 'Audio stream: '
                text += infonize(stream, 'format', showkey=False, suffix='')
                text += infonize(stream, 'channels', prefix=', ', showkey=False, suffix='')
                text += infonize(stream, 'bitrate', lambda x: sizelize(x, ['bps', 'Kbps', 'Mbps', 'Gbps']), prefix=', ', suffix='')
                text += '\n'
        text += infonize(file_info, 'removed', lambda x: 'Yes' if x == '1' else 'No')
        xbmcgui.Dialog().textviewer(_addon.getAddonInfo('name'), text)


def getlink(ident, wst, dtype='video_stream'):
    duuid = _addon.getSetting('duuid')
    if not duuid:
        duuid = str(uuid.uuid4())
        _addon.setSetting('duuid', duuid)

    data = {'ident': ident, 'wst': wst, 'download_type': dtype, 'device_uuid': duuid}

    prot_resp = api('file_protected', {'ident': ident, 'wst': wst})
    prot_xml = parse_xml(prot_resp)
    if is_ok(prot_xml):
        prot_node = prot_xml.find('protected')
        if prot_node is not None and prot_node.text == '1':
            file_pass = xbmcgui.Dialog().input(_addon.getLocalizedString(30108), type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
            if not file_pass:
                return None
            salt_resp = api('file_password_salt', {'ident': ident, 'wst': wst})
            salt_xml = parse_xml(salt_resp)
            if is_ok(salt_xml) and salt_xml.find('salt') is not None and salt_xml.find('salt').text:
                f_salt = salt_xml.find('salt').text
                crypted = md5crypt(file_pass.encode('utf-8'), f_salt.encode('utf-8')).encode('utf-8')
                data['password'] = hashlib.sha1(crypted).hexdigest()
            else:
                data['password'] = file_pass

    response = api('file_link', data)
    xml = parse_xml(response)
    if is_ok(xml):
        link_node = xml.find('link')
        if link_node is not None and link_node.text:
            return link_node.text
    popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
    return None


def clean_query_for_subtitles(video_name):
    base_name = os.path.splitext(video_name)[0]
    ep_match = re.search(r'(S\d{1,2}E\d{1,2}|\d{1,2}x\d{2})', base_name, re.IGNORECASE)
    episode_tag = ep_match.group(1) if ep_match else ''

    cleaned = re.sub(
        r'(?:^|[^A-Z0-9])(2160p|1080p|720p|480p|4K|UHD|FHD|HD|WEB[\-\.]?DL|WEBRip|BluRay|BDRip|BRRip|DVDRip|HDTV|x264|x265|H264|H265|HEVC|AVC|10bit|HDR|HDR10|DV|AAC|AC3|DTS|CZ|SK|EN|ENG|CZE|SVK|DABING|TITULKY|SUBS)(?:$|[^A-Z0-9]).*',
        '',
        base_name,
        flags=re.IGNORECASE
    )
    cleaned = re.sub(r'[\.\-_]+', ' ', cleaned).strip()
    if episode_tag and episode_tag.lower() not in cleaned.lower():
        cleaned = f"{cleaned} {episode_tag}".strip()
    return cleaned if len(cleaned) >= 3 else base_name


def find_subtitles(video_name, token):
    if not video_name or _addon.getSetting('autosubs') == 'false':
        return []

    search_query = clean_query_for_subtitles(video_name)
    response = api('search', {
        'what': search_query,
        'category': 'docs',
        'limit': 15,
        'offset': 0,
        'wst': token
    })
    xml = parse_xml(response)
    subs = []
    if is_ok(xml):
        for file in xml.iter('file'):
            item = todict(file)
            fname = item.get('name', '')
            if fname.lower().endswith(('.srt', '.sub', '.ass', '.vtt')):
                sub_link = getlink(item['ident'], token, 'file_download')
                if sub_link:
                    subs.append(sub_link)
                    if len(subs) >= 4:
                        break
    return subs


def play(params):
    token = revalidate()
    if not token:
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())
        return

    link = getlink(params['ident'], token)
    if link is not None:
        headers = dict(_session.headers)
        headers['Cookie'] = 'wst=' + token
        header_str = urlencode(headers)
        full_link = link + '|' + header_str

        listitem = xbmcgui.ListItem(label=params['name'], path=full_link)
        set_video_info(listitem, params['name'])
        listitem.setProperty('mimetype', 'application/octet-stream')

        subs = find_subtitles(params.get('name', ''), token)
        if subs:
            listitem.setSubtitles([s + '|' + header_str for s in subs])

        xbmcplugin.setResolvedUrl(_handle, True, listitem)
    else:
        popinfo(_addon.getLocalizedString(30107), icon=xbmcgui.NOTIFICATION_WARNING)
        xbmcplugin.setResolvedUrl(_handle, False, xbmcgui.ListItem())


def join_path(path, filename):
    if path.endswith('/') or path.endswith('\\'):
        return path + filename
    return path + '/' + filename


def cancel_download(params):
    win = xbmcgui.Window(10000)
    win.setProperty(PROP_CANCEL_DL, 'true')
    popinfo(_addon.getLocalizedString(30306))
    xbmc.executebuiltin('Container.Refresh')


def download(params):
    win = xbmcgui.Window(10000)
    if win.getProperty(PROP_DOWNLOADING) == 'true':
        popinfo(_addon.getLocalizedString(30307), icon=xbmcgui.NOTIFICATION_WARNING)
        return

    token = revalidate()
    if not token:
        return

    where = _addon.getSetting('dfolder')
    if not where or not xbmcvfs.exists(where):
        popinfo(_addon.getLocalizedString(30101), sound=True)
        _addon.openSettings()
        return

    local = os.path.exists(where)
    normalize = _addon.getSetting('dnormalize') == 'true'
    name = params.get('ident', 'file')
    target_path = None
    bf = None
    progress = xbmcgui.DialogProgressBG()
    progress_created = False
    cancelled = False

    try:
        link = getlink(params['ident'], token, 'file_download')
        if not link:
            return
        file_xml = getinfo(params['ident'], token)
        if file_xml is None:
            return
        name_node = file_xml.find('name')
        if name_node is not None and name_node.text:
            name = name_node.text
        if normalize:
            name = unidecode.unidecode(name)

        target_path = os.path.join(where, name) if local else join_path(where, name)

        exists = os.path.exists(target_path) if local else xbmcvfs.exists(target_path)
        if exists:
            overwrite = xbmcgui.Dialog().yesno(
                _addon.getAddonInfo('name'),
                f"{_addon.getLocalizedString(30308)}\n{name}"
            )
            if not overwrite:
                return

        win.setProperty(PROP_DOWNLOADING, 'true')
        win.clearProperty(PROP_CANCEL_DL)

        bf = io.open(target_path, 'wb') if local else xbmcvfs.File(target_path, 'wb')

        response = _session.get(link, stream=True, timeout=30)
        total = int(response.headers.get('content-length') or 0)

        progress.create(_addon.getAddonInfo('name'), name)
        progress_created = True

        dl = 0
        last_pct = -1
        for chunk in response.iter_content(chunk_size=65536):
            if win.getProperty(PROP_CANCEL_DL) == 'true':
                cancelled = True
                break
            if chunk:
                bf.write(chunk)
                dl += len(chunk)
                if total > 0:
                    pct = int((dl * 100) / total)
                    if pct != last_pct:
                        progress.update(pct, _addon.getAddonInfo('name'), f"{pct}% - {name}")
                        last_pct = pct

        bf.close()
        bf = None
        progress.close()
        progress_created = False

        if cancelled:
            if target_path:
                if local and os.path.exists(target_path):
                    os.remove(target_path)
                elif not local and xbmcvfs.exists(target_path):
                    xbmcvfs.delete(target_path)
            popinfo(_addon.getLocalizedString(30309) + name, icon=xbmcgui.NOTIFICATION_WARNING)
        else:
            popinfo(_addon.getLocalizedString(30303) + name, sound=True)
    except Exception:
        log(traceback.format_exc(), xbmc.LOGERROR)
        if progress_created:
            try:
                progress.close()
            except Exception:
                pass
        if bf is not None:
            try:
                bf.close()
            except Exception:
                pass
        if target_path:
            try:
                if local and os.path.exists(target_path):
                    os.remove(target_path)
                elif not local and xbmcvfs.exists(target_path):
                    xbmcvfs.delete(target_path)
            except Exception:
                log(traceback.format_exc(), xbmc.LOGERROR)
        popinfo(_addon.getLocalizedString(30304) + name, icon=xbmcgui.NOTIFICATION_ERROR, sound=True)
    finally:
        win.clearProperty(PROP_DOWNLOADING)
        win.clearProperty(PROP_CANCEL_DL)


def menu():
    token, is_vip, vip_days = revalidate(return_status=True)
    xbmcplugin.setPluginCategory(_handle, _addon.getAddonInfo('name'))

    if xbmcgui.Window(10000).getProperty(PROP_DOWNLOADING) == 'true':
        cancel_item = xbmcgui.ListItem(label=f"[COLOR red][B]{_addon.getLocalizedString(30305)}[/B][/COLOR]")
        cancel_item.setArt({'icon': 'DefaultIconError.png'})
        xbmcplugin.addDirectoryItem(_handle, get_url(action='cancel_download'), cancel_item, False)

    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30201))
    listitem.setArt({'icon': 'DefaultAddonsSearch.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='search'), listitem, True)

    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30221))
    listitem.setArt({'icon': 'DefaultFavourites.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='bookmarks'), listitem, True)

    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30202))
    listitem.setArt({'icon': 'DefaultPlaylist.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='queue'), listitem, True)

    listitem = xbmcgui.ListItem(label=_addon.getLocalizedString(30203))
    listitem.setArt({'icon': 'DefaultAddonsUpdates.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='history'), listitem, True)

    settings_label = _addon.getLocalizedString(30204)
    if token:
        if is_vip:
            settings_label += f" [COLOR lime](VIP: {vip_days} {_addon.getLocalizedString(30250)})[/COLOR]"
        else:
            settings_label += f" [COLOR orange]({_addon.getLocalizedString(30251)})[/COLOR]"

    listitem = xbmcgui.ListItem(label=settings_label)
    listitem.setArt({'icon': 'DefaultAddonService.png'})
    xbmcplugin.addDirectoryItem(_handle, get_url(action='settings'), listitem, False)

    xbmcplugin.endOfDirectory(_handle)


def router(paramstring):
    try:
        params = dict(parse_qsl(paramstring))
        action = params.get('action')
        if action == 'search':
            search(params)
        elif action == 'search_tmdb':
            search_tmdb(params)
        elif action == 'show_seasons':
            show_seasons(params)
        elif action == 'season_episodes':
            season_episodes(params)
        elif action == 'download_season':
            download_season(params)
        elif action == 'change_filter':
            change_filter(params)
        elif action in ('bookmarks', 'bookmark_add'):
            bookmarks(params)
        elif action == 'queue':
            queue(params)
        elif action == 'history':
            history(params)
        elif action == 'settings':
            settings(params)
        elif action == 'info':
            info(params)
        elif action == 'play':
            play(params)
        elif action == 'download':
            download(params)
        elif action == 'cancel_download':
            cancel_download(params)
        else:
            menu()
    except Exception:
        err = traceback.format_exc()
        log(err, xbmc.LOGERROR)
        xbmcgui.Dialog().textviewer("YAWsP Error", err)
