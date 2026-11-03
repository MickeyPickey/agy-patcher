# Antigravity Patcher v1.3.1

[Русский](#русский) | [English](#english)

---

<a name="русский"></a>
## Русский

Автономный патчер Antigravity (Desktop, IDE, CLI). Снимает региональные ограничения, изолирует прокси через переменную `AGY_U_PROXY` и решает проблему истекшего внутреннего TLS-сертификата Language Server через `NODE_TLS_REJECT_UNAUTHORIZED`. Без фоновых служб и вотчдогов.

> [!NOTE]
> **Важное примечание:**  
> Патчер выполняет только разблокировку исполняемых файлов. Для работы Antigravity по-прежнему требуется либо настроенный прокси (заданный вручную в `AGY_U_PROXY` или `HTTPS_PROXY`), либо активный VPN.

### Обход истекшего локального TLS-сертификата

Внутренний TLS-сертификат, через который Antigravity IDE общается с локальным Language Server (`127.0.0.1`), имел зашитый срок действия, истекший 3 ноября 2026 года. В результате в Developer Tools (Console) появляются ошибки `certificate has expired`, а чат перестает отвечать.

Опция `NODE_TLS_REJECT_UNAUTHORIZED` (значение `0`) отключает проверку истекшего сертификата для Node.js/Electron.

* В меню TUI: выберите строку `NODE_TLS_REJECT_UNAUTHORIZED` и нажмите `[Space]` или `[Enter]`.
* Через консоль: флаг `--set-tls-ignore` для включения, `--unset-tls-ignore` для отключения.

> [!WARNING]
> Переменная `NODE_TLS_REJECT_UNAUTHORIZED=0` задается на уровне пользователя и действует на все процессы Node.js текущего пользователя.

### Благодарности

Идея проекта вдохновлена репозиторием [confeden/Antigravity](https://github.com/confeden/Antigravity.git) и адаптирована для персонального использования с собственным локальным прокси.

### Быстрый запуск

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
antigravity-patcher.exe --status              # Проверить статус
antigravity-patcher.exe --patch               # Пропатчить все
antigravity-patcher.exe --unpatch             # Откатить все
antigravity-patcher.exe --proxy http://127.0.0.1:10808
antigravity-patcher.exe --set-tls-ignore      # Включить обход истекшего TLS-сертификата (NODE_TLS_REJECT_UNAUTHORIZED=0)
antigravity-patcher.exe --unset-tls-ignore    # Отключить обход TLS-сертификата
```

> **Если ранее стоял сторонний анлокер (Windows):**  
> Отключите фоновый вотчдог: `Disable-ScheduledTask -TaskName "AG Unlocker Watchdog"`

---

<a name="english"></a>
## English

Standalone binary patcher for Antigravity (Desktop, IDE, CLI). Unlocks regional restrictions, isolates proxy routing via `AGY_U_PROXY`, and bypasses expired internal Language Server TLS certificates via `NODE_TLS_REJECT_UNAUTHORIZED`. No background daemons or watchdogs.

> [!NOTE]
> **Important Note:**  
> This patcher only unlocks the executable binaries. For Antigravity to work properly, you still need either a configured proxy (specified manually via `AGY_U_PROXY` or `HTTPS_PROXY`) or an active VPN connection.

### Bypassing Expired Internal TLS Certificate

The internal self-signed TLS certificate used by Antigravity IDE to communicate with the local Language Server (`127.0.0.1`) expired on November 3, 2026. This causes `certificate has expired` errors in the Developer Tools Console and breaks chat response generation.

Setting `NODE_TLS_REJECT_UNAUTHORIZED=0` instructs Node.js/Electron to accept the expired local certificate.

* In TUI menu: select `NODE_TLS_REJECT_UNAUTHORIZED` and press `[Space]` or `[Enter]`.
* Via CLI: `--set-tls-ignore` to enable, `--unset-tls-ignore` to remove.

> [!WARNING]
> Setting `NODE_TLS_REJECT_UNAUTHORIZED=0` applies to all Node.js processes for the current user.

### Acknowledgments

This project was inspired by [confeden/Antigravity](https://github.com/confeden/Antigravity.git) and adapted for personal use with your own custom proxy.

### Quick Start

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
* `[Q]` - quit

### Statuses

* `[Enabled]` (green) - patch active / variable set
* `[Disabled]` (gray) - stock binary / variable not set
* `[Partial]` (yellow) - partially patched
* `[Not Found]` (red) - binary not found

### CLI Commands

```bash
antigravity-patcher.exe --status              # Check status
antigravity-patcher.exe --patch               # Patch all
antigravity-patcher.exe --unpatch             # Revert all
antigravity-patcher.exe --proxy http://127.0.0.1:10808
antigravity-patcher.exe --set-tls-ignore      # Enable expired TLS cert bypass (NODE_TLS_REJECT_UNAUTHORIZED=0)
antigravity-patcher.exe --unset-tls-ignore    # Disable TLS cert bypass
```

> **Windows note (if you used full unlockers previously):**  
> Disable leftover watchdog: `Disable-ScheduledTask -TaskName "AG Unlocker Watchdog"`
