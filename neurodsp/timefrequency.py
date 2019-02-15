"""Tools for estimating properties of a neural oscillation over time."""

import math

import numpy as np
from scipy import signal

import neurodsp
from neurodsp.filt import filter_signal

###################################################################################################
###################################################################################################

def phase_by_time(sig, fs, f_range, filter_kwargs=None, hilbert_increase_n=False,
                  remove_edge_artifacts=True, verbose=True):
    """Calculate the phase time series of a neural oscillation.

    Parameters
    ----------
    sig : 1d array
        Time series.
    fs : float
        Sampling rate, in Hz.
    f_range : tuple of float
        Frequency range, in Hz, as (low, high).
    filter_kwargs : dict, optional
        Keyword parameters to pass to `neurodsp.filt.filter_signal()`.
    hilbert_increase_n : bool, optional, default: False
        If True, zeropad the signal to length the next power of 2 when doing the hilbert transform.
        This is because scipy.signal.hilbert can be very slow for some lengths of x.
    remove_edge_artifacts : bool, optional, default: True
        If True, replace the samples that are within half a kernel's length to
        the signal edge with np.nan.
    verbose : bool, optional, default:True
        If True, print filter transition band and any other prints.

    Returns
    -------
    pha : 1d array
        Time series of phase.
    """

    # Set default filtering parameters
    if filter_kwargs is None:
        filter_kwargs = {}

    pass_type = _get_filt_passtype(f_range)

    # Filter signal
    sig_filt, kernel = filter_signal(sig, fs, pass_type, fc=f_range,
                                     remove_edge_artifacts=False,
                                     return_kernel=True,
                                     verbose=verbose, **filter_kwargs)

    # Compute phase time series
    pha = np.angle(_hilbert_ignore_nan(sig_filt, hilbert_increase_n=hilbert_increase_n))

    # Remove edge artifacts
    if remove_edge_artifacts:
        N_rmv = int(np.ceil(len(kernel) / 2))
        pha[:N_rmv] = np.nan
        pha[-N_rmv:] = np.nan

    return pha


def amp_by_time(sig, fs, f_range, filter_kwargs=None, hilbert_increase_n=False,
                remove_edge_artifacts=True, verbose=True):
    """Calculate the amplitude time series.

    Parameters
    ----------
    sig : 1d array
        Time series.
    fs : float
        Sampling rate, in Hz.
    f_range : tuple of float
        The frequency filtering range, in Hz, as (low, high).
    filter_kwargs : dict, optional
        Keyword parameters to pass to `neurodsp.filt.filter_signal()`.
    hilbert_increase_n : bool, optional, default: False
        If True, zeropad the signal to length the next power of 2 when doing the hilbert transform.
        This is because scipy.signal.hilbert can be very slow for some lengths of sig.
    remove_edge_artifacts : bool, optional, default: True
        If True, replace the samples that are within half a kernel's length to
        the signal edge with np.nan.
    verbose : bool, optional, default: True
        If True, print filter transition band and any other prints.

    Returns
    -------
    amp : 1d array
        Time series of amplitude.
    """

    # Set default filtering parameters
    if filter_kwargs is None:
        filter_kwargs = {}

    pass_type = _get_filt_passtype(f_range)

    # Filter signal
    sig_filt, kernel = filter_signal(sig, fs, pass_type, fc=f_range,
                                     remove_edge_artifacts=False,
                                     return_kernel=True,
                                     verbose=verbose, **filter_kwargs)

    # Compute amplitude time series
    amp = np.abs(_hilbert_ignore_nan(sig_filt, hilbert_increase_n=hilbert_increase_n))

    # Remove edge artifacts
    if remove_edge_artifacts:
        N_rmv = int(np.ceil(len(kernel) / 2))
        amp[:N_rmv] = np.nan
        amp[-N_rmv:] = np.nan

    return amp


def freq_by_time(sig, fs, f_range, filter_kwargs=None, hilbert_increase_n=False,
                 remove_edge_artifacts=True, verbose=True):
    """Estimate the instantaneous frequency at each sample.

    Parameters
    ----------
    sig : 1d array
        Voltage time series.
    fs : float
        Sampling rate, in Hz.
    f_range : tuple of float
        Frequency range for filtering, in Hz, as (low, high).
    filter_kwargs : dict, optional
        Keyword parameters to pass to `neurodsp.filt.filter_signal()`.
    hilbert_increase_n : bool, optional, default: False
        If True, zeropad the signal to length the next power of 2 when doing the hilbert transform.
        This is because scipy.signal.hilbert can be very slow for some lengths of sig.
    remove_edge_artifacts : bool, optional, default: True
        If True, replace the samples that are within half a kernel's length to
        the signal edge with np.nan.
    verbose : bool, optional, default: True
        If True, print filter transition band and any other prints.

    Returns
    -------
    i_f : float
        Estimated instantaneous frequency for each sample in 'sig'.

    Notes
    -----
    This function assumes monotonic phase, so a phase slip will be processed as a very high frequency.
    """

    pha = phase_by_time(sig, fs, f_range,
                        filter_kwargs=filter_kwargs,
                        hilbert_increase_n=hilbert_increase_n,
                        remove_edge_artifacts=remove_edge_artifacts,
                        verbose=verbose)

    phadiff = np.diff(pha)
    phadiff[phadiff < 0] = phadiff[phadiff < 0] + 2 * np.pi

    i_f = fs * phadiff / (2 * np.pi)
    i_f = np.insert(i_f, 0, np.nan)

    return i_f


def _hilbert_ignore_nan(sig, hilbert_increase_n=False):
    """Compute the hilbert transform, ignoring the boundaries of that are filled with NaN."""

    # Extract the signal that is not nan
    first_nonan = np.where(~np.isnan(sig))[0][0]
    last_nonan = np.where(~np.isnan(sig))[0][-1] + 1
    sig_nonan = sig[first_nonan:last_nonan]

    # Compute hilbert transform of signal without nans
    if hilbert_increase_n:
        sig_len = len(sig_nonan)
        n_components = 2**(int(math.log(sig_len, 2)) + 1)
        sig_hilb_nonan = signal.hilbert(sig_nonan, n_components)[:sig_len]
    else:
        sig_hilb_nonan = signal.hilbert(sig_nonan)

    # Fill in output hilbert with nans on edges
    sig_hilb = np.ones(len(sig), dtype=complex) * np.nan
    sig_hilb[first_nonan:last_nonan] = sig_hilb_nonan

    return sig_hilb


def _get_filt_passtype(f_range):
    """Given frequency range of filter, check for Nones to return
    appropriate filter pass_type to filt.filter_signal.
    """

    if f_range[0] is None:
        pass_type = 'lowpass'
    elif f_range[1] is None:
        pass_type = 'highpass'
    else:
        if f_range[0] >= f_range[1]:
            raise ValueError('Second cutoff frequency must be greater than first.')
        else:
            pass_type = 'bandpass'

    return pass_type
