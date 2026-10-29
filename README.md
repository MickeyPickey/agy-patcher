# Antigravity Patcher v1.0.0

[Русский](#русский) | [English](#english)

---

<a name="русский"></a>
## Русский

Автономный патчер Antigravity (Desktop, IDE, CLI). Снимает региональные ограничения и изолирует прокси через переменную `AGY_U_PROXY`. Без фоновых служб и вотчдогов.

> [!NOTE]
> **Важное примечание:**  
> Патчер выполняет только разблокировку исполняемых файлов. Для работы Antigravity по-прежнему требуется либо настроенный прокси (заданный вручную в `AGY_U_PROXY` или `HTTPS_PROXY`), либо активный VPN.

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
```

> **Если ранее стоял сторонний анлокер (Windows):**  
> Отключите фоновый вотчдог: `Disable-ScheduledTask -TaskName "AG Unlocker Watchdog"`

---

<a name="english"></a>
## English

Standalone binary patcher for Antigravity (Desktop, IDE, CLI). Unlocks regional restrictions and isolates proxy routing via `AGY_U_PROXY`. No background daemons or watchdogs.

> [!NOTE]
> **Important Note:**  
> This patcher only unlocks the executable binaries. For Antigravity to work properly, you still need either a configured proxy (specified manually via `AGY_U_PROXY` or `HTTPS_PROXY`) or an active VPN connection.

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
```

> **Windows note (if you used full unlockers previously):**  
> Disable leftover watchdog: `Disable-ScheduledTask -TaskName "AG Unlocker Watchdog"`
