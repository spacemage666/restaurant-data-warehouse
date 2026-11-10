"""Chart builders (Altair ships with Streamlit, so nothing extra to install)."""
import altair as alt

PALETTE = ["#D9480F", "#2F9E44", "#1971C2", "#9C36B5", "#F08C00", "#0C8599"]
GRID = "#EADFCF"


_TYPES = {"T": "temporal", "O": "ordinal", "N": "nominal", "Q": "quantitative"}


def _x(field, kind, **kw):
    return alt.X(field=field, type=_TYPES[kind], **kw)


def _y(field, kind, **kw):
    return alt.Y(field=field, type=_TYPES[kind], **kw)


def _color(field, **kw):
    return alt.Color(field=field, type="nominal", legend=alt.Legend(title=None, orient="bottom"), **kw)


def _tip(field, kind, **kw):
    return alt.Tooltip(field=field, type=_TYPES[kind], **kw)


def _style(chart, height):
    return (
        chart.properties(height=height, padding={"left": 14, "right": 10, "top": 6, "bottom": 6}, autosize=alt.AutoSizeParams(type="fit", contains="padding"))
        .configure_view(strokeWidth=0)
        .configure_axis(gridColor=GRID, domainColor=GRID, tickColor=GRID, labelColor="#5C4B3A", titleColor="#5C4B3A")
    )


def line(df, x, y, color, x_type="T", height=300, y_title=None, x_title=None):
    """Multi-line chart. x_type: T (dates), O (ordered labels)."""
    tip_x = _tip(x, x_type, format="%d %b %Y") if x_type == "T" else _tip(x, x_type)
    chart = (
        alt.Chart(df)
        .mark_line(strokeWidth=2.5, interpolate="monotone")
        .encode(
            x=_x(x, x_type, title=x_title, axis=alt.Axis(labelAngle=0, **({"format": "%b", "tickCount": "month"} if x_type == "T" else {}))),
            y=_y(y, "Q", title=y_title or y, scale=alt.Scale(zero=True)),
            color=_color(color, scale=alt.Scale(range=PALETTE)),
            tooltip=[tip_x, _tip(color, "N"), _tip(y, "Q", format=",.1f")],
        )
    )
    return _style(chart, height)


def hbar(df, category, value, height=300, value_title=None, fmt=",.1f"):
    """Horizontal bars, biggest on top."""
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusEnd=4, color=PALETTE[0])
        .encode(
            y=_y(category, "N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
            x=_x(value, "Q", title=value_title or value),
            tooltip=[_tip(category, "N"), _tip(value, "Q", format=fmt)],
        )
    )
    return _style(chart, height)


def stacked_months(df, month, value, color, height=300, value_title=None):
    """Monthly stacked bars (two or more colors)."""
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            x=_x(month, "O", title=None, axis=alt.Axis(labelAngle=-45, labelOverlap=False)),
            y=_y(value, "Q", title=value_title or value),
            color=_color(color, scale=alt.Scale(range=[PALETTE[2], PALETTE[0]])),
            tooltip=[_tip(month, "O"), _tip(color, "N"), _tip(value, "Q", format=",.1f")],
        )
    )
    return _style(chart, height)


def heatmap(df, x, y, value, height=300, value_title=None):
    chart = (
        alt.Chart(df)
        .mark_rect(cornerRadius=2)
        .encode(
            x=_x(x, "O", title=None, axis=alt.Axis(labelAngle=-45, labelOverlap=False)),
            y=_y(y, "N", title=None, axis=alt.Axis(labelOverlap=False)),
            color=alt.Color(field=value, type="quantitative", title=value_title or value, scale=alt.Scale(scheme="oranges")),
            tooltip=[_tip(y, "N"), _tip(x, "O"), _tip(value, "Q", format=",.2f")],
        )
    )
    return _style(chart, height)


def hstacked(df, category, value, color, height=220, value_title=None):
    """Horizontal stacked bars (one bar per category, split by color)."""
    chart = (
        alt.Chart(df)
        .mark_bar()
        .encode(
            y=_y(category, "N", title=None, sort=None, axis=alt.Axis(labelLimit=260)),
            x=_x(value, "Q", title=value_title or value, stack="zero"),
            color=_color(color, scale=alt.Scale(range=[PALETTE[0], PALETTE[2]])),
            tooltip=[_tip(category, "N"), _tip(color, "N"), _tip(value, "Q", format=",.1f")],
        )
    )
    return _style(chart, height)
