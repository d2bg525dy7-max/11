import os, json, time, re
from pathlib import Path
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('VK_TOKEN', '').strip()
ADMIN_IDS = {int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip().isdigit()}
DATA_DIR = Path('data')
DATA_DIR.mkdir(exist_ok=True)
ACCESS_FILE = DATA_DIR / 'access.json'
LISTS_FILE = DATA_DIR / 'lists.json'

DEFAULT_LISTS = {
    "1": {"name": "Лидеры МВД", "members": []},
    "2": {"name": "Лидеры МО", "members": []},
    "3": {"name": "Лидеры МЗ", "members": []},
    "4": {"name": "Лидер Правительства", "members": []},
    "5": {"name": "Лидер НГ-А", "members": []},
    "6": {"name": "Лидер МРЭО", "members": []},
    "7": {"name": "Окружной судья", "members": []},
    "8": {"name": "Министры", "members": []},
}

def load_json(path, default):
    if not path.exists():
        path.write_text(json.dumps(default, ensure_ascii=False, indent=2), encoding='utf-8')
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return default

def save_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

access = load_json(ACCESS_FILE, [])
if not isinstance(access, list): access = []
lists_data = load_json(LISTS_FILE, DEFAULT_LISTS)


def send(vk, peer_id, text):
    vk.messages.send(peer_id=peer_id, message=text, random_id=0)

def is_admin(user_id):
    return user_id in ADMIN_IDS

def extract_user_id(text):
    text = text.strip()
    m = re.search(r'(?:vk\.com/)?(?:id)?(\d+)', text)
    if m: return int(m.group(1))
    m = re.search(r'\[(id(\d+)|club(\d+)|public(\d+))\|', text)
    if m: return int(m.group(2) or m.group(3) or m.group(4))
    return None

def help_text():
    return ("⚠️ Неизвестная команда. Проверьте правильность написания.\n\n"
            "Доступные команды:\n"
            "/d add <ссылка VK или @username/ID> — выдача доступа\n"
            "/d del <@username/ID> — удаление доступа\n"
            "/ping — время ответа бота\n"
            "/list <ID форумного списка> — список участников\n\n"
            "ID форумных списков:\n"
            "1 — Лидеры МВД\n2 — Лидеры МО\n3 — Лидеры МЗ\n4 — Лидер Правительства\n"
            "5 — Лидер НГ-А\n6 — Лидер МРЭО\n7 — Окружной судья\n8 — Министры\n\n"
            "Аргументы в <угловых> скобках обязательны, а в [квадратных] — необязательны.")


if not TOKEN:
    raise SystemExit('Не задан VK_TOKEN в .env')
vk_session = vk_api.VkApi(token=TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)
print('VK bot started and polling...')

for event in longpoll.listen():
    if event.type != VkEventType.MESSAGE_NEW or not event.from_user:
        continue
    msg = (event.text or '').strip()
    peer = event.peer_id
    uid = event.user_id
    low = msg.lower()
    if low == '/ping':
        started = time.perf_counter()
        try:
            vk.users.get(user_ids=[uid])
            elapsed = round((time.perf_counter()-started)*1000)
            send(vk, peer, f'🏓 Pong! Время ответа VK API: {elapsed} мс')
        except Exception:
            send(vk, peer, '⚠️ Не удалось проверить ответ VK API.')
        continue
    if low.startswith('/d add'):
        if not is_admin(uid):
            send(vk, peer, '⛔ Недостаточно прав.')
            continue
        target = extract_user_id(msg[len('/d add'):])
        if not target:
            send(vk, peer, 'Использование: /d add <ссылка VK или ID>')
            continue
        if target in access:
            send(vk, peer, 'ℹ️ У пользователя уже есть доступ.')
        else:
            access.append(target)
            save_json(ACCESS_FILE, access)
            send(vk, peer, f'✅ Доступ выдан пользователю ID {target}.')
        continue
    if low.startswith('/d del'):
        if not is_admin(uid):
            send(vk, peer, '⛔ Недостаточно прав.')
            continue
        target = extract_user_id(msg[len('/d del'):])
        if not target:
            send(vk, peer, 'Использование: /d del <ссылка VK или ID>')
            continue
        if target in access:
            access.remove(target)
            save_json(ACCESS_FILE, access)
            send(vk, peer, f'✅ Доступ пользователя ID {target} удалён.')
        else:
            send(vk, peer, 'ℹ️ У пользователя нет доступа.')
        continue
    if low.startswith('/list') or low.startswith('/список'):
        parts = msg.split()
        if len(parts) != 2 or not parts[1].isdigit() or parts[1] not in lists_data:
            send(vk, peer, '⚠️ Используйте: /list <ID форумного списка> (ID от 1 до 8)')
            continue
        list_id = parts[1]
        item = lists_data[list_id]
        members = item.get('members', [])
        title = item.get('name', 'Список')
        if not members:
            send(vk, peer, f'📋 {title}\nСписок пока пуст. Добавьте участников в data/lists.json.')
        else:
            lines = [f'📋 {title} ({len(members)}):']
            for member in members:
                lines.append(f'• {member}')
            send(vk, peer, '\n'.join(lines))
        continue
    if low in ('/help', '/команды', '/start'):
        send(vk, peer, help_text())
        continue
    if msg.startswith('/'):
        send(vk, peer, help_text())
