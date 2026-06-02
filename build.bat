@echo off
chcp 65001 >nul
echo ============================================================
echo  🇹🇷 Türkiye MCP Server — EXE Build Script
echo ============================================================
echo.

:: Python kontrolü
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python bulunamadı! Python 3.10+ yükleyin.
    pause
    exit /b 1
)

:: Gerekli paketleri yükle
echo 📦 Gerekli paketler yükleniyor...
pip install -r requirements.txt
pip install pyinstaller pywebview pystray Pillow keyring

echo.
echo 🔨 EXE oluşturuluyor (bu birkaç dakika sürebilir)...
echo.

:: PyInstaller ile build
pyinstaller --clean turkiye_mcp.spec

if errorlevel 1 (
    echo.
    echo ❌ EXE oluşturulamadı! Hataları kontrol edin.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  ✅ EXE başarıyla oluşturuldu!
echo  📁 Konum: dist\TurkiyeMCP.exe
echo.
echo  Kullanım:
echo    dist\TurkiyeMCP.exe              → GUI ile başlat
echo    dist\TurkiyeMCP.exe --no-gui      → Sadece sunucu
echo    dist\TurkiyeMCP.exe --browser     → Tarayıcıda aç
echo    dist\TurkiyeMCP.exe --port 9090   → Farklı port
echo ============================================================
echo.
pause