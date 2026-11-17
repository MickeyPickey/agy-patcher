# Antigravity Patcher v1.4.4

[Русский](#русский) | [English](#english)

---

<a name="русский"></a>
## Русский

Патчер для **Antigravity** (Desktop, IDE, CLI): снимает региональные ограничения, изолирует прокси (`AGY_U_PROXY`), обходит истекший локальный TLS-сертификат и автоматически перепатчивает приложения после обновлений.

> [!NOTE]
> Для работы Antigravity по-прежнему нужен рабочий прокси (`AGY_U_PROXY` / `HTTPS_PROXY`) или VPN.

### 1. Установка и запуск

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex
```

**Linux / Termux / PRoot (Bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash
```

### 2. Быстрая настройка в меню (TUI)

Навигация: `↑`/`↓`, переключить: `Space`/`Enter`, выход: `Q`.

1. **Прокси (если нет VPN в TUN-режиме):** включите `AGY_U_PROXY` (для бекенда) и при необходимости `HTTPS_PROXY` (для входа и UI).
2. **Патч:** выберите `Patch All Detected Applications` (или нужные приложения по отдельности).
3. **Авто-патчинг после обновлений:** включите `Auto-Patch Watchdog` (и `Watch Notifications` по желанию).
4. **Если чат не отвечает из-за TLS (`certificate has expired`):** включите `NODE_TLS_REJECT_UNAUTHORIZED`.

### Основные команды CLI

```bash
agy-patcher                  # Открыть меню (TUI)
agy-patcher --status         # Статус патчей, прокси и вотчдога
agy-patcher --patch          # Пропатчить все
agy-patcher --unpatch        # Откатить все
agy-patcher --enable-auto    # Включить авто-патчинг после обновлений
agy-patcher --disable-auto   # Отключить авто-патчинг
agy-patcher --watch-log      # Лог и статус вотчдога
agy-patcher --update         # Обновить agy-patcher
agy-patcher --uninstall      # Удалить из системы
```

---

<a name="english"></a>
## English

Lightweight patcher for **Antigravity** (Desktop, IDE, CLI): unlocks regional restrictions, isolates proxy routing (`AGY_U_PROXY`), bypasses expired local TLS certificates, and automatically re-patches apps after updates.

> [!NOTE]
> You still need a working proxy (`AGY_U_PROXY` / `HTTPS_PROXY`) or active VPN for Antigravity to connect.

### 1. Install & Run

**Windows (PowerShell):**
```powershell
irm https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.ps1 | iex
```

**Linux / Termux / PRoot (Bash):**
```bash
curl -fsSL https://raw.githubusercontent.com/MickeyPickey/agy-patcher/main/run.sh | bash
```

### 2. Quick Setup (TUI)

Controls: `↑`/`↓` navigate, `Space`/`Enter` toggle, `Q` quit.

1. **Proxy (if not using TUN VPN):** enable `AGY_U_PROXY` (backend) and `HTTPS_PROXY` (sign-in / Electron UI) if needed.
2. **Patch:** select `Patch All Detected Applications` (or toggle apps individually).
3. **Auto-patch updates:** enable `Auto-Patch Watchdog` (and `Watch Notifications` if desired).
4. **Expired local TLS (`certificate has expired`):** enable `NODE_TLS_REJECT_UNAUTHORIZED`.

### Essential CLI Commands

```bash
agy-patcher                  # Open interactive menu (TUI)
agy-patcher --status         # Show patch, proxy, and watchdog status
agy-patcher --patch          # Patch all
agy-patcher --unpatch        # Revert all
agy-patcher --enable-auto    # Enable auto-patching after updates
agy-patcher --disable-auto   # Disable auto-patching
agy-patcher --watch-log      # Show watchdog status and recent log
agy-patcher --update         # Update agy-patcher
agy-patcher --uninstall      # Uninstall completely
```
