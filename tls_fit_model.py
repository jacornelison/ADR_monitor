# -*- coding: utf-8 -*-
"""
Created on Tue Dec 17 15:37:50 2024

@author: Jcornelison
"""
import numpy as np
from scipy.special import digamma, i0, k0
import scipy.constants as sc
import scipy.interpolate as si

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
