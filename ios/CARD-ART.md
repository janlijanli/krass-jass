# Where the court figures come from

The twelve court figures in `KrassJass/Resources/Assets.xcassets/Court` are **not ours**. They
are taken from [letele/playing-cards](https://github.com/letele/playing-cards), which is
released under **CC0 1.0 Universal** — a public-domain dedication, so there is no attribution
requirement and nothing to comply with. This file exists because knowing where art came from is
worth more than the licence demands.

Everything else on a card is still drawn in code (`UI/CardArt.swift`, and `web/static/cards.js`
on the web): the suits, the pips, the corner indices, the ace. Only the figure on the K, D and B
is borrowed.

## How the files were made

`scripts/court_figure.py` pulls the figure out of a source card. Each of their cards is a
240 x 336 box in which the figure is drawn as numbered symbols — `HK1`, `HK2`, … one per colour
— each placed twice in a 164.8 x 260.8 box centred on the card, the second turned 180 degrees.
The script lifts those layers and their placements and leaves the rest behind: their border,
their rank glyph and their corner suit marks, because ours are drawn in code and ours say
K, D and B rather than K, Q, J.

```bash
# for each of C/D/H/S x J/Q/K, from their assets/ directory
python3 scripts/court_figure.py <their>/H-K.svg fig/HK.svg

# an SVG is not something iOS can draw, so each one becomes a vector PDF
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless --disable-gpu \
  --no-pdf-header-footer --print-to-pdf=HK.pdf file://.../HK.html
```

The PDFs go into the asset catalog with `preserves-vector-representation`, so they stay sharp at
any size. All twelve come to about 430 KB.

## What this costs

The web build still draws its own court figures, so **iOS and the web no longer show the same
deck**. That breaks the rule the rest of the card art follows. Closing it means either putting
the same SVG figures into `web/static/cards.js` — they are SVG already, so the browser can take
them directly — or going back to the drawn ones on both sides.
