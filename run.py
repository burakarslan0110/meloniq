"""
Meloniq uygulaması için hızlı başlatıcı.
"""

import sys
from pathlib import Path

# src dizinini yola ekle
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from meloniq.main import main

if __name__ == "__main__":
    main()
