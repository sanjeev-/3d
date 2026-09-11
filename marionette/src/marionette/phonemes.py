"""Text → phonemes → visemes for lip-sync animation.

`text_to_phonemes` uses g2p_en (CMU-dict backed) to produce ARPAbet symbols.
`phonemes_to_visemes` maps those to the 12-shape Preston Blair viseme set,
which lines up with the mouth shape-keys on most humanoid rigs.
"""

from enum import Enum
from typing import List


class Viseme(str, Enum):
    REST = "REST"   # silence / closed mouth
    AI   = "AI"     # wide open  (a, i)
    E    = "E"      # mid open   (e)
    O    = "O"      # rounded    (o)
    U    = "U"      # small round(u, oo)
    MBP  = "MBP"    # lips press (m, b, p)
    FV   = "FV"     # teeth-lip  (f, v)
    L    = "L"      # tongue up  (l)
    WQ   = "WQ"     # very round (w, r)
    S    = "S"      # teeth show (default consonants)
    TH   = "TH"     # tongue out (th)
    ETSH = "etsh"   # narrow open(ch, sh, j)


# ARPAbet phoneme → Preston Blair viseme.
PHONEME_TO_VISEME = {
    "AA": Viseme.AI, "AE": Viseme.AI, "AH": Viseme.AI, "AY": Viseme.AI, "EY": Viseme.AI,
    "EH": Viseme.E,  "IH": Viseme.E,  "IY": Viseme.E,  "ER": Viseme.E,  "Y":  Viseme.E,
    "AO": Viseme.O,  "OW": Viseme.O,  "OY": Viseme.O,  "AW": Viseme.O,
    "UH": Viseme.U,  "UW": Viseme.U,
    "M":  Viseme.MBP, "B": Viseme.MBP, "P": Viseme.MBP,
    "F":  Viseme.FV,  "V": Viseme.FV,
    "L":  Viseme.L,
    "W":  Viseme.WQ,  "R": Viseme.WQ,
    "TH": Viseme.TH,  "DH": Viseme.TH,
    "CH": Viseme.ETSH, "JH": Viseme.ETSH, "SH": Viseme.ETSH, "ZH": Viseme.ETSH,
    "S":  Viseme.S,   "Z": Viseme.S,  "T": Viseme.S,  "D": Viseme.S,
    "N":  Viseme.S,   "NG": Viseme.S, "K": Viseme.S,  "G": Viseme.S,
    "HH": Viseme.REST,
}


def text_to_phonemes(text: str) -> List[str]:
    """Convert English text to ARPAbet phonemes.

    Punctuation and whitespace tokens are dropped and stress markers
    (trailing 0/1/2) are stripped, so callers get plain phoneme symbols.
    """
    tokens = _g2p()(text)
    return [p for p in (_strip_stress(t) for t in tokens) if p.isalpha()]


def phonemes_to_visemes(phonemes: List[str]) -> List[Viseme]:
    """Map ARPAbet phonemes to Preston Blair visemes. Unknown → REST."""
    return [PHONEME_TO_VISEME.get(p, Viseme.REST) for p in phonemes]


def text_to_visemes(text: str) -> List[Viseme]:
    """Text → visemes in one call."""
    return phonemes_to_visemes(text_to_phonemes(text))


_g2p_instance = None

def _g2p():
    """Lazy singleton — G2p's NLTK init is multi-second."""
    global _g2p_instance
    if _g2p_instance is None:
        try:
            from g2p_en import G2p
        except ImportError as e:
            raise ImportError(
                "g2p_en is required for phoneme conversion. "
                "Install with: pip install 'marionette[phonemes]'"
            ) from e
        import nltk
        nltk.download("averaged_perceptron_tagger_eng", quiet=True)
        _g2p_instance = G2p()
    return _g2p_instance


def _strip_stress(phoneme: str) -> str:
    """Drop trailing stress digit (0/1/2) if present."""
    return phoneme[:-1] if phoneme and phoneme[-1].isdigit() else phoneme
