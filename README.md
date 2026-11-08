# Antigravity Patcher v1.4.4

[Русский](#русский) | [English](#english)

---

<a name="русский"></a>
## Русский

Автономный патчер Antigravity (Desktop, IDE, CLI). Снимает региональные ограничения, изолирует прокси через переменную `AGY_U_PROXY`, поддерживает обновленную архитектуру Antigravity IDE (VS Code extension + Hub `~/.gemini/bin/agy.exe`) и решает проблему истекшего внутреннего TLS-сертификата Language Server через `NODE_TLS_REJECT_UNAUTHORIZED`. Без фоновых служб и вотчдогов.

> [!NOTE]
> **Важное примечание:**  
> Патчер выполняет только разблокировку исполняемых файлов. Для работы Antigravity по-прежнему требуется либо настроенный прокси (заданный вручную в `AGY_U_PROXY` или `HTTPS_PROXY`), либо активный VPN.

### Поддержка Antigravity IDE (обновление) и работа без TUN-режима

1. **Новая структура Antigravity IDE**:  
   В свежих версиях Antigravity IDE перешла на расширение `agy` (`google-antigravity`), которое автоматически загружает и запускает Language Server / Hub по пути `~/.gemini/bin/agy.exe` (`~/.gemini/bin/agy` на Linux). Патчер v1.4.0 автоматически находит и патчит этот бекенд, сохраняя точные метки времени `mtime` файла, чтобы не нарушать проверку целостности метаданных `agy.version.json`. Если указать путь к `Antigravity IDE.exe` или папке IDE, патчер корректно свяжет его с целевым бекендом.
2. **Работа без TUN-режима (VPN)**:  
   * Переменная `AGY_U_PROXY` изолированно направляет сетевые запросы пропатченных бинарников (`language_server.exe` и `agy.exe` Hub/CLI) через локальный прокси (например, `http://127.0.0.1:10808`).
   * Для веб-оболочки Electron (`Antigravity.exe`), процесса входа в Google аккаунт и загрузки обновлений расширениями IDE без режима TUN предусмотрена настройка `HTTPS_PROXY` (и синхронизация с `HTTP_PROXY`). Ее можно включить в меню TUI (пункт `HTTPS_PROXY`) или через консоль `--set-https-proxy`.

### Обход истекшего локального TLS-сертификата

Внутренний TLS-сертификат, через который Antigravity IDE общается с локальным Language Server (`127.0.0.1`), имел зашитый срок действия, истекший 3 ноября 2026 года. В результате в Developer Tools (Console) появляются ошибки `certificate has expired`, а чат перестает отвечать.

Опция `NODE_TLS_REJECT_UNAUTHORIZED` (значение `0`) отключает проверку истекшего сертификата для Node.js/Electron.

* В меню TUI: выберите строку `NODE_TLS_REJECT_UNAUTHORIZED` и нажмите `[Space]` или `[Enter]`.
* Через консоль: флаг `--set-tls-ignore` для включения, `--unset-tls-ignore` для отключения.

> [!WARNING]
> Переменная `NODE_TLS_REJECT_UNAUTHORIZED=0` задается на уровне пользователя и действует на все процессы Node.js текущего пользователя.

### Благодарности

Идея проекта вдохновлена репозиторием [confeden/Antigravity](https://github.com/confeden/Antigravity.git) и адаптирована для персонального использования с собственным локальным прокси.

### Быстрый запуск и установка

При первом запуске скрипт предложит установить `agy-patcher` в систему (PATH). После установки патчер доступен напрямую через команду `agy-patcher` в любом терминале (PowerShell, CMD, Bash).

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex
```

**Linux (Bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash
```

### Управление в меню (TUI)

* `[Up]` / `[Down]` - перемещение
* `[Space]` / `[Enter]` - переключить / применить
* `[Q]` - выход

### Статусы

* `[Enabled]` (зеленый) - патч активен / переменная задана
* `[Disabled]` (серый) - оригинальный файл / переменная не задана
* `[Partial]` (желтый) - применен один из патчей
* `[Not Found]` (красный) - файл не найден

### Консольные команды

```bash
agy-patcher --status              # Проверить статус
agy-patcher --patch               # Пропатчить все
agy-patcher --unpatch             # Откатить все
agy-patcher --proxy http://127.0.0.1:10808
agy-patcher --set-proxy           # Задать AGY_U_PROXY
agy-patcher --unset-proxy         # Удалить AGY_U_PROXY
agy-patcher --set-https-proxy     # Задать HTTPS_PROXY и HTTP_PROXY (для работы без TUN)
agy-patcher --unset-https-proxy   # Удалить HTTPS_PROXY и HTTP_PROXY
agy-patcher --set-tls-ignore      # Включить обход истекшего TLS-сертификата (NODE_TLS_REJECT_UNAUTHORIZED=0)
agy-patcher --unset-tls-ignore    # Отключить обход TLS-сертификата
agy-patcher --update              # Проверить и обновить патчер до актуальной версии
agy-patcher --uninstall           # Удалить патчер из системы и очистить PATH
```

> **Если ранее стоял сторонний анлокер (Windows):**  
> Отключите фоновый вотчдог: `Disable-ScheduledTask -TaskName "AG Unlocker Watchdog"`

---

<a name="english"></a>
## English

Standalone binary patcher for Antigravity (Desktop, IDE, CLI). Unlocks regional restrictions, isolates proxy routing via `AGY_U_PROXY`, supports modernized Antigravity IDE architecture (VS Code extension + Hub `~/.gemini/bin/agy.exe`), and bypasses expired internal Language Server TLS certificates via `NODE_TLS_REJECT_UNAUTHORIZED`. No background daemons or watchdogs.

> [!NOTE]
> **Important Note:**  
> This patcher only unlocks the executable binaries. For Antigravity to work properly, you still need either a configured proxy (specified manually via `AGY_U_PROXY` or `HTTPS_PROXY`) or an active VPN connection.

### Antigravity IDE Update & Non-TUN Operation

1. **Modern Antigravity IDE Architecture**:  
   Recent Antigravity IDE versions use the `agy` (`google-antigravity`) extension which acquires and spawns the backend Language Server / Hub at `~/.gemini/bin/agy.exe` (`~/.gemini/bin/agy` on Linux). Patcher v1.4.0 automatically discovers and patches this backend while preserving exact file `mtime` to satisfy `agy.version.json` sidecar integrity checks. Passing `Antigravity IDE.exe` or the IDE installation directory automatically resolves to this backend.
2. **Operation without TUN Mode (VPN)**:  
   * `AGY_U_PROXY` isolates proxy routing exclusively to patched backend binaries (`language_server.exe` and `agy.exe` Hub/CLI).
   * For the Electron UI (`Antigravity.exe`), Google OAuth sign-in, and IDE extension downloads without TUN mode, toggle `HTTPS_PROXY` (and synchronized `HTTP_PROXY`) in the TUI menu or via `--set-https-proxy`.

### Bypassing Expired Internal TLS Certificate

The internal self-signed TLS certificate used by Antigravity IDE to communicate with the local Language Server (`127.0.0.1`) expired on November 3, 2026. This causes `certificate has expired` errors in the Developer Tools Console and breaks chat response generation.

Setting `NODE_TLS_REJECT_UNAUTHORIZED=0` instructs Node.js/Electron to accept the expired local certificate.

* In TUI menu: select `NODE_TLS_REJECT_UNAUTHORIZED` and press `[Space]` or `[Enter]`.
* Via CLI: `--set-tls-ignore` to enable, `--unset-tls-ignore` to remove.

> [!WARNING]
> Setting `NODE_TLS_REJECT_UNAUTHORIZED=0` applies to all Node.js processes for the current user.

### Acknowledgments

This project was inspired by [confeden/Antigravity](https://github.com/confeden/Antigravity.git) and adapted for personal use with your own custom proxy.

### Quick Start & Installation

On first run, the script prompts to install `agy-patcher` into your system PATH. Once installed, it is directly accessible as `agy-patcher` from any terminal (PowerShell, CMD, Bash).

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex
```

**Linux (Bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash
```

### Controls (TUI)

* `[Up]` / `[Down]` - navigate
* `[Space]` / `[Enter]` - toggle / apply
* `[Esc]` / `[Q]` - quit (supports non-English layouts)

### Statuses

* `[Enabled]` (green) - patch active / variable set
* `[Disabled]` (gray) - stock binary / variable not set
* `[Partial]` (yellow) - partially patched
* `[Not Found]` (red) - binary not found

### CLI Commands

```bash
agy-patcher --status              # Check status
agy-patcher --patch               # Patch all
agy-patcher --unpatch             # Revert all
agy-patcher --proxy http://127.0.0.1:10808
agy-patcher --set-proxy           # Set AGY_U_PROXY
agy-patcher --unset-proxy         # Remove AGY_U_PROXY
agy-patcher --set-https-proxy     # Set HTTPS_PROXY and HTTP_PROXY (for non-TUN operation)
agy-patcher --unset-https-proxy   # Remove HTTPS_PROXY and HTTP_PROXY
agy-patcher --set-tls-ignore      # Enable expired TLS cert bypass (NODE_TLS_REJECT_UNAUTHORIZED=0)
agy-patcher --unset-tls-ignore    # Disable TLS cert bypass
agy-patcher --update              # Check for updates and update in place
agy-patcher --uninstall           # Uninstall agy-patcher and clean PATH
```

> **Windows note (if you used full unlockers previously):**  
> Disable leftover watchdog: `Disable-ScheduledTask -TaskName "AG Unlocker Watchdog"`
