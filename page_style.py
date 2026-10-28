"""The frontier page's stylesheet, spliced verbatim into build.py's TEMPLATE."""

STYLE = r"""  .viz-root, body {
    color-scheme: light;--surface-1:#fcfcfb; --plane:#f9f9f7;
    /* --muted and --accent are darkened one step from their original values
       (#898781, #2a78d6): at those values the table headers measured 3.50:1
       and the frontier tag 4.30:1, under the 4.5:1 WCAG AA floor. The dark
       theme keeps the originals and passes there. */
    --text-primary:#0b0b0b; --text-secondary:#52514e; --muted:#706e67;--grid:#e1e0d9; --axis:#c3c2b7; --border:rgba(11,11,11,0.10);--series-prop:#2a78d6; --series-open:#eb6834; --dim:#a9a7a0;--accent:#2468c0;
    /* Issue #208's dispute red. A status color from the dataviz skill's
       fixed status palette (critical #d03b3b) -- never a series hue, and
       the same hex in both modes: it clears the 3:1 mark floor in both
       modes (4.68:1 light, 3.62:1 dark). Text needs 4.5:1, which dark
       misses, so --dispute-text steps lighter there (#e05e5e, 4.92:1) --
       the palette's success-text move. Both stepped with the skill
       validator's contrast(), not eyeballed. */
    --dispute:#d03b3b;--dispute-text:#d03b3b;
    /* Dedicated token for the dashed frontier line: the line used to borrow
       --muted, which now also fills every superseded point on every chart.
       It keeps the original gray -- --muted itself was darkened to 4.5:1 for
       AA text contrast, which is exactly the retuning this token exists to
       absorb without silently restyling the line. */
    --frontier-line:#898781;--sans:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;--mono:ui-monospace,'SF Mono',Menlo,Monaco,monospace;--radius:12px;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root,
    :root:where(:not([data-theme="light"])) body {
      color-scheme: dark;
      --surface-1:#1a1a19; --plane:#0d0d0d;
      --text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;
      --grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);
      --series-prop:#3987e5; --series-open:#d95926; --dim:#6f6d67;
      --accent:#3987e5; --dispute-text:#e05e5e;
    }
  }
  :root[data-theme="dark"] .viz-root, :root[data-theme="dark"] body {
    color-scheme: dark;--surface-1:#1a1a19; --plane:#0d0d0d;--text-primary:#ffffff; --text-secondary:#c3c2b7; --muted:#898781;--grid:#2c2c2a; --axis:#383835; --border:rgba(255,255,255,0.10);--series-prop:#3987e5; --series-open:#d95926; --dim:#6f6d67;--accent:#3987e5; --dispute-text:#e05e5e;
  }
  *{margin:0;padding:0;box-sizing:border-box}
  body{font-family:var(--sans);background:var(--plane);color:var(--text-secondary);line-height:1.58;padding:44px 24px 100px;-webkit-font-smoothing:antialiased}
  /* No width cap: the chart and tables use the whole monitor. Prose blocks keep
     their own max-width below, because a 3000px-wide paragraph is unreadable. */
  .page{margin:0 auto;max-width:none}
  .eyebrow{font-family:var(--mono);font-size:11.5px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:10px}
  h1{font-size:34px;line-height:1.15;color:var(--text-primary);font-weight:600;letter-spacing:-.015em;margin-bottom:12px}
  .lede{font-size:15.5px;max-width:860px;margin-bottom:26px}
  a{color:var(--accent)}

  .method{background:var(--surface-1);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:16px}
  .method .label{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:10px}
  .mgrid{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;font-size:13.5px}
  @media (max-width:900px){.mgrid{grid-template-columns:repeat(2,1fr)}}
  .mgrid .k{font-family:var(--mono);font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:2px}
  .mgrid .v{color:var(--text-primary);font-weight:600}

  .callout{background:var(--surface-1);border:1px solid var(--border);border-left:3px solid var(--accent);border-radius:var(--radius);padding:13px 18px;margin-bottom:30px;font-size:13.5px;max-width:980px}
  .callout b{color:var(--text-primary)}

  .filters{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
  .chip{font-family:var(--mono);font-size:12px;padding:6px 13px;border-radius:999px;border:1px solid var(--border);background:var(--surface-1);color:var(--text-secondary);cursor:pointer;user-select:none;display:inline-flex;align-items:center;gap:7px}
  /* .chip sets display:inline-flex, and an author rule beats the UA sheet's
     [hidden]{display:none} -- so without this the pin chips render even when
     the hidden attribute is set. */
  .chip[hidden]{display:none}
  .chip:hover{border-color:var(--accent)}
  .chip[aria-pressed="true"]{border-color:var(--accent);color:var(--text-primary);box-shadow:0 0 0 1px var(--accent) inset}
  .chip .dot{width:9px;height:9px;border-radius:50%;display:inline-block}
  .chip .dot.prop{background:var(--series-prop)}
  .chip .dot.open{background:var(--series-open)}
  /* Hollow, matching how these points draw: an absent value, not a third category. */
  .chip .dot.unk{background:none;border:2px solid var(--series-prop);box-sizing:border-box}
  select,input[type=search]{font-family:var(--mono);font-size:12px;padding:6px 11px;border-radius:999px;border:1px solid var(--border);background:var(--surface-1);color:var(--text-primary)}
  .count{font-family:var(--mono);font-size:12px;color:var(--muted);margin-left:auto}

  .card{background:var(--surface-1);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:34px}
  .cap{font-family:var(--mono);font-size:10.5px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px}
  /* explicit: the tooltip is allowed to hang outside the plot and the card */
  .plotwrap{position:relative;overflow:visible}
  .card{overflow:visible}
  svg{display:block;width:100%;height:auto}
  svg text{font-family:var(--mono);font-size:10.5px;fill:var(--muted)}
  /* Boxed labels: the filled box hides the gridlines behind the lettering (so
     no halo is needed), and the leader line ties the text to its own dot. */
  svg text.lbl{font-size:10px;fill:var(--text-secondary)}
  svg rect.lblbox{fill:var(--surface-1);stroke:var(--border);stroke-width:1}
  svg line.lead{stroke:var(--muted);stroke-width:1}
  .pt{cursor:pointer}
  .pt.fade{opacity:.18}
  .pt:focus{outline:none;stroke:var(--accent);stroke-width:4}
  /* a pinned point keeps a dark ring so you can see what you have stuck down */
  .pt.pinned{stroke:var(--text-primary);stroke-width:2}
  svg rect.lblbox.pinned{stroke:var(--accent)}
  th[data-k]:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}

  .legend{display:flex;gap:18px;flex-wrap:wrap;font-size:12.5px;margin:14px 0 2px;font-family:var(--mono);color:var(--text-secondary)}
  .legend .item{display:inline-flex;align-items:center;gap:7px}
  .legend .swatch{width:11px;height:11px;border-radius:50%;display:inline-block}
  .legend .swatch.hollow{background:none !important;border:2px solid var(--series-prop);box-sizing:border-box}
  .legend .line{width:20px;height:0;border-top:2px dashed var(--frontier-line);display:inline-block}

  .tip{position:absolute;pointer-events:none;opacity:0;background:var(--surface-1);border:1px solid var(--border);border-radius:9px;padding:9px 12px;font-size:12.5px;min-width:190px;max-width:280px;box-shadow:0 6px 22px rgba(0,0,0,.18);z-index:50}
  .tip.on{opacity:1}
  /* The fades are a nicety, not information: under prefers-reduced-motion
     the tooltip and the copy toast must appear and vanish instantly rather
     than animate. */
  @media (prefers-reduced-motion: no-preference) {
    .tip{transition:opacity 120ms ease}
    .toast{transition:opacity .2s}
  }
  .tip .tname{color:var(--text-primary);font-weight:600;font-size:13px;margin-bottom:5px}
  .tip .trow{display:flex;justify-content:space-between;gap:14px;font-family:var(--mono);font-size:11.5px}
  .tip .trow .tv{color:var(--text-primary);font-weight:600}
  .tip .tkey{display:inline-block;width:14px;height:2px;vertical-align:middle;margin-right:6px}

  table{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
  th,td{text-align:left;padding:9px 12px;border-bottom:1px solid var(--border)}
  th{font-family:var(--mono);font-size:10.5px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);cursor:pointer;user-select:none;white-space:nowrap;position:sticky;top:0;background:var(--surface-1);z-index:2}
  th:hover{color:var(--text-primary)}
  th .ar{opacity:.45}
  td.n{font-family:var(--mono);text-align:right;font-variant-numeric:tabular-nums;color:var(--text-primary)}
  td.name{color:var(--text-primary);font-weight:600}
  tbody tr:hover{background:var(--plane)}
  .tag{font-family:var(--mono);font-size:10px;padding:1px 7px;border-radius:999px;border:1px solid var(--border);color:var(--text-secondary);white-space:nowrap}
  .tag.f{border-color:var(--accent);color:var(--accent)}
  /* Issue #208: disputed cells and tooltip values render red -- the
     --dispute-text token, 4.5:1 in both modes (see the token block above). */
  td.n.dispute{color:var(--dispute-text)}
  .tip .trow .tv.dispute{color:var(--dispute-text)}
  /* The footer legend's dispute swatch: the mark red, ringed by the
     surface so it reads on both themes. */
  .dswatch{display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--dispute);border:2px solid var(--surface-1);box-sizing:border-box}
  .scroll{max-height:560px;overflow:auto;border:1px solid var(--border);border-radius:var(--radius)}
  /* An empty filtered slice says so inside the table region instead of
     leaving a silent zero-row body; aria-live announces the change. */
  .empty-state{padding:28px 16px;font-size:13.5px;color:var(--text-secondary)}
  .empty-state[hidden]{display:none}

  h2{font-size:22px;color:var(--text-primary);font-weight:600;margin-bottom:6px;letter-spacing:-.01em}
  .sub{font-size:14px;margin-bottom:16px;max-width:880px}
  .toc{display:flex;gap:16px;flex-wrap:wrap;font-family:var(--mono);font-size:12px;margin-bottom:30px}
  button.action{font-family:var(--mono);font-size:12px;padding:8px 15px;background:var(--surface-1);color:var(--accent);border:1px solid var(--accent);border-radius:8px;cursor:pointer}
  button.action:hover{background:var(--plane)}
  .toast{font-family:var(--mono);font-size:11.5px;color:var(--muted);margin-left:10px;opacity:0}
  .toast.show{opacity:1}
  .foot{color:var(--muted);font-size:12.5px;margin-top:56px;padding-top:20px;border-top:1px solid var(--border)}
  /* The global reset removes paragraph margins, so the footer's stacked
     lines would butt together without re-spacing them here. */
  .foot p+p{margin-top:8px}
"""
