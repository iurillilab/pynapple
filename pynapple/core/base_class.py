"""
    Abstract class for `core` time series.

"""

import abc
from numbers import Number

import numpy as np

from ._core_functions import _count, _restrict, _value_from
from .interval_set import IntervalSet
from .time_index import TsIndex
from .utils import convert_to_numpy_array


class Base(abc.ABC):
    """
    Abstract base class for time series and timestamps objects.
    Implement most of the shared functions across concrete classes `Ts`, `Tsd`, `TsdFrame`, `TsdTensor`
    """

    _initialized = False

    def __init__(self, t, time_units="s", time_support=None):
        if isinstance(t, TsIndex):
            self.index = t
        else:
            self.index = TsIndex(convert_to_numpy_array(t, "t"), time_units)

        if time_support is not None:
            assert isinstance(
                time_support, IntervalSet
            ), "time_support should be an IntervalSet"

        # Restrict should occur in the inherited class
        if len(self.index):
            if isinstance(time_support, IntervalSet):
                self.time_support = time_support
            else:
                self.time_support = IntervalSet(start=self.index[0], end=self.index[-1])

            self.rate = self.index.shape[0] / np.sum(
                self.time_support.values[:, 1] - self.time_support.values[:, 0]
            )
        else:
            self.rate = np.NaN
            self.time_support = IntervalSet(start=[], end=[])

    @property
    def t(self):
        return self.index.values

    @property
    def start(self):
        return self.start_time()

    @property
    def end(self):
        return self.end_time()

    @property
    def shape(self):
        return self.index.shape

    def __repr__(self):
        return str(self.__class__)

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self.index)

    def __setattr__(self, name, value):
        """Object is immutable"""
        if self._initialized:
            raise RuntimeError(
                "Changing directly attributes is not permitted for {}.".format(
                    self.nap_class
                )
            )
        else:
            object.__setattr__(self, name, value)

    @abc.abstractmethod
    def __getitem__(self, key, *args, **kwargs):
        """getter for time series"""
        pass

    def __setitem__(self, key, value):
        pass

    def times(self, units="s"):
        """
        The time index of the object, returned as np.double in the desired time units.

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.ndarray
            the time indexes
        """
        return self.index.in_units(units)

    def start_time(self, units="s"):
        """
        The first time index in the time series object

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.float64
            _
        """
        if len(self.index):
            return self.times(units=units)[0]
        else:
            return None

    def end_time(self, units="s"):
        """
        The last time index in the time series object

        Parameters
        ----------
        units : str, optional
            ('us', 'ms', 's' [default])

        Returns
        -------
        out: numpy.float64
            _
        """
        if len(self.index):
            return self.times(units=units)[-1]
        else:
            return None

    def value_from(self, data, ep=None):
        """
        Replace the value with the closest value from Tsd/TsdFrame/TsdTensor argument

        Parameters
        ----------
        data : Tsd, TsdFrame or TsdTensor
            The object holding the values to replace.
        ep : IntervalSet (optional)
            The IntervalSet object to restrict the operation.
            If None, the time support of the tsd input object is used.

        Returns
        -------
        out : Tsd, TsdFrame or TsdTensor
            Object with the new values

        Examples
        --------
        In this example, the ts object will receive the closest values in time from tsd.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100))) # random times
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> tsd = nap.Tsd(t=np.arange(0,1000), d=np.random.rand(1000), time_units='s')
        >>> ep = nap.IntervalSet(start = 0, end = 500, time_units = 's')

        The variable ts is a timestamp object.
        The tsd object containing the values, for example the tracking data, and the epoch to restrict the operation.

        >>> newts = ts.value_from(tsd, ep)

        newts is the same size as ts restrict to ep.

        >>> print(len(ts.restrict(ep)), len(newts))
            52 52
        """
        if ep is None:
            ep = data.time_support
        time_array = self.index.values
        time_target_array = data.index.values
        data_target_array = data.values
        starts = ep.start
        ends = ep.end

        t, d = _value_from(
            time_array, time_target_array, data_target_array, starts, ends
        )

        time_support = IntervalSet(start=starts, end=ends)

        kwargs = {}
        if hasattr(data, "columns"):
            kwargs["columns"] = data.columns

        return t, d, time_support, kwargs

    def count(self, *args, **kwargs):
        """
        Count occurences of events within bin_size or within a set of bins defined as an IntervalSet.
        You can call this function in multiple ways :

        1. *tsd.count(bin_size=1, time_units = 'ms')*
        -> Count occurence of events within a 1 ms bin defined on the time support of the object.

        2. *tsd.count(1, ep=my_epochs)*
        -> Count occurent of events within a 1 second bin defined on the IntervalSet my_epochs.

        3. *tsd.count(ep=my_bins)*
        -> Count occurent of events within each epoch of the intervalSet object my_bins

        4. *tsd.count()*
        -> Count occurent of events within each epoch of the time support.

        bin_size should be seconds unless specified.
        If bin_size is used and no epochs is passed, the data will be binned based on the time support of the object.

        Parameters
        ----------
        bin_size : None or float, optional
            The bin size (default is second)
        ep : None or IntervalSet, optional
            IntervalSet to restrict the operation
        time_units : str, optional
            Time units of bin size ('us', 'ms', 's' [default])

        Returns
        -------
        out: Tsd
            A Tsd object indexed by the center of the bins.

        Examples
        --------
        This example shows how to count events within bins of 0.1 second.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100)))
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> bincount = ts.count(0.1)

        An epoch can be specified:

        >>> ep = nap.IntervalSet(start = 100, end = 800, time_units = 's')
        >>> bincount = ts.count(0.1, ep=ep)

        And bincount automatically inherit ep as time support:

        >>> bincount.time_support
            start    end
        0  100.0  800.0
        """
        bin_size = None
        if "bin_size" in kwargs:
            bin_size = kwargs["bin_size"]
            if isinstance(bin_size, int):
                bin_size = float(bin_size)
            if not isinstance(bin_size, float):
                raise ValueError("bin_size argument should be float.")
        else:
            for a in args:
                if isinstance(a, (float, int)):
                    bin_size = float(a)

        time_units = "s"
        if "time_units" in kwargs:
            time_units = kwargs["time_units"]
            if not isinstance(time_units, str):
                raise ValueError("time_units argument should be 's', 'ms' or 'us'.")
        else:
            for a in args:
                if isinstance(a, str) and a in ["s", "ms", "us"]:
                    time_units = a

        ep = self.time_support
        if "ep" in kwargs:
            ep = kwargs["ep"]
            if not isinstance(ep, IntervalSet):
                raise ValueError("ep argument should be IntervalSet")
        else:
            for a in args:
                if isinstance(a, IntervalSet):
                    ep = a

        starts = ep.start
        ends = ep.end

        if isinstance(bin_size, (float, int)):
            bin_size = TsIndex.format_timestamps(np.array([bin_size]), time_units)[0]

        time_array = self.index.values

        t, d = _count(time_array, starts, ends, bin_size)

        return t, d, ep

    def restrict(self, iset):
        """
        Restricts a time series object to a set of time intervals delimited by an IntervalSet object

        Parameters
        ----------
        iset : IntervalSet
            the IntervalSet object

        Returns
        -------
        Ts, Tsd, TsdFrame or TsdTensor
            Tsd object restricted to ep

        Examples
        --------
        The Ts object is restrict to the intervals defined by ep.

        >>> import pynapple as nap
        >>> import numpy as np
        >>> t = np.unique(np.sort(np.random.randint(0, 1000, 100)))
        >>> ts = nap.Ts(t=t, time_units='s')
        >>> ep = nap.IntervalSet(start=0, end=500, time_units='s')
        >>> newts = ts.restrict(ep)

        The time support of newts automatically inherit the epochs defined by ep.

        >>> newts.time_support
            start    end
        0    0.0  500.0

        """

        assert isinstance(iset, IntervalSet), "Argument should be IntervalSet"

        time_array = self.index.values
        starts = iset.start
        ends = iset.end

        idx = _restrict(time_array, starts, ends)

        kwargs = {}
        if hasattr(self, "columns"):
            kwargs["columns"] = self.columns

        if hasattr(self, "values"):
            data_array = self.values
            return self.__class__(
                t=time_array[idx], d=data_array[idx], time_support=iset, **kwargs
            )
        else:
            return self.__class__(t=time_array[idx], time_support=iset)

    def copy(self):
        """Copy the data, index and time support"""
        return self.__class__(t=self.index.copy(), time_support=self.time_support)

    def find_support(self, min_gap, time_units="s"):
        """
        find the smallest (to a min_gap resolution) IntervalSet containing all the times in the Tsd

        Parameters
        ----------
        min_gap : float or int
            minimal interval between timestamps
        time_units : str, optional
            Time units of min gap

        Returns
        -------
        IntervalSet
            Description
        """
        assert isinstance(min_gap, Number), "min_gap should be a float or int"
        min_gap = TsIndex.format_timestamps(np.array([min_gap]), time_units)[0]
        time_array = self.index.values

        starts = [time_array[0]]
        ends = []
        for i in range(len(time_array) - 1):
            if (time_array[i + 1] - time_array[i]) > min_gap:
                ends.append(time_array[i] + 1e-6)
                starts.append(time_array[i + 1])

        ends.append(time_array[-1] + 1e-6)

        return IntervalSet(start=starts, end=ends)

    def get(self, start, end=None, time_units="s"):
        """Slice the time series from `start` to `end` such that all the timestamps satisfy `start<=t<=end`.
        If `end` is None, only the timepoint closest to `start` is returned.

        By default, the time support doesn't change. If you want to change the time support, use the `restrict` function.

        Parameters
        ----------
        start : float or int
            The start (or closest time point if `end` is None)
        end : float or int or None
            The end
        """
        assert isinstance(start, Number), "start should be a float or int"
        time_array = self.index.values

        if end is None:
            start = TsIndex.format_timestamps(np.array([start]), time_units)[0]
            idx = int(np.searchsorted(time_array, start))
            if idx == 0:
                return self[idx]
            elif idx >= self.shape[0]:
                return self[-1]
            else:
                if start - time_array[idx - 1] < time_array[idx] - start:
                    return self[idx - 1]
                else:
                    return self[idx]
        else:
            assert isinstance(end, Number), "end should be a float or int"
            assert start < end, "Start should not precede end"
            start, end = TsIndex.format_timestamps(np.array([start, end]), time_units)
            idx_start = np.searchsorted(time_array, start)
            idx_end = np.searchsorted(time_array, end, side="right")
            return self[idx_start:idx_end]

    @classmethod
    def _from_npz_reader(cls, file):
        """Load a time series object from a npz file interface.

        Parameters
        ----------
        file : NPZFile object
            opened npz file interface.

        Returns
        -------
        out : Ts or Tsd or TsdFrame or TsdTensor
            The time series object
        """
        kwargs = {
            key: file[key] for key in file.keys() if key not in ["start", "end", "type"]
        }
        iset = IntervalSet(start=file["start"], end=file["end"])
        return cls(time_support=iset, **kwargs)
