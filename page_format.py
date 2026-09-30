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
    return str(decimal.Decimal(float(value)).quantize(
        decimal.Decimal(1).scaleb(-digits), rounding=decimal.ROUND_HALF_UP))


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
    return EM_DASH if value is None or value == "" else str(value)


def fmt_cost(value):
    """The page's fmtCost: two decimals at a dollar, three below."""
    if value >= 1:
        return "$" + js_to_fixed(value, 2)
    return "$" + js_to_fixed(value, 3)


def fmt_params(value):
    """The page's fmtParams: the count renders as T/B/M exactly as V8 does,
    with a decimal only where the script prints one."""
    if value is None:
        return EM_DASH
    if value >= 1000:
        return js_to_fixed(value / 1000, 1 if value % 1000 else 0) + "T"
    if value >= 1:
        return js_to_fixed(value, 1 if value < 10 else 0) + "B"
    return str(math_round(value * 1000)) + "M"


def fmt_ctx(value):
    """The page's fmtCtx: M/K compact forms at the same thresholds."""
    if value is None:
        return EM_DASH
    if value >= 1e6:
        return js_to_fixed(value / 1e6, 1 if value % 1e6 else 0) + "M"
    if value >= 1e3:
        return str(math_round(value / 1e3)) + "K"
    return js_number(value)


def weights_text(row):
    """The page's weightsOf(): weights status belongs to the model a row
    measures, and a run on a model the leaderboard does not carry is honest
    about it rather than defaulted."""
    if row["open"] is None:
        return "not published"
    if row["open"]:
        return row["lic"] or "open"
    return "proprietary"
