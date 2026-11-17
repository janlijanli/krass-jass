"""Pull the figure out of a letele/playing-cards court card (CC0-1.0).

The card is a 240 x 336 box. The figure is drawn as numbered symbols -- HK1, HK2, ... one per
colour -- each placed twice in a 164.8 x 260.8 box centred on the card, the second turned 180
degrees. Everything else on the card (border, rank glyph, corner suit marks) is ours to draw,
so only the numbered layers and their placements come across.
"""
import re, sys, pathlib

BOX = 'width="164.8" height="260.8" x="-82.4" y="-130.4"'

def symbol(src: str, name: str) -> str:
    k = src.find(f'<symbol id="{name}"')
    if k == -1:
        return ""
    return src[k:src.index("</symbol>", k) + len("</symbol>")]

def figure(path: pathlib.Path) -> str:
    src = path.read_text()
    code = path.stem
    body = src[src.rindex("</defs>"):]
    layers = []
    for href in re.findall(r'xlink:href="#(\w+)"', body):
        if re.fullmatch(rf"{code}\d+", href) and href not in layers:
            layers.append(href)
    if not layers:
        raise SystemExit(f"{path}: no figure layers found")
    defs, seen = "", set()
    queue = list(layers)
    while queue:
        name = queue.pop(0)
        if name in seen:
            continue
        seen.add(name)
        chunk = symbol(src, name)
        defs += chunk
        queue += re.findall(r'xlink:href="#(\w+)"', chunk)
    uses = "".join(
        f'<use {BOX} xlink:href="#{n}"/><use transform="rotate(180)" {BOX} xlink:href="#{n}"/>'
        for n in layers
    )
    return f"<defs>{defs}</defs>{uses}"

if __name__ == "__main__":
    src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
    out.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        'viewBox="-82.4 -130.4 164.8 260.8" width="618" height="978">' + figure(src) + "</svg>")
    print(out.name, out.stat().st_size, "bytes")

# Used by ios/CARD-ART.md to build ios/KrassJass/Resources/Assets.xcassets/Court.
