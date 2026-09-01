> 🔗 Task: /Users/viktor/Projects/vschk-platform/tasks/log/2026-07-22-vschk-platform--622-vpn-via-ai-coder-course/task.md
> 🔗 Course chapter: [Глава 4 — Готовый промпт для AI-кодера](./course-content-full.md#глава-4--готовый-промпт-для-ai-кодера)

# AI-Coder Prompt — свой VPN на Xray + VLESS + Reality

Полный промпт для Claude Code / Cursor / Codex, который поднимает персональный VPN на твоём VDS за 10-15 минут. Плюс готовые под-промпты на расширение (добавить клиента, сменить IP, переехать, настроить мониторинг).

---

## Как пользоваться

1. Убедись что выполнены главы 1-3 курса: сервер заказан, IP получен, SSH-ключ добавлен, домен (опционально) настроен
2. Открой Claude Code (или Cursor / Codex) в любой пустой папке — например `~/vpn-setup/`
3. Скопируй **основной промпт** (раздел ниже), подставь placeholders, вставь в чат
4. Разрешай SSH и bash-действия по мере запросов AI
5. Дождись финального вывода: VLESS URI + QR
6. При необходимости — используй **интеграционные промпты** (добавить клиента, сменить IP и т.д.)

---

## Placeholders — что подставлять

| Placeholder | Что это | Пример | Обязательный |
|---|---|---|---|
| `<YOUR_SERVER_IP>` | IP твоего VDS из панели Timeweb | `1.2.3.4` | ✅ да |
| `<YOUR_DOMAIN>` | Домен из главы 3, или `none` если пропустил | `vpn.example.com` / `none` | ✅ да |
| `<YOUR_TG>` | Твой Telegram-хендл без `@` (пойдёт в имя первого клиента) | `mynickname` | ✅ да |
| `<SSH_KEY_PATH>` | Путь к твоему приватному SSH-ключу (обычно можно опустить, AI возьмёт дефолт) | `~/.ssh/id_ed25519` | ⭕ нет |

> ⚠️ Все примеры в этой странице — **фейковые** (`1.2.3.4`, `mynickname`, случайные UUID/ключи). При выполнении промпта AI сгенерит для тебя настоящие credentials. **Никому не показывай их** — с ними чужой человек залезет на твой VPN как один из твоих клиентов.

**Проверка перед стартом:**

```bash
# 1. Сервер отвечает по SSH?
ssh root@<YOUR_SERVER_IP> "uname -a && lsb_release -a"

# 2. DNS резолвится (если указал домен)?
dig +short <YOUR_DOMAIN>
# должен вернуть <YOUR_SERVER_IP>
```

Если оба ок — можно копировать основной промпт ниже.

---

## Основной промпт (копировать целиком)

````
Server IP: <YOUR_SERVER_IP>
Domain (empty if none): <YOUR_DOMAIN>
Owner tag: <YOUR_TG>

Ты — DevOps agent. Задача: поднять на указанном сервере (Ubuntu 24.04 LTS)
персональный VPN на Xray-core с протоколом VLESS + Reality. Работай через
SSH (`ssh root@<Server IP>`). После каждого этапа проверяй что он выполнен
успешно, только тогда переходи к следующему.

## Этапы

### 1. Baseline hardening

```bash
apt update && apt upgrade -y
apt install -y ufw curl wget qrencode jq fail2ban ca-certificates net-tools

# UFW
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 443/tcp comment 'VLESS'
ufw --force enable

# fail2ban
cat > /etc/fail2ban/jail.d/sshd.local <<EOF
[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
findtime = 600
bantime = 3600
EOF
systemctl restart fail2ban
systemctl enable fail2ban

# Timezone + hostname
timedatectl set-timezone UTC
hostnamectl set-hostname my-vpn
```

Проверь:
- `ufw status verbose` → active, разрешены 22 + 443
- `systemctl status fail2ban` → active
- `free -h` → минимум 500 MB RAM свободно
- `df -h /` → минимум 5 GB свободно на диске

### 2. Установка Xray-core

```bash
bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install
```

Проверь:
- `xray version` → 25.x или новее
- `systemctl status xray` → active (может быть failed из-за дефолтного пустого конфига — это ок, поправим на этапе 4)

### 3. Генерация ключей Reality + UUID первого клиента

```bash
# Reality keypair
xray x25519
# → выведет: Private key: XXX / Public key: YYY

# ShortId (8 байт hex)
openssl rand -hex 8
# → выведет: 8 hex-символов

# UUID клиента
cat /proc/sys/kernel/random/uuid
# → выведет: standard UUID v4
```

Сохрани эти четыре значения. Дальше подставишь их в config.json.

### 4. Собери /usr/local/etc/xray/config.json

Используй режим Reality (маскировка под www.apple.com) независимо от того
указан домен или нет. Домен нужен только чтобы клиент коннектился по
красивому адресу вместо IP, но на server side всё через Reality.

Шаблон:

```json
{
  "log": {
    "loglevel": "warning",
    "access": "/var/log/xray/access.log",
    "error": "/var/log/xray/error.log"
  },
  "inbounds": [
    {
      "listen": "0.0.0.0",
      "port": 443,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "<GENERATED_UUID>",
            "email": "<Owner tag>-mac",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "www.apple.com:443",
          "xver": 0,
          "serverNames": ["www.apple.com"],
          "privateKey": "<GENERATED_PRIVATE_KEY>",
          "shortIds": ["<GENERATED_SHORT_ID>"]
        }
      },
      "sniffing": {
        "enabled": true,
        "destOverride": ["http", "tls", "quic"]
      }
    }
  ],
  "outbounds": [
    {"protocol": "freedom", "tag": "direct"},
    {"protocol": "blackhole", "tag": "block"}
  ]
}
```

Прежде чем сохранить — валидируй:

```bash
xray -test -c /path/to/config.json
```

Если валидация ок — положи в `/usr/local/etc/xray/config.json`, установи права:

```bash
chmod 644 /usr/local/etc/xray/config.json
chown root:root /usr/local/etc/xray/config.json
mkdir -p /var/log/xray
```

### 5. Рестарт Xray + проверка

```bash
systemctl restart xray
sleep 2
systemctl status xray
journalctl -u xray -n 30 --no-pager
ss -tlnp | grep :443
```

Ожидаемо:
- systemd status = active (running)
- journalctl без FATAL / ERROR
- `ss -tlnp` → xray слушает 0.0.0.0:443

### 6. Собери VLESS URI + QR-код

Формат URI:

```
vless://<UUID>@<HOST>:443?security=reality&sni=www.apple.com&fp=chrome&pbk=<PUBLIC_KEY>&sid=<SHORT_ID>&type=tcp&flow=xtls-rprx-vision&encryption=none#<Owner tag>-mac
```

Где `<HOST>` = Domain если указан и не `none`, иначе Server IP.

QR-код:

```bash
echo 'vless://...' | qrencode -t ANSIUTF8
```

### 7. Итоговый отчёт

Выведи мне в чат:

1. **VLESS URI** — полная строка в одном code block, готова к копированию в буфер
2. **QR-код** — ASCII, чтобы можно было отсканировать с телефона прямо с экрана мака
3. **Команда для добавления второго клиента** — краткий пример SQL / sed / jq на будущее
4. **Команда проверки статуса** — `systemctl status xray && ss -tlnp | grep :443 && journalctl -u xray -n 5`
5. **Файлы что изменил** — короткий список путей

## Правила работы

- **Идемпотентность:** каждый этап можно перезапустить без вреда
- **Всегда `set -euo pipefail`** в bash-скриптах
- **Валидируй JSON** через `xray -test` перед сохранением config.json
- **Проверка после каждого этапа** — не переходи дальше пока предыдущий не завершён
- **Никаких паролей в консоль** — только SSH-ключ
- Если ошибка — не глотай, покажи мне вывод и предложи фикс
- Если что-то неоднозначно — спроси меня, не гадай
- **Backup config.json** перед любым изменением: `cp config.json config.json.bak.$(date +%s)`

Начинай.
````

---

## Что должен вернуть AI (пример ожидаемого вывода)

После успешного прогона AI должен ответить примерно так:

````
Готово. VPN поднят на 1.2.3.4.

## VLESS URI

vless://00000000-0000-0000-0000-000000000000@1.2.3.4:443?security=reality&sni=www.apple.com&fp=chrome&pbk=EXAMPLE_PUBLIC_KEY_REPLACED_BY_AI&sid=0000000000000000&type=tcp&flow=xtls-rprx-vision&encryption=none#mynickname-mac

## QR-код

█▀▀▀▀▀█ ▀█▄▀▄▄ █▀▀▀▀▀█
█ ███ █ ▄▄█▀█▀ █ ███ █
...
█▄▄▄▄▄█ ▀ █ ▀▄ █▄▄▄▄▄█

## Изменил

- /usr/local/etc/xray/config.json (создал)
- /etc/systemd/system/xray.service (создал installer'ом)
- /etc/ufw/user.rules (добавил 443/tcp)
- /etc/fail2ban/jail.d/sshd.local (создал)
- /etc/hostname → my-vpn
- Установил пакеты: ufw curl wget qrencode jq fail2ban ca-certificates

## Проверка статуса

systemctl status xray:  active (running) since 2026-08-05 14:30:22 UTC
ss -tlnp | grep :443:   LISTEN 0.0.0.0:443 users:(("xray",pid=12345,fd=6))
journalctl -u xray -n 5: (no errors, только startup messages)

Готов добавить второго клиента когда скажешь.
````

Если ты видишь в чате AI такой отчёт — **всё сделано, можно переходить к главе 6 курса** (импорт URI в Happ).

---

## Интеграционные промпты (готовые к копированию)

### Добавить второго / третьего клиента

````
На моём VPN <YOUR_SERVER_IP> добавь ещё одного клиента.

Имя клиента: <NEW_CLIENT_NAME>   # например: viktor-iphone, lena-mac

Задача:
1. Сгенерируй новый UUID (`cat /proc/sys/kernel/random/uuid`)
2. Сгенерируй новый shortId (`openssl rand -hex 8`)
3. Через jq (или sed) добавь в /usr/local/etc/xray/config.json:
   - в `inbounds[0].settings.clients` — новую запись с UUID/email/flow=xtls-rprx-vision
   - в `inbounds[0].streamSettings.realitySettings.shortIds` — новый shortId
4. Валидируй: xray -test -c /usr/local/etc/xray/config.json
5. Рестарт: systemctl restart xray
6. Проверь: journalctl -u xray -n 20 без ошибок
7. Собери VLESS URI для этого клиента (тот же формат что для первого)
8. Выведи мне: URI + QR-код + команду для удаления этого клиента (на будущее)

Backup config.json перед изменениями.
````

### Удалить клиента

````
На моём VPN <YOUR_SERVER_IP> удали клиента с email <CLIENT_NAME>.

Задача:
1. Backup config.json
2. Через jq удали запись из `inbounds[0].settings.clients` где email == <CLIENT_NAME>
3. Опционально удали shortId клиента из `realitySettings.shortIds` (найди по subId/email mapping)
4. Валидируй + рестарт Xray
5. Подтверди что клиента больше нет в конфиге
````

### Пересоздать сервер с миграцией конфига (при смене IP)

````
Мой VPN на <OLD_IP> капчит Cloudflare / отвалился. 
Хочу пересоздать VDS с тем же тарифом на Timeweb Cloud, получить новый IP,
и накатить существующий конфиг обратно.

Задача:
1. Скачай /usr/local/etc/xray/config.json с <OLD_IP> локально
2. Дай мне команду через Timeweb API (или инструкции через web-панель) 
   как пересоздать VDS с тем же тарифом и OS
3. После того как получу новый IP — я его скажу тебе
4. Прогони на новом IP основной промпт (baseline + xray install), 
   но БЕЗ этапа 3 (генерации ключей) и БЕЗ этапа 4 (сборки config'а с нуля).
   Вместо этого — накати сохранённый config.json как есть
5. Рестарт Xray + проверка
6. Сгенерируй мне новые VLESS URI для КАЖДОГО клиента (с новым IP но старыми UUID/keys)
7. Дай список URI для рассылки клиентам
````

### Переехать на другого хостера (Aeza / Hetzner / 1984)

````
Хочу переехать с Timeweb на <NEW_HOSTER> (например Aeza в NL / Hetzner в FI / 1984 в IS).

Задача:
1. Забэкапь /usr/local/etc/xray/config.json + /etc/systemd/system/xray.service со старого сервера
2. Инструкции как заказать VDS у <NEW_HOSTER> с параметрами: 
   Ubuntu 24.04 LTS, 1 vCPU, 1 GB RAM, локация вне РФ, порт 443 open
3. После заказа — я скажу тебе новый IP
4. Прогони на новом IP полный setup (baseline + xray install + накатка конфига)
5. Дай новые VLESS URI + инструкции клиентам

Особое внимание: 
- новый провайдер может отличаться правилами firewall — проверь UFW внутри + firewall на уровне хостера
- если MTU другой — возможно потребуется настройка через iface configuration
````

### Добавить домен и TLS позже (после того как VPN уже работает на Reality)

````
Мой VPN работает на <YOUR_SERVER_IP> в режиме Reality (маска под apple.com).
Хочу добавить свой домен <YOUR_DOMAIN> для клиентского подключения по красивому адресу.

Задача:
1. Проверь что <YOUR_DOMAIN> резолвится на <YOUR_SERVER_IP>: `dig +short <YOUR_DOMAIN>`
2. Обнови все существующие VLESS URI: заменить <YOUR_SERVER_IP> на <YOUR_DOMAIN> в `@` части
3. Верни мне обновлённые URI для рассылки клиентам

На сервере МЕНЯТЬ НИЧЕГО НЕ НАДО — Reality serverName это `www.apple.com`, 
он не зависит от того по какому адресу клиент коннектится.
````

### Мониторинг + автобэкап (setup-and-forget)

````
Настрой на моём VPN-сервере <YOUR_SERVER_IP> systemd services / cron jobs:

1. **Ежедневный бэкап конфига** (03:00 UTC):
   - Копировать /usr/local/etc/xray/config.json в /root/backups/xray-YYYYMMDD.json
   - Retention 30 дней (удалять старые через find -mtime +30)
   - Bash-скрипт положи в /root/scripts/backup-xray.sh, cron в /etc/cron.d/xray-backup

2. **Uptime monitor** (каждые 5 минут):
   - Проверять `systemctl is-active xray`
   - Если not-active — 3 попытки рестарта через systemctl restart, между попытками sleep 30
   - Если после 3 попыток всё ещё not-active — слать мне сообщение в Telegram 
     через `curl https://api.telegram.org/bot<TOKEN>/sendMessage`
   - Токен и chat_id я скажу отдельно (или скажи как их получить через @BotFather)
   - Bash-скрипт в /root/scripts/xray-uptime.sh, cron */5 в /etc/cron.d/xray-uptime

3. **Log rotation** для /var/log/xray/access.log и error.log:
   - Стандартный logrotate config в /etc/logrotate.d/xray
   - Rotate weekly, keep 4, compress

4. **Auto-update Xray** ежемесячно:
   - Cron 1 числа месяца в 04:00 UTC:
     `bash -c "$(curl -L https://github.com/XTLS/Xray-install/raw/main/install-release.sh)" @ install`
   - После update — systemctl restart xray + проверка status
   - Если проблема — писать в TG (тот же бот)

Все логи операций — в /var/log/vpn-ops/*.log.

После setup — покажи мне статус всех cron jobs и первый запуск каждого скрипта manually для теста.
````

---

## Troubleshooting recipes

### AI застрял в середине основного промпта

````
Продолжи с этапа <N> setup'а VPN на <YOUR_SERVER_IP>.

Перед продолжением проверь текущее состояние сервера:
- Что уже установлено: `dpkg -l | grep -E 'xray|ufw|fail2ban'`
- Есть ли config: `ls -la /usr/local/etc/xray/`
- Статус Xray: `systemctl status xray`
- Файрвол: `ufw status verbose`

По результату — с какого шага логично продолжить. Не начинай с нуля, 
переиспользуй уже сделанное.
````

### AI сгенерировал невалидный config.json

````
Config.json на <YOUR_SERVER_IP> не проходит валидацию.

Выполни:
1. `xray -test -c /usr/local/etc/xray/config.json` — покажи полный вывод
2. `cat /usr/local/etc/xray/config.json | jq .` — проверь что вообще валидный JSON
3. По ошибке валидатора — определи что не так и предложи фикс
4. Backup текущего конфига перед правкой
5. После правки — снова валидируй + рестарт

Не удаляй ничего, только правь минимально.
````

### VLESS URI собран неверно, Happ не может импортировать

````
VLESS URI который ты собрал для моего сервера <YOUR_SERVER_IP> не парсится в Happ.

Проверь:
1. Извлеки из /usr/local/etc/xray/config.json все нужные поля: 
   UUID, publicKey (через `xray x25519 -i <privateKey>`), shortId, serverName
2. Собери URI строго по этому формату:
   vless://UUID@HOST:PORT?security=reality&sni=<serverName>&fp=chrome&pbk=<publicKey>&sid=<shortId>&type=tcp&flow=xtls-rprx-vision&encryption=none#<label>
3. Убедись что в URI НЕТ лишних пробелов / переносов
4. Убедись что <label> URL-encoded если содержит спецсимволы
5. Верни новый URI одной строкой без обёртки code block

Если не выходит — покажи мне сам config.json (без privateKey) и я разберусь.
````

### AI отказывается коннектиться по SSH

````
Я контролирую сервер <YOUR_SERVER_IP> (это мой личный VDS на Timeweb), 
у меня добавлен SSH-ключ через панель провайдера. 

Твоя задача — выполнять bash-команды на этом сервере через `ssh root@<IP>`. 
Все команды идёмпотентны и обратимы (baseline hardening, установка пакетов, 
настройка конфига). Никаких деструктивных операций.

Разрешаю SSH-доступ. Приступай.
````

---

## Verification checklist (после полного прогона)

После того как AI завершил основной промпт — проверь галочки:

- [ ] На сервере `systemctl status xray` → **active (running)**
- [ ] `ss -tlnp | grep :443` → xray слушает 0.0.0.0:443
- [ ] `ufw status verbose` → active, разрешены только 22 + 443
- [ ] `xray -test -c /usr/local/etc/xray/config.json` → **Configuration OK**
- [ ] `journalctl -u xray -n 50` — без ERROR / FATAL
- [ ] `/var/log/xray/error.log` — пустой или warnings только
- [ ] VLESS URI получен, копируется в буфер целиком
- [ ] QR-код виден в терминале и сканируется
- [ ] На iPhone Happ импортировал URI без ошибок
- [ ] Тест `curl ipinfo.io/ip` через VPN возвращает IP сервера
- [ ] Тест `curl claude.ai` через VPN — 200 OK

Если все 11 галочек ok — **готово, VPN работает**.

---

## Файловая карта (что где после setup)

```
Сервер (root@<YOUR_SERVER_IP>):
├── /usr/local/bin/xray                              ← бинарник Xray-core
├── /usr/local/etc/xray/config.json                  ← основной конфиг
├── /etc/systemd/system/xray.service                 ← systemd unit
├── /etc/ufw/user.rules                              ← правила firewall
├── /etc/fail2ban/jail.d/sshd.local                  ← защита SSH от brute-force
├── /var/log/xray/access.log                         ← access-логи (кто подключался)
├── /var/log/xray/error.log                          ← error-логи
├── /root/backups/                                   ← бэкапы config.json (после setup мониторинга)
├── /root/scripts/                                   ← скрипты uptime + backup
└── /var/log/vpn-ops/                                ← логи собственных скриптов

Локально (мак):
├── ~/vpn-setup/                                    ← рабочая папка Claude Code сессии
└── ~/1password / bitwarden                         ← бэкап privateKey Reality + URI
```

---

**Автор:** Виктор Васечка [@bearded_illirian](https://t.me/bearded_illirian)
**Часть курса:** [Как собрать свой VPN за 1 час](./course-content-full.md)
