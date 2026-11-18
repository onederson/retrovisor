"""Gera os icones do app (web/icone-192.png, icone-512.png e icone.ico) - preto OLED com o botao power verde.

Rodar com um Python que tenha Pillow: python scripts/gerar_icones.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

WEB = Path(__file__).resolve().parent.parent / "web"
VERDE = (0, 230, 118)
VERDE_ESCURO = (11, 61, 31)


def desenhar(lado: int) -> Image.Image:
    s = 4  # desenha 4x maior e reduz: bordas suaves
    L = lado * s
    img = Image.new("RGB", (L, L), (0, 0, 0))
    d = ImageDraw.Draw(img)
    # X da porta, discreto, de canto a canto
    d.line([(0, 0), (L, L)], fill=VERDE_ESCURO, width=int(L * 0.018))
    d.line([(L, 0), (0, L)], fill=VERDE_ESCURO, width=int(L * 0.018))
    # aro do botao (dentro da zona segura de icone "maskable": 80% central)
    c, r = L / 2, L * 0.30
    d.ellipse([c - r, c - r, c + r, c + r], fill=(0, 0, 0), outline=VERDE, width=int(L * 0.035))
    # simbolo power: arco aberto em cima + traco vertical
    ri, w = L * 0.16, int(L * 0.045)
    d.arc([c - ri, c - ri, c + ri, c + ri], start=-60, end=240, fill=VERDE, width=w)
    d.line([(c, c - ri * 1.25), (c, c - ri * 0.15)], fill=VERDE, width=w)
    return img.resize((lado, lado), Image.LANCZOS)


if __name__ == "__main__":
    for lado in (192, 512):
        desenhar(lado).save(WEB / f"icone-{lado}.png")
    desenhar(256).save(WEB / "icone.ico", sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("icones gerados em", WEB)
