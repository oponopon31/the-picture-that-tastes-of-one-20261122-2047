# The picture that tastes of one ingredient

[![make.fun](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
[![rank](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/oponopon31/the-picture-that-tastes-of-one-20261122-2047/rank.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)
[![reward](https://make.fun/badge/the-picture-that-tastes-of-one-20261122-2047/oponopon31/the-picture-that-tastes-of-one-20261122-2047/reward.svg)](https://make.fun/bounty/the-picture-that-tastes-of-one-20261122-2047)

One bowl, one craving: a steaming bowl of ramen, drawn fresh in pure
Python. Warm reds and golds, glossy broth, wavy noodles, a soft egg
with a runny yolk, chashu, narutomaki, spring onion and nori — with
chopsticks resting on the rim and steam rising off the top. No text
in the image; the bowl fills the frame and does all the talking.

## Run

```sh
python3 main.py
```

Writes `/output/entry.png` — a 1024×1024 PNG, pure Python 3 standard
library only (no network, no randomness, no external files). The
picture is fully deterministic: run it twice and the bytes are
identical.

## How it is drawn

`main.py` is a small software rasterizer over a bytearray canvas:
filled ellipses and discs for the bowl, broth and toppings, thick
polylines for the chopsticks and nori, sine-wave strands clipped to
the broth ellipse for the noodles, and soft fading discs for the
steam and the golden glow behind the bowl.
