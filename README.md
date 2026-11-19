# CAVERON — Salon & Barber

Offline desktop software for billing, groom packages, appointments, staff pay, stock, and thermal slips. The salon file stays on this computer. Nothing is sent to a server.

## Run it

1. Install Python 3.10 or newer and tick “Add python.exe to PATH”.
2. Double-click `run.bat`.
3. The first launch creates `.venv`, installs the libraries, builds the monogram if `assets/caveron_logo.png` is missing, and opens the sign-in screen.

Sign in:

| Desk | Username | Password |
| --- | --- | --- |
| Owner | `admin` | `caveron1987` |
| Reception | `cashier` | `cashier123` |

Change both passwords in Settings → Roles & Security before the salon uses the app.

Reception can bill, book chairs, and track groom packages. The owner also has the menu, staff, payroll, expenses, reports, and settings.

## What is created on first launch

- `caveron_salon.db` — the salon database (WAL mode).
- `backups/caveron_YYYY-MM-DD.db` — one automatic copy per day.
- `assets/caveron_logo.png` — monogram, until you upload the real logo.
- `assets/caveron_logo_thermal.png` — the 1-bit slip version.
- Four sample staff profiles and a small consumables list, so attendance, payroll, and low-stock alerts can be tried immediately. Deactivate anyone who does not work here.

The menu, price ranges, and deals are the CAVERON list in PKR. Range services ask for the agreed price at the till.

## Black Copper printer

1. Install the Windows driver so the printer appears in Windows (BC-85AC, BC-90AC, BC-80, POS-80, POS-58, or another ESC/POS printer).
2. Open Settings → Thermal Printer.
3. Choose the printer. Prefer **Windows Spooler Raw ESC/POS** and **80mm** unless the roll is 58mm.
4. Turn on the logo, address, stylist, barcode, and auto-cut as needed. Cash-drawer kick is off until you enable it.
5. Press **Print test slip**. The preview on the right is the same slip.

If the printer is unplugged, the bill is still saved. A message offers the on-screen slip and a PDF. Switch to **Windows Graphic Print** if the driver refuses raw ESC/POS. Network IP (port 9100) and USB VID/PID are on the same screen.

## Reports and backups

Reports cover today, yesterday, this week, this month, or a custom range. Export PDF, Excel, or CSV, or print through Windows.

Settings → Backup & Reset exports a `.db` file, restores one, or rebuilds the original menu. Type `RESET` for the rebuild. Take a backup first. After a reset, sign in again with `admin` / `caveron1987`.

## Build a single Windows exe

```bat
build_exe.bat
```

The result is `dist\CAVERON.exe`. Copy that file into its own folder and run it. The database, uploaded logo, and `backups` folder are created next to the exe, not inside it. The first start of a one-file build is slower because Windows unpacks it.

Some antivirus tools warn about PyInstaller executables. That warning is about the packer, not this salon app.

## Fonts

`fonts/` includes Cinzel and Plus Jakarta Sans (Latin subset) under the SIL Open Font License. If those files are removed, the app uses Georgia and Segoe UI.
