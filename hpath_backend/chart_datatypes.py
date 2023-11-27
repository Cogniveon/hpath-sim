"""Chart data types for compatibility with https://github.com/lakeesiv/digital-twin"""
from datetime import datetime, timedelta
import typing as ty

import pandas as pd
import pydantic as pyd

ContinuousT = ty.TypeVar(
    'ContinuousT',
    float,
    datetime,
    timedelta
)


class ChartData(pyd.BaseModel):
    """Jsonifiable chart data representation for a single data series."""
    x: list[ContinuousT] | list[str]
    y: list[float]
    ymin: ty.Optional[list[float]]
    ymax: ty.Optional[list[float]]

    @staticmethod
    def from_pandas(
        means: pd.DataFrame | pd.Series,
        mins: pd.DataFrame | pd.Series | None = None,
        maxs: pd.DataFrame | pd.Series | None = None,
    ) -> 'ChartData':
        """Instantiate a ChartData object from pandas :py:class:`~pandas.DataFrame`
        or :py:class:`~pandas.Series` objects. Dataframes are converted to Series by taking
        the first column (index 0)."""

        # TODO: validate that means, mins, and maxs have identical indexes
        y = means.tolist() if isinstance(means, pd.Series) else means.iloc[:, 0].tolist()
        y_min = (
            None if mins is None
            else mins.tolist() if isinstance(mins, pd.Series)
            else mins.iloc[:, 0].tolist()
        )
        y_max = (
            None if maxs is None
            else maxs.tolist() if isinstance(maxs, pd.Series)
            else maxs.iloc[:, 0].tolist()
        )

        return __class__(
            x=means.index,
            y=y,
            ymin=y_min,
            ymax=y_max
        )


class MultiChartData(pyd.BaseModel):
    """Jsonifiable chart data representation for multiple data series.

    **Note**: only line charts are supported currently for this data type,
    unlike for :py:class:`ChartData` which can also represent bar chart data
    with ``string`` x values.
    """
    x: list[ContinuousT]
    y: list[list[float]]
    """List of line series.  Each series is a ``list[float]``."""
    labels: list[str]
    """Legend labels for each line series."""
    ymin: list[list[float]] | None
    ymax: list[list[float]] | None

    @staticmethod
    def from_pandas(
        means: pd.DataFrame,
        mins: pd.DataFrame | None = None,
        maxs: pd.DataFrame | None = None,
    ) -> 'MultiChartData':
        """Instantiate a MultiChartData object from pandas :py:class:`~pandas.DataFrame`
        objects."""

        # TODO: validate that means, mins, and maxs have identical indexes and columns
        return __class__(
            x=means.index.tolist(),
            y=means.T.values.tolist(),
            ymin=None if mins is None else mins.T.values.tolist(),
            ymax=None if maxs is None else maxs.T.values.tolist(),
            labels=means.columns.tolist()
        )
