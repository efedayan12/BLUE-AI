"""PNG logoyu çoklu-boyutlu ICO dosyasına çevir — düzeltilmiş versiyon."""
from PIL import Image
import sys
import os

def png_to_ico(png_path: str, ico_path: str):
    img = Image.open(png_path).convert("RGBA")
    
    # Windows'un beklediği standart boyutlar
    sizes = [16, 24, 32, 48, 64, 128, 256]
    
    # Her boyut için yüksek kaliteli resize
    icons = []
    for s in sizes:
        resized = img.resize((s, s), Image.Resampling.LANCZOS)
        icons.append(resized)
    
    # ICO olarak kaydet — Pillow'un doğru çalışan yöntemi
    img.save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in sizes]
    )
    
    file_size = os.path.getsize(ico_path)
    print(f"[OK] ICO olusturuldu: {ico_path} ({file_size:,} bytes)")
    print(f"     Boyutlar: {', '.join(f'{s}x{s}' for s in sizes)}")

if __name__ == "__main__":
    png_path = sys.argv[1]
    ico_path = sys.argv[2]
    png_to_ico(png_path, ico_path)
