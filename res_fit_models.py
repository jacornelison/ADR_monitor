# -*- coding: utf-8 -*-
"""
Created on Tue Dec 17 15:37:50 2024

@author: Jcornelison
"""
import numpy as np
from scipy.special import digamma, i0, k0
import scipy.constants as sc
import scipy.interpolate as si
import scraps as scr
import lmfit as lf

def f0_tls(params, temps, powers, data = None, eps = None, **kwargs):
    """A model of frequency shift vs temperature and power, weighted by uncertainties.

    Parameters
    ----------
    params : ``lmfit.Parameters`` object
        Parameters must include ``['Fd', 'df', 'fRef', 'alpha', 'delta0']``.

    temps : ``numpy.Array``
        Array of temperature values to evaluate model at. May be 2D.

    powers : ``numpy.Array``
        Array of power values to evaluate model at. May be 2D.

    data : ``numpy.Array``
        Data values to compare to model. May also be ``None``, in which case
        function returns model.

    eps : ``numpy.Array``
        Uncertianties with which to weight residual. May also be ``None``, in
        which case residual is unwieghted.

    Returns
    -------

    residual : ``numpy.Array``
        The weighted or unweighted vector of residuals if ``data`` is passed.
        Otherwise, it returns the model.

    Note
    ----
    The following constraint must be satisfied::

        all(numpy.shape(x) == numpy.shape(data) for x in [temps, powers, eps])

    It is almost certain that this model does NOT apply to your device as the
    assumptions it makes are highly constraining and ignore several material
    parameters. It is included here more as an example for how to write a model
    than anything else, and it does at least qualitatively describe the behavior
    of most superconducting resonators.

    This model is taken from J. Gao's Caltech dissertation (2008) and the below
    equations are from that work.

    (2.54) gives for MBD (f(T)-f(0))/f(0) = -alpha*0.5*(X(T)-X(0))/X(0)

    (5.71) gives for TLS "" = Fd/pi * (usual TLS expression from Phillips)

    (X(T)-X(0))/X(0) calculated from (2.80), (2.89), and (2.90), using the ``deltaBCS``
    function in this module for returning gap as a function of temperature.

    """
    #Unpack parameter values from params
    Fd = params['Fd'].value
    f0 = params['f0'].value    

    #Set temperature units
    units = kwargs.pop('units', 'mK')
    assert units in ['mK', 'K'], "Units must be 'mK' or 'K'."

    if units == 'mK':
        ts = temps*0.001


    #Pack all these together for convenience
    zeta = sc.h*f0/(2*sc.k*ts)

    
    #TLS contribution
    dfTLS = Fd/sc.pi*(np.real(digamma(0.5+zeta/(1j*sc.pi)))-np.log(zeta/sc.pi))


    #Calculate model from parameters
    model = f0+f0*(dfTLS)


    #Weight the residual if eps is supplied
    if data is not None:
        if eps is not None:
            residual = (model-data)/eps
        else:
            residual = (model-data)

        return residual
    else:
        return model

def f0_tls_mod(params, temps, powers, data = None, eps = None, **kwargs):
    """A model of frequency shift vs temperature and power, weighted by uncertainties. Same as TLS, but has a overall temp offset, DT.

    Parameters
    ----------
    params : ``lmfit.Parameters`` object
        Parameters must include ``['Fd', 'df', 'fRef', 'alpha', 'delta0']``.

    temps : ``numpy.Array``
        Array of temperature values to evaluate model at. May be 2D.

    powers : ``numpy.Array``
        Array of power values to evaluate model at. May be 2D.

    data : ``numpy.Array``
        Data values to compare to model. May also be ``None``, in which case
        function returns model.

    eps : ``numpy.Array``
        Uncertianties with which to weight residual. May also be ``None``, in
        which case residual is unwieghted.

    Returns
    -------

    residual : ``numpy.Array``
        The weighted or unweighted vector of residuals if ``data`` is passed.
        Otherwise, it returns the model.

    Note
    ----
    The following constraint must be satisfied::

        all(numpy.shape(x) == numpy.shape(data) for x in [temps, powers, eps])

    It is almost certain that this model does NOT apply to your device as the
    assumptions it makes are highly constraining and ignore several material
    parameters. It is included here more as an example for how to write a model
    than anything else, and it does at least qualitatively describe the behavior
    of most superconducting resonators.

    This model is taken from J. Gao's Caltech dissertation (2008) and the below
    equations are from that work.

    (2.54) gives for MBD (f(T)-f(0))/f(0) = -alpha*0.5*(X(T)-X(0))/X(0)

    (5.71) gives for TLS "" = Fd/pi * (usual TLS expression from Phillips)

    (X(T)-X(0))/X(0) calculated from (2.80), (2.89), and (2.90), using the ``deltaBCS``
    function in this module for returning gap as a function of temperature.

    """
    #Unpack parameter values from params
    Fd = params['Fd'].value
    f0 = params['f0'].value    
    DT = params['DT'].value
    
    temps = temps+DT
    
    #Set temperature units
    units = kwargs.pop('units', 'mK')
    assert units in ['mK', 'K'], "Units must be 'mK' or 'K'."

    if units == 'mK':
        ts = temps*0.001


    #Pack all these together for convenience
    zeta = sc.h*f0/(2*sc.k*ts)

    
    #TLS contribution
    dfTLS = Fd/sc.pi*(np.real(digamma(0.5+zeta/(1j*sc.pi)))-np.log(zeta/sc.pi))


    #Calculate model from parameters
    model = f0+f0*(dfTLS)


    #Weight the residual if eps is supplied
    if data is not None:
        if eps is not None:
            residual = (model-data)/eps
        else:
            residual = (model-data)

        return residual
    else:
        return model


def f0_tlsAndMBT_mod(params, temps, powers, data = None, eps = None, **kwargs):
    """A model of frequency shift vs temperature and power, weighted by uncertainties.
    Same as TLS, but has a overall temp offset, DT.

    Parameters
    ----------
    params : ``lmfit.Parameters`` object
        Parameters must include ``['Fd', 'df', 'fRef', 'alpha', 'delta0']``.

    temps : ``numpy.Array``
        Array of temperature values to evaluate model at. May be 2D.

    powers : ``numpy.Array``
        Array of power values to evaluate model at. May be 2D.

    data : ``numpy.Array``
        Data values to compare to model. May also be ``None``, in which case
        function returns model.

    eps : ``numpy.Array``
        Uncertianties with which to weight residual. May also be ``None``, in
        which case residual is unwieghted.

    Returns
    -------

    residual : ``numpy.Array``
        The weighted or unweighted vector of residuals if ``data`` is passed.
        Otherwise, it returns the model.

    Note
    ----
    The following constraint must be satisfied::

        all(numpy.shape(x) == numpy.shape(data) for x in [temps, powers, eps])

    It is almost certain that this model does NOT apply to your device as the
    assumptions it makes are highly constraining and ignore several material
    parameters. It is included here more as an example for how to write a model
    than anything else, and it does at least qualitatively describe the behavior
    of most superconducting resonators.

    This model is taken from J. Gao's Caltech dissertation (2008) and the below
    equations are from that work.

    (2.54) gives for MBD (f(T)-f(0))/f(0) = -alpha*0.5*(X(T)-X(0))/X(0)

    (5.71) gives for TLS "" = Fd/pi * (usual TLS expression from Phillips)

    (X(T)-X(0))/X(0) calculated from (2.80), (2.89), and (2.90), using the ``deltaBCS``
    function in this module for returning gap as a function of temperature.

    """
    #Unpack parameter values from params
    Fd = params['Fd'].value
    f0 = params['f0'].value
    alpha = params['alpha'].value
    delta0 = params['delta0'].value*sc.e
    DT = params['DT'].value

    temps = temps+DT

    #Set temperature units
    units = kwargs.pop('units', 'mK')
    assert units in ['mK', 'K'], "Units must be 'mK' or 'K'."

    if units == 'mK':
        ts = temps*0.001

    #Calculate tc from BCS relation
    tc = delta0/(1.76*sc.k)

    #Get the reduced energy gap
    deltaR = deltaBCS(ts/tc)

    #And the energy gap at T
    deltaT = delta0*deltaR

    #Pack all these together for convenience
    zeta = sc.h*f0/(2*sc.k*ts)

    #Assuming thick film local limit
    #Other good options are 1 or 1/3
    gamma = kwargs.pop('gamma', 0.5)

    #TLS contribution
    dfTLS = Fd/sc.pi*(np.real(digamma(0.5+zeta/(1j*sc.pi)))-np.log(zeta/sc.pi))

    #MBD contribution
    dfMBD = alpha*gamma*0.5*(deltaR*(1-
                        2*np.exp(-deltaT/(sc.k*ts))
                        *np.exp(-zeta)
                        *i0(zeta))-1)


    #Calculate model from parameters
    model = f0+f0*(dfTLS + dfMBD)


    #Weight the residual if eps is supplied
    if data is not None:
        if eps is not None:
            residual = (model-data)/eps
        else:
            residual = (model-data)

        return residual
    else:
        return model

@np.vectorize
def deltaBCS(temp):
    r"""Return the reduced BCS gap deltar = delta(T)/delta(T=0).

    Parameters
    ----------
    temp : float
        reduced temperature t=(T/Tc) where Tc is critical temperature.

    Returns
    -------
    deltar : float
        Superconducting gap, delta, normalized by delta(T=0)

    Note
    ----
    Function interpolates data from Muhlschlegel (1959). For temperature below
    1.8 K, the following functional form is used::

        gap = np.exp(-np.sqrt(3.562*temp)*np.exp(-1.764/temp))

    For temperatures below 50 mK, it returns 1.

    """

    #These data points run from t=0.18 to t=1
    #in steps of 0.02 from Muhlschlegel (1959)
    delta_calc = [1.0, 0.9999, 0.9997, 0.9994, 0.9989,
           0.9982, 0.9971, 0.9957, 0.9938, 0.9915,
           0.9885, 0.985,  0.9809, 0.976,  0.9704,
           0.9641, 0.9569, 0.9488, 0.9399, 0.9299,
           0.919,  0.907,  0.8939, 0.8796, 0.864,
           0.8471, 0.8288, 0.8089, 0.7874, 0.764,
           0.7386, 0.711,  0.681,  0.648,  0.6117,
           0.5715, 0.5263, 0.4749, 0.4148, 0.3416,
           0.2436, 0.0]

    t_calc = np.linspace(0.18, 1, len(delta_calc))

    if 1 >= temp >= 0.3:
        #interpolate data from table
        gap = float(si.interp1d(t_calc, delta_calc, kind='cubic')(temp))
    elif temp > 1 or temp < 0:
        gap = 0.0
    elif temp < 0.05:
        gap = 1.0
    else:
        gap = np.exp(-np.sqrt(3.562*temp)*np.exp(-1.764/temp))

    return gap

def refit_QI_curves(resListList,res,tmax=1e6):
    for residx,r in enumerate(resListList):
        for roidx,res_obj in enumerate(r):
            if res_obj.temp<=tmax:
                res_obj.do_lmfit(scr.cmplxIQ_fit,f0=res[residx])
                resListList[residx][roidx] = res_obj
            
    return resListList


def refit_QI_min_freq(resListList):
    for residx,r in enumerate(resListList):
        for roidx,res_obj in enumerate(r):
            minidx = np.argmin(res_obj.logmag)
            res_obj.lmfit_vals[1] = res_obj.freq[minidx]
            res_obj.lmfit_result['default']['values'][1] = res_obj.freq[minidx]

    return resListList




def do_lmfit_ragged(resSweep,
                    model_func,
                    params,
                    param_name='qi',
                    min_temp=None,
                    max_temp=None,
                    powers=None,
                    verbose=False):
    """
    Ragged-data fitter for ResonatorSweep that works for both Qi and f0 models.

    Parameters
    ----------
    resSweep : scraps.ResonatorSweep
        Sweep object; must have resSweep[param_name] as a DataFrame
    model_func : callable
        Function signature: model_func(params, T_array, P_array) -> predicted values
    params : lmfit.Parameters
        Initial fit parameters
    param_name : str
        Name of the parameter to fit ('qi' or 'f0')
    min_temp, max_temp : float, optional
        Temperature filtering
    powers : iterable, optional
        Only fit these power values
    verbose : bool
        Print fit report
    """

    df = resSweep[param_name]
    T_grid = resSweep.tvec
    P_grid = df.columns.values

    T_list, P_list, Y_list, Y_sigma_list = [], [], [], []

    for j, P in enumerate(P_grid):
        col = df.iloc[:, j]
        Tvals = T_grid
        Yvals = col.values

        # Temperature filter
        mask = np.ones_like(Tvals, dtype=bool)
        if min_temp is not None:
            mask &= (Tvals >= min_temp)
        if max_temp is not None:
            mask &= (Tvals <= max_temp)
        if powers is not None and P not in powers:
            continue

        T_list.append(Tvals[mask])
        P_list.append(np.full(np.sum(mask), P))
        Y_list.append(Yvals[mask])

        # pick up uncertainties if available
        sigma_name = param_name + '_sigma'
        if sigma_name in resSweep:
            Y_sigma_list.append(resSweep[sigma_name].iloc[:, j].values[mask])

    T = np.concatenate(T_list)
    P = np.concatenate(P_list)
    Y = np.concatenate(Y_list)
    Y_sigma = np.concatenate(Y_sigma_list) if Y_sigma_list else None

    # Remove any remaining NaNs or infs
    mask_finite = np.isfinite(Y)
    if Y_sigma is not None:
        mask_finite &= np.isfinite(Y_sigma)

    T = T[mask_finite]
    P = P[mask_finite]
    Y = Y[mask_finite]
    Y_sigma = Y_sigma[mask_finite] if Y_sigma is not None else None

    if Y.size == 0:
        raise ValueError(f"No valid points left to fit for parameter '{param_name}'")

    # residual function
    def residual(fit_params):
        model_Y = model_func(fit_params, T, P)
        model_Y = np.asarray(model_Y).reshape(-1)

        # guard against NaNs in the model
        if not np.all(np.isfinite(model_Y)):
            bad_mask = ~np.isfinite(model_Y)
            model_Y = model_Y.copy()
            model_Y[bad_mask] = 0.0

        resid = Y - model_Y
        if Y_sigma is not None:
            resid = resid / Y_sigma
        return resid

    # run the fit
    minner = lf.Minimizer(residual, params)
    result = minner.minimize()

    if verbose:
        lf.report_fit(result)

    return result

