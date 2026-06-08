#!/bin/bash
# Türkiye MCP Server — macOS Kurulum Betiği
# Bu betik macOS'te Turkiye MCP'yi kurar ve çalıştırır.
#
# Kullanım:
#   chmod +x install-macos.command
#   ./install-macos.command
#
# VEYA Terminal'den:
#   bash install-macos.sh

set -e

# Renk tanımları
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🇹🇷 Türkiye MCP Server — macOS Kurulumu${NC}"
echo "============================================"
echo ""

# 1. Python 3.11+ kontrolü
echo -e "${YELLOW}[1/5] Python kontrol ediliyor...${NC}"
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    if [ "$PY_MAJOR" -lt 3 ] || ([ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]); then
        echo -e "${RED}HATA: Python 3.11+ gereklidir. Mevcut sürüm: $PY_VERSION${NC}"
        echo "Homebrew ile kurmak için:"
        echo "  brew install python@3.14"
        exit 1
    fi
    echo -e "${GREEN}✓ Python $PY_VERSION bulundu${NC}"
else
    echo -e "${RED}HATA: Python3 bulunamadı.${NC}"
    echo "Homebrew ile kurmak için:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo "  brew install python@3.14"
    exit 1
fi

# 2. Proje dizini
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
echo -e "${YELLOW}[2/5] Proje dizini: $SCRIPT_DIR${NC}"

# 3. Sanal ortam oluştur
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}[3/5] Sanal ortam oluşturuluyor...${NC}"
    python3 -m venv "$VENV_DIR"
    echo -e "${GREEN}✓ Sanal ortam oluşturuldu${NC}"
else
    echo -e "${GREEN}[3/5] Sanal ortam zaten mevcut${NC}"
fi

# Sanal ortamı aktifleştir
source "$VENV_DIR/bin/activate"

# 4. Bağımlılıkları yükle
echo -e "${YELLOW}[4/5] Bağımlılıklar yükleniyor...${NC}"
pip install --upgrade pip --quiet
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet 2>/dev/null || {
    echo -e "${YELLOW}Bazı bağımlılıklar yüklenemedi, tekrar deneniyor...${NC}"
    pip install -r "$SCRIPT_DIR/requirements.txt"
}
echo -e "${GREEN}✓ Bağımlılıklar yüklendi${NC}"

# 5. Çalıştırma betiği oluştur
LAUNCH_SCRIPT="$SCRIPT_DIR/TurkiyeMCP.command"
echo -e "${YELLOW}[5/5] Başlatma betiği oluşturuluyor...${NC}"
cat > "$LAUNCH_SCRIPT" << 'LAUNCH_EOF'
#!/bin/bash
# Türkiye MCP Server — macOS Başlatma Betiği
# Çift tıklayarak veya Terminal'den çalıştırılabilir.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
    echo "Sanal ortam bulunamadı. Önce install-macos.sh çalıştırın."
    echo "  bash $SCRIPT_DIR/install-macos.sh"
    exit 1
fi

source "$VENV_DIR/bin/activate"

# Port ve host ayarları
PORT="${TURKIYE_MCP_PORT:-8080}"
HOST="127.0.0.1"

echo "🇹🇷 Türkiye MCP Server başlatılıyor..."
echo "   Dashboard: http://$HOST:$PORT"
echo "   MCP SSE:   http://$HOST:$PORT/sse"
echo ""
echo "Durdurmak için Ctrl+C basın."
echo ""

# Sunucuyu başlat
python -m uvicorn app:starlette_app --host "$HOST" --port "$PORT"
LAUNCH_EOF

chmod +x "$LAUNCH_SCRIPT"
echo -e "${GREEN}✓ Başlatma betiği oluşturuldu: TurkiyeMCP.command${NC}"

echo ""
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✓ Kurulum tamamlandı!${NC}"
echo ""
echo "Kullanım:"
echo -e "  ${BLUE}Çift tıkla:${NC} TurkiyeMCP.command"
echo -e "  ${BLUE}Terminal'den:${NC} ./TurkiyeMCP.command"
echo ""
echo "Dashboard: http://127.0.0.1:8080"
echo "MCP SSE:   http://127.0.0.1:8080/sse"
echo ""
echo "Port değiştirmek için:"
echo "  TURKIYE_MCP_PORT=9090 ./TurkiyeMCP.command"
echo -e "${GREEN}============================================${NC}"