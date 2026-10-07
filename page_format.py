"""The generated page's number and text formatting, mirrored from its
JavaScript.

build.py renders both table bodies into the page at build time (#97) by
running the same rules the page's script runs on load. These functions ARE
the script's fmtCost/fmtParams/fmtCtx/show/weightsOf/toFixed/String rules,
one for one; the browser drift test loads the built page with JavaScript
enabled and disabled and holds the two renders equal cell-for-cell, so any
drift between a function here and its JavaScript original fails there.

Every value the page formats is non-negative and finite -- scores, costs,
parameter counts, token prices -- which several of the rules below lean on.
"""

import decimal
import math

EM_DASH = "—"


def js_to_fixed(value, digits):
    """V8's Number.prototype.toFixed for the page's values.

    V8 rounds the number's EXACT binary expansion, and an exact tie picks
    the larger candidate -- 2.25.toFixed(1) is "2.3". Decimal(float) is that
    exact expansion, and ROUND_HALF_UP picks the larger candidate on a tie;
    the two only diverge on negative values, which the page never formats.
    """
    return str(
        decimal.Decimal(float(value)).quantize(
            decimal.Decimal(1).scaleb(-digits), rounding=decimal.ROUND_HALF_UP
        )
    )


def js_number(value):
    """JavaScript String(number) for a payload number.

    An integral value prints without a decimal point ("$"+4 is "$4", never
    "$4.0"), and everything else prints its shortest round-tripping form --
    repr() since Python 3.1, the same shortest-form algorithm V8 uses.
    Python switches to exponent notation at 1e-4 where V8 holds out until
    1e-6, so an e-notation repr is written back out in full; a value that
    small cannot reach the page's prices and speeds.

    Parity with V8 is contractual for 1e-6 <= |v| < 1e21 -- the range the
    page's prices, speeds and parameter counts can reach -- and the
    spellings outside it diverge on purpose; StaticTableRenderTests pins
    both boundaries, so changing this contract is a deliberate diff.
    """
    if value == int(value) and abs(value) < 1e21:
        return str(int(value))
    text = repr(float(value))
    if "e" in text or "E" in text:
        text = format(decimal.Decimal(text), "f")
    return text


def math_round(value):
    """Math.round: floor(value + 0.5) for the non-negative values here."""
    return math.floor(value + 0.5)


def show_text(value):
    """The page's show(): a missing value is the em dash, never blank."""
    # Treat None, empty string, or NaN as missing values.
    if value is None or value == "" or (isinstance(value, float) and math.isnan(value)):
        return EM_DASH
    return str(value)